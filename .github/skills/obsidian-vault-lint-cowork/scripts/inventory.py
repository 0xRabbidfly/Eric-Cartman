"""Phase 1 - Inventory: read-only vault health scan."""
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(_SCRIPT_DIR))
from obsidian import Obsidian, _SKIP_DIRS

MASTER_MOC_PATH = "Research/Library/00 MOC/\U0001f5fa️ MOC - Research Library.md"
LIBRARY_FOLDER = "Research/Library"
MOC_FOLDER = "Research/Library/00 MOC"
LOG_FOLDER = "Research/Logs"

# Scoping: which folders' broken-link and orphan counts should be reported.
# Other folders are intentionally noisy:
#   - "Personal - Nuno/" - OneNote migration; user does not want forced linking here
#   - "Podcasts/" - importer creates aspirational stubs like [[Companies/Anthropic]]
#   - "Research/Dailies/" - daily notes; orphan by design
# Set to None to disable filtering for that metric.
ORPHAN_SCOPE_FOLDERS = (LIBRARY_FOLDER,)
BROKEN_LINK_SCOPE_FOLDERS = (LIBRARY_FOLDER, "Research/Reports", "Research/Logs")

# Wikilink targets ending in these extensions are attachments, not note links.
# The underlying graph builder only indexes .md files, so attachment links would
# otherwise always appear as "unresolved" even when the file exists.
_ATTACHMENT_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp",
    ".pdf", ".mp4", ".mov", ".webm", ".mp3", ".wav", ".m4a",
    ".xlsx", ".xls", ".docx", ".doc", ".pptx", ".ppt",
    ".zip", ".csv", ".json",
}

_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
_SECTION_RE = re.compile(r"^(#+)\s+(.+)$")


@dataclass
class InventoryResult:
    orphans: list = field(default_factory=list)
    broken_links: list = field(default_factory=list)
    deadend_research: list = field(default_factory=list)
    missing_from_moc: list = field(default_factory=list)
    stale_recently_added: list = field(default_factory=list)
    similar_tags: list = field(default_factory=list)
    library_note_count: int = 0
    orphan_count: int = 0
    deadend_count: int = 0
    orphans_unscoped_count: int = 0
    broken_links_unscoped_count: int = 0


def _in_scope(path: str, scope_folders) -> bool:
    if scope_folders is None:
        return True
    return any(path.startswith(folder.rstrip("/") + "/") for folder in scope_folders)


_VAULT_BASENAMES_CACHE: dict = {}


