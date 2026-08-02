"""Phase 3 — Taxonomy Repair: keeps library tags and folder placement canonical.

  - Reads the master MOC's canonical tag guidance
  - Compares each library note's tags and folder placement
  - Auto-applies tag normalization (case fixes, synonym merges)
  - Proposes folder moves and flags orphaned tags for human review

Emergent topic detection is NOT done here — obsidian-weekly-brain (trend
momentum + cross-domain bridges) and obsidian-thesis-tracker own that.
"""
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

_SCRIPT_DIR = Path(__file__).parent.resolve()
_SKILLS_ROOT = _SCRIPT_DIR.parent.parent
sys.path.insert(0, str(_SCRIPT_DIR))
sys.path.insert(0, str(_SKILLS_ROOT / "obsidian" / "scripts"))
from obsidian import Obsidian
from inventory import MASTER_MOC_PATH, LIBRARY_FOLDER


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TAG_SIMILARITY_THRESHOLD = 0.8

# Folder-to-tag routing table: canonical tags that map to each library bucket.
# This is the fallback; the live MOC's Canonical Tag Guidance takes precedence.
FOLDER_TAG_ROUTING = {
    "01": {"agents", "ai-agents", "agent-harnesses", "orchestration", "architecture"},
    "02": {"skills", "claude-code", "copilot", "mcp", "ides", "tooling", "hooks"},
    "03": {"evals", "reliability", "governance", "testing", "review", "controls"},
    "04": {"sdlc", "workflow-design", "strategy", "consulting"},
    "05": {"rag", "retrieval", "knowledge", "obsidian", "memory", "second-brain"},
    "06": {"cryptography", "post-quantum", "blockchain", "zero-knowledge"},
    "07": {"space", "megatrends", "futures", "off-world"},
    "08": {"org-design", "ai-transformation", "management"},
}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TaxonomyResult:
    """Results from taxonomy repair analysis."""
    tag_fixes_applied: int = 0
    tag_fix_details: list = field(default_factory=list)       # [{note_path, old_tag, new_tag}]
    folder_move_proposals: list = field(default_factory=list)  # [{note_path, current_folder, suggested_folder, reason}]
    orphaned_tags: list = field(default_factory=list)          # [{note_path, tag}]
    missing_crosslinks: list = field(default_factory=list)     # [{note_path, suggested_link, reason}]

    # Summary
    changes: list = field(default_factory=list)                # [{type, detail}]



# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_taxonomy_repair(
    similar_tags: list,
    dry_run: bool = False,
    verbose: bool = False,
) -> TaxonomyResult:
    """Run taxonomy repair over every library note.

    Args:
        similar_tags: List of similar tag pairs from Phase 1 inventory
                      (each item: {t1, t2, ratio}).
        dry_run: If True, report what would change without writing.
        verbose: If True, print per-item detail.

    Returns:
        TaxonomyResult with all findings and applied changes.
    """
    ob = Obsidian()
    result = TaxonomyResult()

    # Read master MOC for the canonical tag list
    moc_content = ob.read(path=MASTER_MOC_PATH)
    canonical_tags = _extract_canonical_tags(moc_content)

    if verbose:
        print(f"[taxonomy] Canonical tags from MOC: {len(canonical_tags)}")

    # Read all library notes' frontmatter
    library_notes = ob.files(folder=LIBRARY_FOLDER, ext="md").lines()
    content_notes = [n for n in library_notes if "/00 MOC/" not in n]

    if verbose:
        print(f"[taxonomy] Library notes to analyze: {len(content_notes)}")

    _taxonomy_drift_repair(
        ob, result, content_notes, canonical_tags,
        similar_tags, dry_run, verbose,
    )

    return result



# ---------------------------------------------------------------------------
# MOC parsing helper
# ---------------------------------------------------------------------------

