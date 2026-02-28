"""Read Research/Library notes to understand content for linking."""
import sys
sys.path.insert(0, ".github/skills/obsidian/scripts")
from obsidian import Obsidian

ob = Obsidian()

notes = [
    "Research/Library/ai-second-brain-obsidian-claude-code.md",
    "Research/Library/skillsbench-benchmarking-agent-skills.md",
    "Research/Library/complete-guide-building-skills-for-claude.md",
    "Research/Library/agent-skills-vscode-docs.md",
    "Research/Library/rag-pipeline-explained.md",
    "Research/Library/vscode-agent-hooks.md",
    "Research/Library/vscode-custom-agents.md",
    "Research/Library/custom-instructions-vscode-docs.md",
    "Research/Library/best-practices-claude-code.md",
    "Research/Library/every-saas-is-now-an-api.md",
    "Research/Library/delete-your-agents-md-vs-add-evals.md",
]

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
