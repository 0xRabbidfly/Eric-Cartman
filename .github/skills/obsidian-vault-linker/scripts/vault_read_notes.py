"""Read current Research/Library notes to understand content for linking."""
import sys
from pathlib import PurePosixPath

sys.path.insert(0, ".github/skills/obsidian/scripts")
from obsidian import Obsidian

MOC_PATH = "Research/Library/00 MOC/🤖 MOC - AI Agent Development.md"
TARGET_SLUGS = {
    "ai-second-brain-obsidian-claude-code",
    "skillsbench-benchmarking-agent-skills",
    "complete-guide-building-skills-for-claude",
    "agent-skills-vscode-docs",
    "rag-pipeline-explained",
    "vscode-agent-hooks",
    "vscode-custom-agents",
    "custom-instructions-vscode-docs",
    "best-practices-claude-code",
    "every-saas-is-now-an-api",
    "delete-your-agents-md-vs-add-evals",
}

ob = Obsidian()

library_paths = [
    line for line in ob.files(folder="Research/Library", ext="md").lines()
    if not line.startswith("Research/Library/00 MOC/")
]

notes = []
slug_to_path = {
    PurePosixPath(path).stem: path
    for path in library_paths
}

for slug in sorted(TARGET_SLUGS):
    path = slug_to_path.get(slug)
    if path:
        notes.append(path)

notes.insert(0, MOC_PATH)

for note in notes:
    content = ob.read(path=note)
    lines = content.split("\n")
    name = note.rsplit("/", 1)[-1]
    title_line = lines[0] if lines else "(empty)"
    
    # Extract tags
    tags = []
    for l in lines[:30]:
        if l.strip().startswith("- #") or l.strip().startswith("#") and not l.startswith("# "):
            if "tags" not in l.lower():
                tags.append(l.strip())
    
    # First heading
    heading = ""
    in_frontmatter = False
    for l in lines:
        if l.strip() == "---":
            in_frontmatter = not in_frontmatter
            continue
        if not in_frontmatter and (l.startswith("# ") or l.startswith("## ")):
            heading = l.strip()
            break
    
    print(f"--- {name} ---")
    print(f"  Title/H1: {heading or title_line}")
    if tags:
        print(f"  Tags: {', '.join(tags[:8])}")
    # Summary: first non-empty, non-frontmatter paragraph
    in_fm = False
    for l in lines:
        if l.strip() == "---":
            in_fm = not in_fm
            continue
        if not in_fm and l.strip() and not l.startswith("#"):
            summary = l.strip()[:150]
            print(f"  Summary: {summary}")
            break
    print()