def _extract_canonical_tags(moc_content: str) -> Set[str]:
    """Extract canonical tags from the MOC's 'Canonical Tag Guidance' section.

    Looks for tags in backtick-quoted format like `agents`, `rag`, `evals`.
    Falls back to an empty set if the section is not found.
    """
    canonical = set()
    in_tag_section = False

    for line in moc_content.splitlines():
        if re.match(r"^#+\s+Canonical Tag Guidance", line, re.IGNORECASE):
            in_tag_section = True
            continue
        if in_tag_section and re.match(r"^#+\s+", line):
            break
        if in_tag_section:
            # Match backtick-quoted tags: `tag-name`
            for m in re.finditer(r"`([a-z][a-z0-9-]*)`", line):
                canonical.add(m.group(1))

    return canonical


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_TAGS_RE = re.compile(r"^tags:\s*\[([^\]]*)\]", re.MULTILINE)
_TAGS_LIST_RE = re.compile(r"^tags:\s*$", re.MULTILINE)


def _parse_frontmatter_tags(content: str) -> List[str]:
    """Extract tags from YAML frontmatter.

    Handles both inline format: tags: [tag1, tag2]
    and list format:
        tags:
          - tag1
          - tag2
    """
    fm_match = _FRONTMATTER_RE.match(content)
    if not fm_match:
        return []

    fm = fm_match.group(1)

    # Try inline format first: tags: [tag1, tag2, tag3]
    inline = _TAGS_RE.search(fm)
    if inline:
        raw = inline.group(1)
        return [t.strip().strip("'\"") for t in raw.split(",") if t.strip()]

    # Try list format: tags:\n  - tag1\n  - tag2
    list_match = _TAGS_LIST_RE.search(fm)
    if list_match:
        tags = []
        start = list_match.end()
        for line in fm[start:].splitlines():
            stripped = line.strip()
            if stripped.startswith("- "):
                tags.append(stripped[2:].strip().strip("'\""))
            elif stripped and not stripped.startswith("#"):
                break
        return tags

    return []


def _get_note_folder_number(note_path: str) -> Optional[str]:
    """Extract the folder number (e.g. '01', '05') from a library note path.

    Example: 'Research/Library/05 Knowledge, RAG & Memory/note.md' -> '05'
    """
    parts = note_path.split("/")
    if len(parts) >= 4 and parts[:2] == ["Research", "Library"]:
        folder = parts[2]
        num = folder.split(" ", 1)[0] if " " in folder else folder[:2]
        if num.isdigit():
            return num.zfill(2)
    return None


def _suggest_folder_for_tags(tags: List[str]) -> Optional[str]:
    """Given a note's tags, suggest the best library folder number.

    Scores each folder by how many of the note's tags match that folder's
    canonical tag set. Returns the folder number with the highest score,
    or None if no match.
    """
    if not tags:
        return None

    tag_set = {t.lower() for t in tags}
    scores: Dict[str, int] = {}

    for folder_num, folder_tags in FOLDER_TAG_ROUTING.items():
        overlap = len(tag_set & folder_tags)
        if overlap > 0:
            scores[folder_num] = overlap

    if not scores:
        return None

    best = max(scores, key=scores.get)
    return best



# ---------------------------------------------------------------------------
# Taxonomy Drift Repair
# ---------------------------------------------------------------------------

