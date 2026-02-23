"""Obsidian vault reader/writer for daily-research pipeline.

Reads existing dailies and library notes for deduplication.
Writes new daily research notes directly to the vault filesystem.
Obsidian auto-detects file changes — no CLI needed.
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


def get_vault_paths(config: dict) -> Tuple[Path, Path, Path]:
    """Return (vault_root, dailies_dir, library_dir) from config."""
    vault = Path(config["vault_path"])
    dailies = vault / config.get("dailies_folder", "Research/Dailies")
    library = vault / config.get("library_folder", "Research/Library")
    return vault, dailies, library


def ensure_dirs(config: dict) -> Tuple[Path, Path]:
    """Create dailies and library directories if needed. Returns (dailies, library)."""
    _, dailies, library = get_vault_paths(config)
    dailies.mkdir(parents=True, exist_ok=True)
    library.mkdir(parents=True, exist_ok=True)
    return dailies, library


def extract_urls_from_file(filepath: Path) -> Set[str]:
    """Extract all URLs from a markdown file."""
    urls: Set[str] = set()
    try:
        text = filepath.read_text(encoding="utf-8", errors="replace")
        # Match URLs in markdown links [text](url) and bare URLs
        for match in re.finditer(r'https?://[^\s\)\]>\"\']+', text):
            url = match.group(0).rstrip(".,;:!?")
            urls.add(url)
    except OSError:
        pass
    return urls


def extract_titles_from_file(filepath: Path) -> Set[str]:
    """Extract article titles from markdown headers and list items."""
    titles: Set[str] = set()
    try:
        text = filepath.read_text(encoding="utf-8", errors="replace")
        # Markdown links in list items: - [Title](url) or - [ ] [Title](url)
        for match in re.finditer(r'[-*]\s*(?:\[[ x]\]\s*)?\[([^\]]+)\]\(', text):
            title = match.group(1).strip().lower()
            if len(title) > 10:  # Skip very short titles
                titles.add(title)
        # ### Headers
        for match in re.finditer(r'^#{2,4}\s+(.+)$', text, re.MULTILINE):
            title = match.group(1).strip().lower()
            if len(title) > 10:
                titles.add(title)
    except OSError:
        pass
    return titles


def load_seen_urls(config: dict) -> Set[str]:
    """Scan all dailies + library notes and return all previously seen URLs.

    This is the dedup set — any URL in here will be excluded from new results.
    Cost: zero tokens (pure filesystem + regex).
    """
    _, dailies, library = get_vault_paths(config)
    seen: Set[str] = set()

    for folder in [dailies, library]:
        if not folder.exists():
            continue
        for md_file in folder.glob("*.md"):
            seen.update(extract_urls_from_file(md_file))

    return seen


def load_seen_titles(config: dict) -> Set[str]:
    """Load previously seen article titles for fuzzy dedup."""
    _, dailies, library = get_vault_paths(config)
    titles: Set[str] = set()

    for folder in [dailies, library]:
        if not folder.exists():
            continue
        for md_file in folder.glob("*.md"):
            titles.update(extract_titles_from_file(md_file))

    return titles


def title_is_seen(title: str, seen_titles: Set[str], threshold: float = 0.8) -> bool:
    """Check if a title is similar enough to a seen title (simple word overlap)."""
    if not title or not seen_titles:
        return False
    title_words = set(title.lower().split())
    if len(title_words) < 3:
        return title.lower() in seen_titles

    for seen in seen_titles:
        seen_words = set(seen.split())
        if not seen_words:
            continue
        overlap = len(title_words & seen_words) / max(len(title_words), len(seen_words))
        if overlap >= threshold:
            return True
    return False


def write_daily_note(config: dict, date_str: str, content: str) -> Path:
    """Write a daily research note to the vault.

    Args:
        config: Pipeline config dict
        date_str: Date in YYYY-MM-DD format
        content: Full markdown content

    Returns:
        Path to the written file
    """
    dailies, _ = ensure_dirs(config)
    filepath = dailies / f"{date_str}.md"

    # Don't overwrite — append a suffix if file exists
    if filepath.exists():
        i = 2
        while filepath.exists():
            filepath = dailies / f"{date_str}-{i}.md"
            i += 1

    filepath.write_text(content, encoding="utf-8")
    return filepath


def get_daily_path(config: dict, date_str: str) -> Path:
    """Get the path where a daily note would be written."""
    _, dailies, _ = get_vault_paths(config)
    return dailies / f"{date_str}.md"


def daily_exists(config: dict, date_str: str) -> bool:
    """Check if a daily note already exists for this date."""
    return get_daily_path(config, date_str).exists()
