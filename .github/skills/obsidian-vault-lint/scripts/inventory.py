"""Phase 1 — Inventory: read-only vault health scan."""
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent.resolve()
_SKILLS_ROOT = _SCRIPT_DIR.parent.parent
sys.path.insert(0, str(_SKILLS_ROOT / "obsidian" / "scripts"))
from obsidian import Obsidian

MASTER_MOC_PATH = "Research/Library/00 MOC/🗺️ MOC - Research Library.md"
LIBRARY_FOLDER = "Research/Library"
MOC_FOLDER = "Research/Library/00 MOC"
LOG_FOLDER = "Research/Logs"

_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
_SECTION_RE = re.compile(r"^(#+)\s+(.+)$")


@dataclass
class InventoryResult:
    orphans: list = field(default_factory=list)
    broken_links: list = field(default_factory=list)   # [{file, link}]
    deadend_research: list = field(default_factory=list)
    missing_from_moc: list = field(default_factory=list)
    stale_recently_added: list = field(default_factory=list)  # [{line_index, slug, date, age_days, raw_line}]
    similar_tags: list = field(default_factory=list)   # [{t1, t2, ratio}]
    library_note_count: int = 0
    orphan_count: int = 0
    deadend_count: int = 0


def collect_inventory(stale_days: int = 7, verbose: bool = False) -> InventoryResult:
    ob = Obsidian()
    result = InventoryResult()

    if verbose:
        print("[inventory] Collecting orphans...")
    orphan_lines = ob.orphans().lines()
    result.orphans = orphan_lines
    result.orphan_count = len(orphan_lines)
    orphan_set = set(orphan_lines)

    if verbose:
        print(f"[inventory] Orphans: {result.orphan_count}")
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
        moc_links = _extract_wikilink_slugs(moc_content)
        result.missing_from_moc = [
            path for slug, path in content_slugs.items() if slug not in moc_links
        ]
        result.stale_recently_added = _find_stale_recently_added(moc_content, stale_days)
    except Exception as e:
        print(f"[inventory] Could not read Master MOC: {e}", file=sys.stderr)

    if verbose:
        print(f"[inventory] Missing from MOC: {len(result.missing_from_moc)}")
        print("[inventory] Collecting broken links...")

    unresolved_text = ob.unresolved(verbose=True).text
    result.broken_links = _parse_unresolved(unresolved_text)

    if verbose:
        print(f"[inventory] Broken links: {len(result.broken_links)}")
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
    """Find entries in the ## Recently Added section older than stale_days."""
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
    """Parse verbose unresolved output into [{file, link}] list."""
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