def _taxonomy_drift_repair(
    ob: Obsidian,
    result: TaxonomyResult,
    content_notes: List[str],
    canonical_tags: Set[str],
    similar_tags: list,
    dry_run: bool,
    verbose: bool,
) -> None:
    """Check each library note for tag and folder drift.

    Auto-applies:
      - Tag case normalization (e.g. 'RAG' -> 'rag')
      - Synonym merges from similar_tags (e.g. 'AI-agents' -> 'ai-agents')

    Proposes (approval-gated):
      - Folder moves when tags suggest a different bucket
      - Orphaned tags not in the canonical list
    """
    # Build synonym merge map from Phase 1 similar tags
    # For each high-similarity pair where one is canonical, map the other to it
    synonym_map = _build_synonym_map(similar_tags, canonical_tags)

    if verbose and synonym_map:
        print(f"[taxonomy] Synonym merge map: {len(synonym_map)} entries")
        for old, new in list(synonym_map.items())[:5]:
            print(f"[taxonomy]   '{old}' -> '{new}'")

    for note_path in content_notes:
        try:
            content = ob.read(path=note_path)
        except Exception as e:
            if verbose:
                print(f"[taxonomy] Could not read {note_path}: {e}")
            continue

        if not content or not content.strip():
            continue

        tags = _parse_frontmatter_tags(content)
        if not tags:
            continue

        current_folder = _get_note_folder_number(note_path)
        note_modified = False
        new_content = content

        # Check each tag
        for tag in tags:
            normalized = tag.lower().strip()

            # Case normalization
            if tag != normalized:
                new_content = _replace_tag_in_frontmatter(new_content, tag, normalized)
                result.tag_fix_details.append({
                    "note_path": note_path,
                    "old_tag": tag,
                    "new_tag": normalized,
                    "reason": "case normalization",
                })
                note_modified = True

            # Synonym merge
            elif normalized in synonym_map:
                canonical = synonym_map[normalized]
                new_content = _replace_tag_in_frontmatter(new_content, tag, canonical)
                result.tag_fix_details.append({
                    "note_path": note_path,
                    "old_tag": tag,
                    "new_tag": canonical,
                    "reason": f"synonym merge (similar to '{canonical}')",
                })
                note_modified = True

            # Orphaned tag check (tag not in canonical set)
            elif canonical_tags and normalized not in canonical_tags:
                result.orphaned_tags.append({
                    "note_path": note_path,
                    "tag": normalized,
                })

        # Write tag fixes
        if note_modified:
            result.tag_fixes_applied += 1
            if not dry_run:
                try:
                    ob.create(path=note_path, content=new_content, overwrite=True)
                    if verbose:
                        print(f"[taxonomy] Fixed tags in: {note_path}")
                except Exception as e:
                    print(f"[taxonomy] ERROR writing tag fix to {note_path}: {e}", file=sys.stderr)
            elif verbose:
                print(f"[taxonomy] [DRY RUN] Would fix tags in: {note_path}")

        # Folder routing check
        final_tags = _parse_frontmatter_tags(new_content if note_modified else content)
        suggested_folder = _suggest_folder_for_tags(final_tags)

        if (
            suggested_folder
            and current_folder
            and suggested_folder != current_folder
        ):
            result.folder_move_proposals.append({
                "note_path": note_path,
                "current_folder": current_folder,
                "suggested_folder": suggested_folder,
                "tags": final_tags,
                "reason": f"Tags suggest folder {suggested_folder}, currently in {current_folder}",
            })
            if verbose:
                slug = note_path.rsplit("/", 1)[-1]
                print(f"[taxonomy] Folder drift: {slug} ({current_folder} -> {suggested_folder})")

    # Build changes summary
    if result.tag_fixes_applied > 0:
        result.changes.append({
            "type": "tag_normalization",
            "detail": f"Normalized tags in {result.tag_fixes_applied} notes "
                      f"({len(result.tag_fix_details)} individual tag fixes)",
        })

    if result.orphaned_tags:
        unique_orphans = len({t["tag"] for t in result.orphaned_tags})
        result.changes.append({
            "type": "orphaned_tags_flagged",
            "detail": f"Found {unique_orphans} unique orphaned tags across "
                      f"{len(result.orphaned_tags)} note-tag pairs",
        })

    if result.folder_move_proposals:
        result.changes.append({
            "type": "folder_move_proposals",
            "detail": f"Proposed {len(result.folder_move_proposals)} folder moves",
        })



def _build_synonym_map(similar_tags: list, canonical_tags: Set[str]) -> Dict[str, str]:
    """Build a mapping of non-canonical tags to their canonical synonyms.

    For each pair in similar_tags with ratio > TAG_SIMILARITY_THRESHOLD:
    - If one is canonical and the other is not, map non-canonical -> canonical
    - If both are canonical or neither is, skip (ambiguous merge)
    """
    synonym_map: Dict[str, str] = {}

    for pair in similar_tags:
        if pair["ratio"] < TAG_SIMILARITY_THRESHOLD:
            continue

        t1 = pair["t1"].lower().lstrip("#")
        t2 = pair["t2"].lower().lstrip("#")

        t1_canonical = t1 in canonical_tags
        t2_canonical = t2 in canonical_tags

        if t1_canonical and not t2_canonical:
            synonym_map[t2] = t1
        elif t2_canonical and not t1_canonical:
            synonym_map[t1] = t2
        # If both or neither are canonical, skip — requires human judgment

    return synonym_map


