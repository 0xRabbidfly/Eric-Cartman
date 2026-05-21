"""Phase 2 - Autonomous Fixes: safe, reversible vault writes.

Cowork-native fork: imports the local obsidian.py adapter.
"""
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(_SCRIPT_DIR))
from obsidian import Obsidian
from inventory import InventoryResult, MASTER_MOC_PATH, MOC_FOLDER, _WIKILINK_RE, _SECTION_RE


@dataclass
class FixResult:
    stale_pruned: int = 0
    moc_entries_added: int = 0
    broken_links_fixed: int = 0
    moc_sections_sorted: int = 0
    changes: list = field(default_factory=list)


def apply_fixes(inv: InventoryResult, dry_run: bool = False, verbose: bool = False) -> FixResult:
    ob = Obsidian()
    result = FixResult()

    moc_content = ob.read(path=MASTER_MOC_PATH)
    moc_backup = moc_content
    moc_modified = False

    # 1. Prune stale Recently Added entries
    if inv.stale_recently_added:
        moc_content, pruned = _prune_stale_recently_added(moc_content, inv.stale_recently_added)
        if pruned > 0:
            moc_modified = True
            result.stale_pruned = pruned
            result.changes.append({"type": "prune_stale", "detail": f"Pruned {pruned} stale Recently Added entries"})
            if verbose:
                print(f"[fixes] Pruned {pruned} stale Recently Added entries")

    # 2. Add missing notes to Master MOC
    if inv.missing_from_moc:
        moc_content, added = _add_missing_to_moc(moc_content, inv.missing_from_moc)
        if added > 0:
            moc_modified = True
            result.moc_entries_added = added
            result.changes.append({"type": "add_to_moc", "detail": f"Added {added} missing notes to Master MOC"})
            if verbose:
                print(f"[fixes] Added {added} notes to Master MOC")

    # 3. Sort MOC sections alphabetically
    moc_content, sorted_count = _sort_moc_sections(moc_content)
    if sorted_count > 0:
        moc_modified = True
        result.moc_sections_sorted = sorted_count
        result.changes.append({"type": "sort_moc", "detail": f"Sorted {sorted_count} MOC sections alphabetically"})
        if verbose:
            print(f"[fixes] Sorted {sorted_count} MOC sections")

    if moc_modified:
        if not dry_run:
            try:
                ob.create(path=MASTER_MOC_PATH, content=moc_content, overwrite=True)
            except Exception as e:
                print(f"[fixes] ERROR writing MOC - original content was at: {MASTER_MOC_PATH}", file=sys.stderr)
                print(f"[fixes] Error: {e}", file=sys.stderr)
                print(f"[fixes] MOC backup length: {len(moc_backup)} chars. Manual recovery may be needed.", file=sys.stderr)
        else:
            if verbose:
                print("[fixes] [DRY RUN] MOC changes not written")

    # 4. Broken wikilinks - report only (auto-fix disabled 2026-05-19)
    # The previous behavior stripped brackets, demoting [[foo]] -> foo (destructive).
    # That ate attachment-style links and aliases without resolving them. Now we leave
    # broken links in place and surface them in the report so the user can decide
    # note-by-note. inventory.py already scopes broken_links to Research/ folders to
    # cut out aspirational stubs from the podcast importer.
    if inv.broken_links and verbose:
        print(f"[fixes] {len(inv.broken_links)} broken wikilinks left for manual review")

    return result


def _prune_stale_recently_added(content: str, stale: list) -> tuple:
    stale_indices = {item["line_index"] for item in stale}
    lines = content.splitlines()
    new_lines = [line for i, line in enumerate(lines) if i not in stale_indices]
    return "\n".join(new_lines), len(stale_indices)


def _add_missing_to_moc(content: str, missing_paths: list) -> tuple:
    lines = content.splitlines()
    added = 0

    by_section = defaultdict(list)
    ungrouped = []
    for path in missing_paths:
        parts = path.split("/")
        if len(parts) >= 4 and parts[:2] == ["Research", "Library"]:
            folder = parts[2]
            if not folder.startswith("00"):
                slug = parts[-1].replace(".md", "")
                by_section[folder].append(slug)
        else:
            slug = path.rsplit("/", 1)[-1].replace(".md", "")
            ungrouped.append(slug)

    for section_name, slugs in by_section.items():
        lines, count = _insert_into_section(lines, section_name, slugs)
        added += count

    if ungrouped:
        lines.append("")
        for slug in sorted(ungrouped):
            lines.append(f"- [[{slug}]]")
        added += len(ungrouped)

    return "\n".join(lines), added


def _insert_into_section(lines: list, section_name: str, slugs: list) -> tuple:
    section_start = None
    section_end = None

    for i, line in enumerate(lines):
        m = _SECTION_RE.match(line)
        if m:
            header_text = m.group(2).strip()
            if (header_text.lower() == section_name.lower()
                    or header_text.lower().startswith(section_name.lower())):
                section_start = i
            elif section_start is not None and section_end is None:
                section_end = i
                break

    if section_start is None:
        lines.append("")
        lines.append(f"## {section_name}")
        for slug in sorted(slugs):
            lines.append(f"- [[{slug}]]")
        return lines, len(slugs)

    if section_end is None:
        section_end = len(lines)

    section_body = lines[section_start + 1:section_end]
    existing = {_WIKILINK_RE.search(l).group(1).strip() for l in section_body if _WIKILINK_RE.search(l)}
    new_slugs = [s for s in slugs if s not in existing]
    if not new_slugs:
        return lines, 0

    link_lines = [l for l in section_body if _WIKILINK_RE.search(l)]
    other_lines = [l for l in section_body if not _WIKILINK_RE.search(l)]

    for slug in new_slugs:
        link_lines.append(f"- [[{slug}]]")

    link_lines.sort(key=lambda l: (_WIKILINK_RE.search(l).group(1).lower() if _WIKILINK_RE.search(l) else l.lower()))
    new_section = [lines[section_start]] + other_lines + link_lines
    lines = lines[:section_start] + new_section + lines[section_end:]
    return lines, len(new_slugs)


def _sort_moc_sections(content: str) -> tuple:
    lines = content.splitlines()
    sorted_count = 0

    sections = []
    current_start = None
    for i, line in enumerate(lines):
        if _SECTION_RE.match(line):
            if current_start is not None:
                sections.append((current_start, i))
            current_start = i
    if current_start is not None:
        sections.append((current_start, len(lines)))

    for sec_start, sec_end in sections:
        link_indices = [i for i in range(sec_start + 1, sec_end) if _WIKILINK_RE.search(lines[i])]
        if len(link_indices) < 2:
            continue

        link_lines = [lines[i] for i in link_indices]
        sorted_links = sorted(
            link_lines,
            key=lambda l: (_WIKILINK_RE.search(l).group(1).lower() if _WIKILINK_RE.search(l) else l.lower())
        )

        if link_lines != sorted_links:
            for idx, new_line in zip(link_indices, sorted_links):
                lines[idx] = new_line
            sorted_count += 1

    return "\n".join(lines), sorted_count
