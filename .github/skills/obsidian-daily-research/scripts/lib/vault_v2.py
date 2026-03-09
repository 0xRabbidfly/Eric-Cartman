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

# Cache: vault file path → content (populated once per process, invalidated on write)
_file_content_cache: dict[str, str] = {}

# Vault filesystem root (set from config on first use; enables direct FS I/O)
_vault_fs_root: str | None = None


def _client() -> Obsidian:
    """Get or create the Obsidian client singleton."""
    global _ob
    if _ob is None:
        _ob = Obsidian()
    return _ob


def _init_fs(config: dict) -> None:
    """Populate _vault_fs_root from config (idempotent, call at start of any config-aware function).

    When the vault root is a real directory on disk, subsequent _scan_folder_files()
    and _read_vault_file() calls go directly to the filesystem — zero CLI spawns.
    This eliminates the 300+ Obsidian.com subprocess invocations that previously
    caused IPC overload and spurious new-window openings.
    """
    global _vault_fs_root
    if _vault_fs_root:
        return  # already set
    root = config.get("vault_path", "")
    if root and Path(root).is_dir():
        _vault_fs_root = root


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
    """List .md files in a vault folder (cached per process).

    Uses filesystem I/O when _vault_fs_root is set (fast, no CLI spawns).
    Falls back to Obsidian CLI when vault root is not known.
    """
    if folder in _folder_cache:
        return _folder_cache[folder]

    vault_root = _vault_fs_root
    if vault_root:
        base = Path(vault_root) / folder
        if base.is_dir():
            files = sorted(
                f"{folder}/{f.name}"
                for f in base.iterdir()
                if f.is_file() and f.suffix == ".md"
            )
        else:
            files = []
    else:
        ob = _client()
        result = ob.files(folder=folder, ext="md")
        files = result.lines() if result.ok else []

    _folder_cache[folder] = files
    return files


def _read_vault_file(filepath: str) -> str:
    """Read a file from the vault (cached per process).

    Uses filesystem I/O when _vault_fs_root is set (fast, no CLI spawns).
    Falls back to Obsidian CLI when vault root is not known.
    """
    if filepath in _file_content_cache:
        return _file_content_cache[filepath]

    vault_root = _vault_fs_root
    if vault_root:
        full = Path(vault_root) / filepath
        try:
            text = full.read_text(encoding="utf-8", errors="replace") if full.exists() else ""
        except Exception:
            text = ""
    else:
        ob = _client()
        text = ob.read(path=filepath)

    _file_content_cache[filepath] = text
    return text


def _scan_folder_recursive(folder: str) -> list[str]:
    """List .md files recursively in a vault folder.

    Uses os.walk on the filesystem when _vault_fs_root is set — one syscall
    traversal instead of 50+ individual folder-listing CLI calls.
    Falls back to the sub-folder loop (CLI) when vault root is not known.
    """
    vault_root = _vault_fs_root
    if vault_root:
        base = Path(vault_root) / folder
        if not base.is_dir():
            return []
        all_files = []
        for dirpath, _dirs, filenames in base.walk() if hasattr(base, "walk") else _os_walk(base):
            rel_dir = str(Path(dirpath).relative_to(Path(vault_root))).replace("\\", "/")
            for fname in sorted(filenames):
                if fname.endswith(".md"):
                    all_files.append(f"{rel_dir}/{fname}")
        return all_files

    # --- Fallback: CLI-based enumeration (used when vault_path is not configured) ---
    all_files: list[str] = []
    all_files.extend(_scan_folder_files(folder))

    import datetime
    current_year = datetime.datetime.now().year
    for year in range(2024, current_year + 2):
        year_folder = f"{folder}/{year}"
        for month in range(1, 13):
            month_folder = f"{year_folder}/{month:02d}"
            month_files = _scan_folder_files(month_folder)
            all_files.extend(month_files)
        year_files = _scan_folder_files(year_folder)
        all_files.extend(year_files)

    return all_files


def _os_walk(base: Path):
    """Compatibility shim: use os.walk when Path.walk() is not available (Python <3.12)."""
    import os
    for dirpath, dirnames, filenames in os.walk(str(base)):
        dirnames.sort()
        yield dirpath, dirnames, filenames


def load_seen_dedup(config: dict) -> tuple[Set[str], Set[str]]:
    """Scan all dailies + library notes in ONE pass, returning (seen_urls, seen_titles).

    Replaces separate load_seen_urls / load_seen_titles calls to halve the
    number of Obsidian CLI file-read operations.
    """
    _init_fs(config)  # enable FS-direct reads if vault_path is valid
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
    """Write a daily research note to the vault.

    Organizes into year/month subfolders:
      Research/Dailies/2026/02/2026-02-26.md

    Writes directly to the vault filesystem when vault_path is configured
    (avoids the named-pipe size limit that causes Pipe errors on large notes).
    Falls back to Obsidian CLI when vault root is not available.

    Returns the vault-relative path of the written file.
    """
    _init_fs(config)
    dailies_folder = config.get("dailies_folder", "Research/Dailies")
    path = _daily_path(dailies_folder, date_str)

    vault_root = _vault_fs_root
    if vault_root:
        full_path = Path(vault_root) / path
        if full_path.exists():
            raise FileExistsError(f"Daily note already exists: {path}")
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        # Populate cache so subsequent reads in same run don't re-read disk
        _file_content_cache[path] = content
    else:
        ob = _client()
        if ob.exists(path=path):
            raise FileExistsError(f"Daily note already exists: {path}")
        ob.create(path=path, content=content)

    return path


def daily_exists(config: dict, date_str: str) -> bool:
    """Check if a daily note already exists for this date."""
    _init_fs(config)
    dailies_folder = config.get("dailies_folder", "Research/Dailies")
    new_path = _daily_path(dailies_folder, date_str)
    legacy_path = f"{dailies_folder}/{date_str}.md"

    vault_root = _vault_fs_root
    if vault_root:
        if (Path(vault_root) / new_path).exists():
            return True
        if (Path(vault_root) / legacy_path).exists():
            return True
        return False

    ob = _client()
    if ob.exists(path=new_path) or ob.exists(path=legacy_path):
        return True

    base = new_path.rsplit('.md', 1)[0]
    suffix = 2
    while ob.exists(path=f"{base}-{suffix}.md"):
        return True

    legacy_base = legacy_path.rsplit('.md', 1)[0]
    suffix = 2
    while ob.exists(path=f"{legacy_base}-{suffix}.md"):
        return True

    return False


# ---------------------------------------------------------------------------
# Library / promote helpers
# ---------------------------------------------------------------------------

def read_file(path: str) -> str:
    """Read a vault file by path (uses FS cache when available)."""
    return _read_vault_file(path)


def write_file(path: str, content: str) -> None:
    """Write (create/overwrite) a vault file by path.

    Writes directly to the vault filesystem when vault_path is configured
    (avoids the named-pipe size limit on large content).
    """
    vault_root = _vault_fs_root
    if vault_root:
        full_path = Path(vault_root) / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        # Invalidate the in-process cache so the next read sees new content
        _file_content_cache[path] = content
    else:
        _client().create(path=path, content=content, overwrite=True)


def append_to_file(path: str, content: str) -> None:
    """Append content to a vault file."""
    _client().append(content, path=path)


def file_exists(path: str) -> bool:
    """Check if a file exists in the vault."""
    vault_root = _vault_fs_root
    if vault_root:
        return (Path(vault_root) / path).exists()
    return _client().exists(path=path)


def list_md_files(folder: str) -> list[str]:
    """List .md files in a vault folder."""
    return _scan_folder_files(folder)
