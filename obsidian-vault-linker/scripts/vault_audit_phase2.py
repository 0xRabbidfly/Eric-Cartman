"""Vault Link Audit — Phase 2+3: Cross-reference clusters with orphans and find link opportunities."""

import json
import sys
sys.path.insert(0, ".github/skills/obsidian/scripts")
from obsidian import Obsidian

ob = Obsidian()

# --- Get orphan set ---
orphan_lines = ob.orphans().lines()
orphan_set = set(orphan_lines)

# --- Get Research/Library notes and check linking ---
print("=" * 60)
print("RESEARCH LIBRARY NOTES — Link Map")
print("=" * 60)

r = ob.files(folder="Research/Library", ext="md")
library_notes = r.lines()
print(f"\nTotal Research/Library notes: {len(library_notes)}")
orphaned_lib = [n for n in library_notes if n in orphan_set]
print(f"Orphaned Research/Library notes: {len(orphaned_lib)}")
for n in orphaned_lib[:20]:
    print(f"  🏝️ {n}")
if len(orphaned_lib) > 20:
    print(f"  ... +{len(orphaned_lib) - 20} more")

# --- Check backlinks for key AI notes ---
print("\n" + "=" * 60)
print("BACKLINK ANALYSIS — Key AI/Agent Notes")
print("=" * 60)

key_notes = [
    "Research/Library/ai-second-brain-obsidian-claude-code.md",
    "Research/Library/skillsbench-benchmarking-agent-skills.md",
    "Research/Library/delete-your-agents-md-vs-add-evals.md",
    "Research/Library/complete-guide-building-skills-for-claude.md",
    "Research/Library/agent-skills-vscode-docs.md",
    "Research/Library/rag-pipeline-explained.md",
    "Research/Library/vscode-agent-hooks.md",
    "Research/Library/vscode-custom-agents.md",
    "Research/Library/custom-instructions-vscode-docs.md",
    "Research/Library/best-practices-claude-code.md",
    "Research/Library/every-saas-is-now-an-api.md",
]

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

from collections import Counter
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

cx_set = set(cx_results) if isinstance(cx_results[0], str) else set(r.get("path", "") for r in cx_results)
st_set = set(st_results) if isinstance(st_results[0], str) else set(r.get("path", "") for r in st_results)

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
