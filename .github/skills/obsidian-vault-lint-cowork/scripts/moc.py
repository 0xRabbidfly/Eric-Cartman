"""Phase 4 - MOC Reorganization: clean dead entries, deduplicate, propose Topic MOCs.

Cowork-native fork: imports the local obsidian.py adapter.
"""
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(_SCRIPT_DIR))
from obsidian import Obsidian
from inventory import MASTER_MOC_PATH, _WIKILINK_RE, _SECTION_RE

TOPIC_MOC_THRESHOLD = 12


@dataclass
class MOCResult:
    dead_entries_removed: int = 0
    sections_deduped: int = 0
    topic_moc_proposals: list = field(default_factory=list)
    changes: list = field(default_factory=list)


def reorganize_moc(dry_run: bool = False, verbose: bool = False) -> MOCResult:
    ob = Obsidian()
    result = MOCResult()

    all_files = ob.files(ext="md").lines()
    all_slugs = {p.rsplit("/", 1)[-1].replace(".md", "") for p in all_files}

    moc_content = ob.read(path=MASTER_MOC_PATH)
    new_content, removed, deduped = _clean_moc(moc_content, all_slugs, verbose=verbose)

    result.dead_entries_removed = removed
    result.sections_deduped = deduped

    if removed > 0 or deduped > 0:
        if not dry_run:
            ob.create(path=MASTER_MOC_PATH, content=new_content, overwrite=True)
        if removed:
            result.changes.append(f"Removed {removed} dead MOC entries (targets no longer exist)")
        if deduped:
            result.changes.append(f"Removed {deduped} duplicate entries within MOC sections")
        if verbose and dry_run:
            print(f"[moc] [DRY RUN] Would remove {removed} dead entries, {deduped} duplicates")

    result.topic_moc_proposals = _find_topic_moc_candidates(new_content)
    if verbose and result.topic_moc_proposals:
        names = [p["section"] for p in result.topic_moc_proposals]
        print(f"[moc] {len(result.topic_moc_proposals)} Topic MOC candidates: {names}")

    return result


def _clean_moc(content: str, all_slugs: set, verbose: bool = False) -> tuple:
    lines = content.splitlines()
    removed = 0
    deduped = 0
    result_lines = []

    current_section = None
    seen_in_section: dict = {}

    for line in lines:
        if _SECTION_RE.match(line):
            current_section = line.strip()
            seen_in_section[current_section] = set()
            result_lines.append(line)
            continue

        link_match = _WIKILINK_RE.search(line)
        if not link_match:
            result_lines.append(line)
            continue

        slug = link_match.group(1).strip().split("|")[0]

        if slug not in all_slugs:
            if verbose:
                print(f"[moc] Dead entry removed: [[{slug}]]")
            removed += 1
            continue

        section_seen = seen_in_section.get(current_section, set())
        if slug in section_seen:
            if verbose:
                print(f"[moc] Duplicate removed in '{current_section}': [[{slug}]]")
            deduped += 1
            continue

        section_seen.add(slug)
        if current_section:
            seen_in_section[current_section] = section_seen
        result_lines.append(line)

    return "\n".join(result_lines), removed, deduped


def _find_topic_moc_candidates(content: str) -> list:
    candidates = []
    lines = content.splitlines()
    current_section = None
    section_slugs = []

    def flush():
        if current_section and len(section_slugs) > TOPIC_MOC_THRESHOLD:
            safe_name = re.sub(r"[^\w\s-]", "", current_section).strip()
            candidates.append({
                "section": current_section,
                "entry_count": len(section_slugs),
                "sample_slugs": list(section_slugs[:5]),
                "proposed_moc_name": f"MOC - {safe_name}",
                "proposed_moc_path": f"Research/Library/00 MOC/\U0001f4cd MOC - {safe_name}.md",
            })

    for line in lines:
        m = _SECTION_RE.match(line)
        if m:
            flush()
            current_section = m.group(2).strip()
            section_slugs = []
            continue
        lm = _WIKILINK_RE.search(line)
        if lm and current_section:
            section_slugs.append(lm.group(1).strip())

    flush()
    return candidates


def format_moc_proposals(proposals: list, run_date: str) -> str:
    if not proposals:
        return ""
    lines = [
        f"# Vault Lint - MOC Reorganization Proposals - {run_date}",
        "",
        "> These sections have grown large. Create Topic MOCs to reduce Master MOC size.",
        "",
    ]
    for p in proposals:
        lines += [
            f"## {p['section']} ({p['entry_count']} entries)",
            f"Proposed new Topic MOC: `{p['proposed_moc_name']}`",
            f"Suggested path: `{p['proposed_moc_path']}`",
            "",
            f"Seed notes ({min(5, len(p['sample_slugs']))} shown):",
        ]
        for slug in p["sample_slugs"]:
            lines.append(f"- [[{slug}]]")
        lines.append("")
    return "\n".join(lines)
