"""Vault Link Audit — Phase 2+3: Cross-reference clusters with orphans and find link opportunities."""

import json
import sys
from pathlib import PurePosixPath
from collections import Counter

sys.path.insert(0, ".github/skills/obsidian/scripts")
from obsidian import Obsidian

MASTER_MOC_PATH = "Research/Library/00 MOC/🗺️ MOC - Research Library.md"
TOPIC_MOC_PATHS = {
    "AI Agent Development": "Research/Library/00 MOC/🤖 MOC - AI Agent Development.md",
}
KEY_NOTE_SLUGS = [
    "ai-second-brain-obsidian-claude-code",
    "skillsbench-benchmarking-agent-skills",
    "delete-your-agents-md-vs-add-evals",
    "complete-guide-building-skills-for-claude",
    "agent-skills-vscode-docs",
    "rag-pipeline-explained",
    "vscode-agent-hooks",
    "vscode-custom-agents",
    "custom-instructions-vscode-docs",
    "best-practices-claude-code",
    "every-saas-is-now-an-api",
]

ob = Obsidian()


def extract_wikilink_targets(content: str):
    targets = set()
    for raw_line in content.splitlines():
        for chunk in raw_line.split("[["):
            if "]]" not in chunk:
                continue
            target = chunk.split("]]", 1)[0].split("|", 1)[0].strip()
            if target:
                targets.add(target)
    return targets

# --- Get orphan set ---
orphan_lines = ob.orphans().lines()
orphan_set = set(orphan_lines)

# --- Get Research/Library notes and check linking ---
print("=" * 60)
print("RESEARCH LIBRARY NOTES — Link Map")
print("=" * 60)

r = ob.files(folder="Research/Library", ext="md")
library_notes = r.lines()
library_content_notes = [n for n in library_notes if not n.startswith("Research/Library/00 MOC/")]
print(f"\nTotal Research/Library notes: {len(library_notes)}")
print(f"Content notes (excluding MOC): {len(library_content_notes)}")
orphaned_lib = [n for n in library_content_notes if n in orphan_set]
print(f"Orphaned Research/Library content notes: {len(orphaned_lib)}")
for n in orphaned_lib[:20]:
    print(f"  🏝️ {n}")
if len(orphaned_lib) > 20:
    print(f"  ... +{len(orphaned_lib) - 20} more")

content_slugs = {PurePosixPath(path).stem: path for path in library_content_notes}

print("\n" + "=" * 60)
print("MASTER MOC COVERAGE — Research Library")
print("=" * 60)

master_moc_content = ob.read(path=MASTER_MOC_PATH)
master_moc_links = extract_wikilink_targets(master_moc_content)
master_linked_content = [path for slug, path in content_slugs.items() if slug in master_moc_links]
master_unlinked_content = [path for slug, path in content_slugs.items() if slug not in master_moc_links]

print(f"Master MOC path: {MASTER_MOC_PATH}")
print(f"Library notes linked from master MOC: {len(master_linked_content)}/{len(library_content_notes)}")
for path in sorted(master_unlinked_content)[:15]:
    print(f"  ➕ Missing from master MOC: {path}")
if len(master_unlinked_content) > 15:
    print(f"  ... +{len(master_unlinked_content) - 15} more")

print("\n" + "=" * 60)
print("TOPIC MOC COVERAGE — Scoped Maps")
print("=" * 60)

for moc_name, moc_path in TOPIC_MOC_PATHS.items():
    topic_content = ob.read(path=moc_path)
    topic_links = extract_wikilink_targets(topic_content)
    topic_linked_content = [path for slug, path in content_slugs.items() if slug in topic_links]
    folder_counts = Counter(PurePosixPath(path).parts[2] for path in topic_linked_content if len(PurePosixPath(path).parts) > 2)

    print(f"{moc_name}: {moc_path}")
    print(f"  Referenced library notes: {len(topic_linked_content)}")
    print("  Scoped topic MOCs are not expected to cover the entire library.")
    for folder_name, count in folder_counts.most_common():
        print(f"    {count:2d}  {folder_name}")

# --- Check backlinks for key AI notes ---
print("\n" + "=" * 60)
print("BACKLINK ANALYSIS — Key AI/Agent Notes")
print("=" * 60)

slug_to_path = {PurePosixPath(path).stem: path for path in library_content_notes}
key_notes = [slug_to_path[slug] for slug in KEY_NOTE_SLUGS if slug in slug_to_path]

for note_path in key_notes:
    bl = ob.backlinks(path=note_path, total=True)
    out_links = ob.links(path=note_path, total=True)
    is_orphan = "🏝️" if note_path in orphan_set else "✅"
    name = note_path.split("/")[-1].replace(".md", "")
    print(f"  {is_orphan} {name}: backlinks={bl.text}, outgoing={out_links.text}")

# --- Orphan analysis by folder ---
print("\n" + "=" * 60)
print("ORPHAN DISTRIBUTION BY TOP-LEVEL FOLDER")
print("=" * 60)

folder_counts = Counter()
for o in orphan_lines:
    parts = o.split("/")
    if len(parts) >= 2:
        folder_counts[parts[0] + "/" + parts[1]] += 1
    else:
        folder_counts["(root)"] += 1

for folder, count in folder_counts.most_common(20):
    print(f"  {count:4d}  {folder}")

# --- Dead-end analysis for Research notes ---
print("\n" + "=" * 60)
print("DEAD-END RESEARCH NOTES (no outgoing links)")
print("=" * 60)

deadend_lines = ob.deadends().lines()
deadend_set = set(deadend_lines)
deadend_research = [n for n in deadend_lines if n.startswith("Research/")]
print(f"Total dead-ends in Research/: {len(deadend_research)}")
for n in deadend_research[:25]:
    print(f"  🔚 {n}")
if len(deadend_research) > 25:
    print(f"  ... +{len(deadend_research) - 25} more")

# --- Complexity + Systems Thinking cluster overlap ---
print("\n" + "=" * 60)
print("CLUSTER OVERLAP: Complexity ∩ Systems Thinking")
print("=" * 60)

cx_results = json.loads(ob.search("complexity", format="json").text)
st_results = json.loads(ob.search("systems thinking", format="json").text)

cx_set = set(cx_results) if cx_results and isinstance(cx_results[0], str) else set(r.get("path", "") for r in cx_results)
st_set = set(st_results) if st_results and isinstance(st_results[0], str) else set(r.get("path", "") for r in st_results)

overlap = cx_set & st_set
cx_only = cx_set - st_set
st_only = st_set - cx_set

print(f"  Both: {len(overlap)} notes")
print(f"  Complexity only: {len(cx_only)} notes")
print(f"  Systems Thinking only: {len(st_only)} notes")

# Notes in both that are orphans
overlap_orphans = [n for n in overlap if n in orphan_set]
print(f"  Overlap + orphaned: {len(overlap_orphans)} notes")
for n in sorted(overlap_orphans)[:10]:
    print(f"    🏝️ {n}")
