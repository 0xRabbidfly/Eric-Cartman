"""Obsidian vault operations for obsidian-daily-research pipeline.

Thin wrapper around the vendored Obsidian module. Provides dedup scanning,
daily note writing, and library management via the Obsidian CLI.

Requires Obsidian to be running with CLI enabled.
"""

import re
import sys
from pathlib import Path
from typing import Set, Tuple

# Import from vendor/obsidian (self-contained, no external skill dependency)
_VENDOR_DIR = Path(__file__).resolve().parents[1] / "vendor" / "obsidian"
if str(_VENDOR_DIR) not in sys.path:
    sys.path.insert(0, str(_VENDOR_DIR))

from obsidian import Obsidian

# Module-level client (lazy init)
_ob: Obsidian | None = None

# Cache: vault folder → list of .md files (populated once per process)
_folder_cache: dict[str, list[str]] = {}


def _client() -> Obsidian:
    """Get or create the Obsidian client singleton."""
    global _ob
    if _ob is None:
        _ob = Obsidian()
    return _ob


# ---------------------------------------------------------------------------
# URL / title extraction (pure regex logic — CLI search can't do this)
# ---------------------------------------------------------------------------

def extract_urls_from_text(text: str) -> Set[str]:
    """Extract all URLs from markdown text."""
    urls: Set[str] = set()
    for match in re.finditer(r'https?://[^\s\)\]>\"\']+', text):
        url = match.group(0).rstrip(".,;:!?")
        urls.add(url)
    return urls


def extract_titles_from_text(text: str) -> Set[str]:
    """Extract article titles from markdown headers and list items."""
    titles: Set[str] = set()
    for match in re.finditer(r'[-*]\s*(?:\[[ x]\]\s*)?\[([^\]]+)\]\(', text):
        title = match.group(1).strip().lower()
        if len(title) > 10:
            titles.add(title)
    for match in re.finditer(r'^#{2,4}\s+(.+)$', text, re.MULTILINE):
        title = match.group(1).strip().lower()
        if len(title) > 10:
            titles.add(title)
    return titles


def title_is_seen(title: str, seen_titles: Set[str], threshold: float = 0.8) -> bool:
    """Check if a title is similar enough to a seen title (word overlap)."""
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


# ---------------------------------------------------------------------------
# Vault scanning (reads files via CLI, extracts with regex)
# ---------------------------------------------------------------------------

def _scan_folder_files(folder: str) -> list[str]:
    """List .md files in a vault folder via CLI (cached per process)."""
    if folder in _folder_cache:
        return _folder_cache[folder]
    ob = _client()
    result = ob.files(folder=folder, ext="md")
    files = result.lines() if result.ok else []
    _folder_cache[folder] = files
    return files


def _read_vault_file(filepath: str) -> str:
    """Read a file from the vault via CLI."""
    ob = _client()
    return ob.read(path=filepath)


def _scan_folder_recursive(folder: str) -> list[str]:
    """List .md files recursively in a vault folder.

    Handles both flat (legacy) and year/month subfolder layouts.
    Scans the root folder, then any YYYY/ and YYYY/MM/ sub-dirs.
    """
    all_files: list[str] = []
    # Root-level files
    all_files.extend(_scan_folder_files(folder))

    # Scan year sub-folders (e.g. Research/Dailies/2026/)
    import datetime
    current_year = datetime.datetime.now().year
    for year in range(2024, current_year + 2):
        year_folder = f"{folder}/{year}"
        for month in range(1, 13):
            month_folder = f"{year_folder}/{month:02d}"
            month_files = _scan_folder_files(month_folder)
            all_files.extend(month_files)
        # Also check files directly in the year folder
        year_files = _scan_folder_files(year_folder)
        all_files.extend(year_files)

    return all_files


def load_seen_dedup(config: dict) -> tuple[Set[str], Set[str]]:
    """Scan all dailies + library notes in ONE pass, returning (seen_urls, seen_titles).

    Replaces separate load_seen_urls / load_seen_titles calls to halve the
    number of Obsidian CLI file-read operations.
    """
    dailies_folder = config.get("dailies_folder", "Research/Dailies")
    library_folder = config.get("library_folder", "Research/Library")
    seen_urls: Set[str] = set()
    seen_titles: Set[str] = set()

    all_files = list(_scan_folder_recursive(dailies_folder)) + list(_scan_folder_files(library_folder))
    for filepath in all_files:
        text = _read_vault_file(filepath)
        if text:
            seen_urls.update(extract_urls_from_text(text))
            seen_titles.update(extract_titles_from_text(text))

    return seen_urls, seen_titles


def load_seen_urls(config: dict) -> Set[str]:
    """Return all previously seen URLs from dailies + library.

    Prefer load_seen_dedup() when you need both URLs and titles.
    """
    urls, _ = load_seen_dedup(config)
    return urls


def load_seen_titles(config: dict) -> Set[str]:
    """Return all previously seen article titles for fuzzy dedup.

    Prefer load_seen_dedup() when you need both URLs and titles.
    """
    _, titles = load_seen_dedup(config)
    return titles


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def _daily_path(dailies_folder: str, date_str: str) -> str:
    """Build year/month sub-path for a daily note.

    e.g. Research/Dailies/2026/02/2026-02-26.md
    """
    try:
        year = date_str[:4]
        month = date_str[5:7]
        return f"{dailies_folder}/{year}/{month}/{date_str}.md"
    except (IndexError, ValueError):
        return f"{dailies_folder}/{date_str}.md"


def write_daily_note(config: dict, date_str: str, content: str) -> str:
    """Write a daily research note to the vault via CLI.

    Organizes into year/month subfolders:
      Research/Dailies/2026/02/2026-02-26.md

    Returns the path of the written file.
    """
    dailies_folder = config.get("dailies_folder", "Research/Dailies")
    ob = _client()

    path = _daily_path(dailies_folder, date_str)

    # Don't overwrite — find an available filename
    if ob.exists(path=path):
        base = path.rsplit('.md', 1)[0]
        i = 2
        while ob.exists(path=f"{base}-{i}.md"):
            i += 1
        path = f"{base}-{i}.md"

    ob.create(path=path, content=content)
    return path


def daily_exists(config: dict, date_str: str) -> bool:
    """Check if a daily note already exists for this date."""
    dailies_folder = config.get("dailies_folder", "Research/Dailies")
    # Check both new (year/month) and legacy (flat) paths
    new_path = _daily_path(dailies_folder, date_str)
    legacy_path = f"{dailies_folder}/{date_str}.md"
    ob = _client()
    return ob.exists(path=new_path) or ob.exists(path=legacy_path)


# ---------------------------------------------------------------------------
# Library / promote helpers
# ---------------------------------------------------------------------------

def read_file(path: str) -> str:
    """Read a vault file by path."""
    return _client().read(path=path)


def write_file(path: str, content: str) -> None:
    """Write (create/overwrite) a vault file by path."""
    _client().create(path=path, content=content, overwrite=True)


def append_to_file(path: str, content: str) -> None:
    """Append content to a vault file."""
    _client().append(content, path=path)


def file_exists(path: str) -> bool:
    """Check if a file exists in the vault."""
    return _client().exists(path=path)


def list_md_files(folder: str) -> list[str]:
    """List .md files in a vault folder."""
    return _scan_folder_files(folder)