def _vault_basenames(vault_path: Path) -> set:
    """Set of every filename in the vault, walked once per vault path and cached.

    Replaces a per-link `rglob` (which walked the entire tree once for every
    broken attachment link — O(links x tree) and the dominant cost on large
    vaults). Building the set once is O(tree); lookups are then O(1).
    """
    key = str(vault_path)
    cached = _VAULT_BASENAMES_CACHE.get(key)
    if cached is not None:
        return cached
    names: set = set()
    for root, dirs, files in os.walk(vault_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        names.update(files)
    _VAULT_BASENAMES_CACHE[key] = names
    return names


def _is_attachment_link(link: str, vault_path: Path) -> bool:
    """Return True if `link` is an attachment reference whose target file exists in the vault."""
    ext = os.path.splitext(link)[1].lower()
    if ext not in _ATTACHMENT_EXTS:
        return False
    return os.path.basename(link) in _vault_basenames(vault_path)


def collect_inventory(stale_days: int = 7, verbose: bool = False) -> InventoryResult:
    ob = Obsidian()
    result = InventoryResult()

    if verbose:
        print("[inventory] Collecting orphans...")
    orphan_lines = ob.orphans().lines()
    result.orphans_unscoped_count = len(orphan_lines)
    result.orphans = [o for o in orphan_lines if _in_scope(o, ORPHAN_SCOPE_FOLDERS)]
    result.orphan_count = len(result.orphans)

    if verbose:
        print(f"[inventory] Orphans (scoped): {result.orphan_count} / {result.orphans_unscoped_count} unscoped")
        print("[inventory] Collecting library notes...")

    library_notes = ob.files(folder=LIBRARY_FOLDER, ext="md").lines()
    content_notes = [n for n in library_notes if not n.startswith(MOC_FOLDER)]
    result.library_note_count = len(content_notes)
    content_slugs = {n.rsplit("/", 1)[-1].replace(".md", ""): n for n in content_notes}

    if verbose:
        print(f"[inventory] Library notes: {result.library_note_count}")
        print("[inventory] Checking Master MOC coverage...")

    try:
        moc_content = ob.read(path=MASTER_MOC_PATH)
        # Coverage: a Library note is "in the MOC system" if any file in the
        # 00 MOC folder references it (Master MOC OR any Topic MOC).
        all_moc_slugs = set()
        for moc_path in ob.files(folder=MOC_FOLDER, ext="md").lines():
            try:
                all_moc_slugs |= _extract_wikilink_slugs(ob.read(path=moc_path))
            except Exception:
                pass
        result.missing_from_moc = [
            path for slug, path in content_slugs.items() if slug not in all_moc_slugs
        ]
        result.stale_recently_added = _find_stale_recently_added(moc_content, stale_days)
    except Exception as e:
        print(f"[inventory] Could not read Master MOC: {e}", file=sys.stderr)

    if verbose:
        print(f"[inventory] Missing from MOC: {len(result.missing_from_moc)}")
        print("[inventory] Collecting broken links...")

    unresolved_text = ob.unresolved(verbose=True).text
    all_broken = _parse_unresolved(unresolved_text)
    # Filter out attachment links that actually resolve to a file (graph only indexes .md)
    vault_root = Path(ob.vault_path)
    all_broken = [b for b in all_broken if not _is_attachment_link(b["link"], vault_root)]
    result.broken_links_unscoped_count = len(all_broken)
    result.broken_links = [b for b in all_broken if _in_scope(b["file"], BROKEN_LINK_SCOPE_FOLDERS)]

    if verbose:
        print(f"[inventory] Broken links (scoped): {len(result.broken_links)} / {result.broken_links_unscoped_count} unscoped")
        print("[inventory] Collecting dead-ends in Research/...")

    deadend_lines = ob.deadends().lines()
    result.deadend_research = [n for n in deadend_lines if n.startswith("Research/")]
    result.deadend_count = len(result.deadend_research)

    if verbose:
        print(f"[inventory] Dead-ends in Research: {result.deadend_count}")
        print("[inventory] Checking tag similarity...")

    result.similar_tags = _find_similar_tags(ob)

    if verbose:
        print(f"[inventory] Similar tag pairs: {len(result.similar_tags)}")

    return result


def _extract_wikilink_slugs(content: str) -> set:
    return {m.group(1).strip() for m in _WIKILINK_RE.finditer(content)}


def _find_stale_recently_added(moc_content: str, stale_days: int) -> list:
    stale = []
    lines = moc_content.splitlines()
    in_recently_added = False
    today = date.today()

    for i, line in enumerate(lines):
        if re.match(r"^#+\s+Recently Added", line, re.IGNORECASE):
            in_recently_added = True
            continue
        if in_recently_added and re.match(r"^#+\s+", line):
            break
        if not in_recently_added:
            continue

        link_match = _WIKILINK_RE.search(line)
        if not link_match:
            continue
        date_match = _DATE_RE.search(line)
        if not date_match:
            continue

        slug = link_match.group(1).strip()
        try:
            entry_date = datetime.strptime(date_match.group(1), "%Y-%m-%d").date()
        except ValueError:
            continue
        age_days = (today - entry_date).days

        if age_days > stale_days:
            stale.append({
                "line_index": i,
                "slug": slug,
                "date": str(entry_date),
                "age_days": age_days,
                "raw_line": line,
            })

    return stale


def _parse_unresolved(text: str) -> list:
    broken = []
    current_file = None
    for line in text.splitlines():
        if not line.strip():
            continue
        if not (line.startswith(" ") or line.startswith("\t")):
            current_file = line.strip()
        else:
            link = line.strip()
            if link and current_file:
                broken.append({"file": current_file, "link": link})
    return broken


def _find_similar_tags(ob: Obsidian) -> list:
    tags_raw = ob.tags(sort="count", format="tsv").lines()
    tag_names = []
    for line in tags_raw:
        parts = line.split("\t")
        if parts:
            tag_names.append(parts[0].strip())

    similar = []
    seen = set()
    for i, t1 in enumerate(tag_names):
        for j, t2 in enumerate(tag_names):
            if i >= j:
                continue
            t1n = t1.lower().replace("-", "").replace("_", "").replace("#", "")
            t2n = t2.lower().replace("-", "").replace("_", "").replace("#", "")
            ratio = SequenceMatcher(None, t1n, t2n).ratio()
            if ratio > 0.7 and (t1, t2) not in seen:
                seen.add((t1, t2))
                similar.append({"t1": t1, "t2": t2, "ratio": ratio})
    return similar