def _replace_tag_in_frontmatter(content: str, old_tag: str, new_tag: str) -> str:
    """Replace a specific tag in frontmatter YAML, preserving structure.

    Handles both inline and list tag formats.
    """
    fm_match = _FRONTMATTER_RE.match(content)
    if not fm_match:
        return content

    fm = fm_match.group(0)
    body = content[fm_match.end():]

    # Replace in inline format: tags: [old_tag, other]
    new_fm = re.sub(
        rf"(?<=[\[,\s])\s*{re.escape(old_tag)}\s*(?=[,\]])",
        new_tag,
        fm,
    )

    # Replace in list format: - old_tag
    new_fm = re.sub(
        rf"^(\s*-\s*){re.escape(old_tag)}\s*$",
        rf"\g<1>{new_tag}",
        new_fm,
        flags=re.MULTILINE,
    )

    return new_fm + body



# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def format_taxonomy_report(result: TaxonomyResult, run_date: str) -> str:
    """Format taxonomy repair results as a markdown proposals file.

    This file is written to Research/Logs/ for human review of folder moves
    and orphaned tags.
    """
    lines = [
        f"# Vault Lint — Taxonomy Repair Proposals — {run_date}",
        "",
        "> Review these proposals. Tag normalization has already been auto-applied.",
        "> Folder moves require manual approval.",
        "",
    ]

    # Folder move proposals
    if result.folder_move_proposals:
        lines += [
            f"## Folder Move Proposals ({len(result.folder_move_proposals)} notes)",
            "",
        ]
        for p in result.folder_move_proposals:
            slug = p["note_path"].rsplit("/", 1)[-1].replace(".md", "")
            lines += [
                f"### [[{slug}]]",
                f"- **Current**: folder `{p['current_folder']}`",
                f"- **Suggested**: folder `{p['suggested_folder']}`",
                f"- **Tags**: {', '.join(f'`{t}`' for t in p.get('tags', []))}",
                f"- **Reason**: {p['reason']}",
                "",
            ]

    # Orphaned tags summary
    if result.orphaned_tags:
        unique_tags = sorted({t["tag"] for t in result.orphaned_tags})
        lines += [
            f"## Orphaned Tags ({len(unique_tags)} unique tags not in canonical list)",
            "",
        ]
        tag_notes: Dict[str, List[str]] = defaultdict(list)
        for t in result.orphaned_tags:
            tag_notes[t["tag"]].append(t["note_path"])
        for tag in unique_tags[:20]:  # cap at 20 for readability
            notes = tag_notes[tag]
            note_list = ", ".join(
                f"[[{n.rsplit('/', 1)[-1].replace('.md', '')}]]" for n in notes[:3]
            )
            suffix = f" (+{len(notes) - 3} more)" if len(notes) > 3 else ""
            lines.append(f"- `{tag}` — {note_list}{suffix}")
        lines.append("")

    # Tag fixes applied (informational, already done)
    if result.tag_fix_details:
        lines += [
            f"## Tag Fixes Applied ({len(result.tag_fix_details)} fixes, already written)",
            "",
        ]
        for fix in result.tag_fix_details[:20]:
            slug = fix["note_path"].rsplit("/", 1)[-1].replace(".md", "")
            lines.append(
                f"- [[{slug}]]: `{fix['old_tag']}` -> `{fix['new_tag']}` ({fix['reason']})"
            )
        if len(result.tag_fix_details) > 20:
            lines.append(f"- ... and {len(result.tag_fix_details) - 20} more")
        lines.append("")

    return "\n".join(lines)
