"""
Tag rename script for Obsidian vault.
Handles frontmatter `tags:` lists and inline `#tag` mentions.
Dry-run mode prints what would change; --apply actually writes.

Safe to re-run: idempotent if same rename map.
"""
import os, re, sys, json, argparse
from collections import Counter, defaultdict
from datetime import datetime

# Rename map: source tag -> target tag
RENAME_MAP = {
    # === AGENTS family: synonyms -> agents ===
    "ai-agents": "agents",
    "AIagents": "agents",
    "agentic-ai": "agents",
    "agentic-systems": "agents",
    "agentic": "agents",
    "llm-agents": "agents",
    "agent-mode": "agents",

    # === AGENTS family: sub-concepts -> agents/<child> ===
    "agent-harnesses": "agents/harnesses",
    "agent-memory": "agents/memory",
    "agent-frameworks": "agents/frameworks",
    "multi-agent": "agents/multi",
    "multi-agent-systems": "agents/multi",
    "multi-agent-architecture": "agents/multi",
    "agent-skills": "agents/skills",
    "agent-reliability": "agents/reliability",
    "agent-security": "agents/security",
    "coding-agents": "agents/coding",
    "code-agents": "agents/coding",
    "agent-teams": "agents/teams",
    "agentic-design": "agents/design",
    "cli-agents": "agents/cli",
    "cloud-agents": "agents/cloud",
    "agentops": "agents/ops",
    "managed-agents": "agents/managed",
    "meta-agent": "agents/meta",
    "agent-economy": "agents/economy",
    "agent-tooling": "agents/tooling",
    "custom-agents": "agents/custom",
    "agents-md": "agents/md",
    "agent-md": "agents/md",

    # === SKILLS family ===
    "skill-md": "skills/md",
    "skill-system": "skills/system",
    "skills-framework": "skills/framework",

    # === CLAUDE family ===
    "claude-md": "claude-code/md",

    # === SDLC family ===
    "spec-driven-development": "sdd",
    "ai-sdlc": "sdlc",

    # === KNOWLEDGE / RAG / MEMORY ===
    "ai-second-brain": "second-brain",
    "retrieval-augmented-generation": "rag",

    # === WORKFLOW / ENGINEERING ===
    "SoftwareEngineering": "software-engineering",
    "developer-workflow": "workflow-design",

    # === EVALS ===
    "benchmarks": "benchmarking",
    "custom-benchmarks": "benchmarking",
    "eval-loops": "evals",
    "ai-evaluation": "evals",

    # === RESEARCH family (added 2026-05-30) ===
    "ai-research": "research",
    "autoResearch": "autoresearch",
}

# Tags to leave alone but worth flagging for manual review
MANUAL_REVIEW = {
    "claude": "Could be Claude model OR Claude Code — needs per-note check",
    "memory-architecture": "Could be agents/memory or knowledge concept — review",
    "the-pragmatic-engineer": "Source tag, not a topic — consider deleting",
    "copilot-instructions": "Consider copilot/instructions (judgment call)",
    "copilot-instructions-md": "Consider copilot/instructions-md (judgment call)",
}

# Tags identified as junk in the plan
JUNK_TAGS = {"bbb", "bad", "bad-noted", "aac", "eef6e8", "eef4fb", "f2f2f2"}


def rewrite_inline_tags(text, rename_map):
    """Replace #FROM with #TO in inline text. Careful with tag boundaries."""
    changes = 0
    # Sort by length descending so longer tags match first
    for src in sorted(rename_map.keys(), key=len, reverse=True):
        tgt = rename_map[src]
        # Match #src not followed by word char, / or -
        pattern = r'(?<![A-Za-z0-9_/\-])#' + re.escape(src) + r'(?![A-Za-z0-9_/\-])'
        def sub(m):
            nonlocal changes
            changes += 1
            return '#' + tgt
        text = re.sub(pattern, sub, text)
    return text, changes


def rewrite_frontmatter_tags(fm_text, rename_map):
    """Rewrite tag entries inside YAML frontmatter. Returns (new_text, change_count)."""
    changes = 0
    new_lines = []
    in_tags_block = False
    tags_indent = None
    collected_tags = []
    inline_tags_pattern = re.compile(r'^(tags:\s*)\[(.*?)\]\s*$')

    lines = fm_text.split('\n')
    i = 0
    out_lines = []
    while i < len(lines):
        line = lines[i]
        m_inline = inline_tags_pattern.match(line)
        if m_inline:
            # tags: [a, b, c] form
            prefix, body = m_inline.group(1), m_inline.group(2)
            items = [t.strip().strip('"').strip("'") for t in body.split(',') if t.strip()]
            new_items = []
            for t in items:
                if t in rename_map:
                    changes += 1
                    t = rename_map[t]
                if t not in new_items:
                    new_items.append(t)
            out_lines.append(f"{prefix}[{', '.join(new_items)}]")
            i += 1
            continue
        if re.match(r'^tags\s*:\s*$', line):
            # tags: block, expect indented list items below
            out_lines.append(line)
            i += 1
            block_lines = []
            while i < len(lines):
                next_line = lines[i]
                m = re.match(r'^(\s+)-\s+(.+?)\s*$', next_line)
                if m:
                    indent = m.group(1)
                    raw = m.group(2).strip().strip('"').strip("'").lstrip('#')
                    block_lines.append((indent, raw))
                    i += 1
                else:
                    break
            # rewrite tags, dedup
            seen = []
            for indent, raw in block_lines:
                if raw in rename_map:
                    changes += 1
                    raw = rename_map[raw]
                if raw not in seen:
                    seen.append(raw)
                    out_lines.append(f"{indent}- {raw}")
            continue
        # tags: a b c (space separated single line)
        m_sp = re.match(r'^(tags\s*:\s*)(.+)$', line)
        if m_sp and not re.search(r'[\[\{]', m_sp.group(2)):
            prefix, body = m_sp.group(1), m_sp.group(2).strip()
            # only handle if no quotes / brackets
            if body and not body.startswith('-'):
                items = re.split(r'[,\s]+', body)
                items = [t.strip().strip('"').strip("'").lstrip('#') for t in items if t.strip()]
                new_items = []
                for t in items:
                    if t in rename_map:
                        changes += 1
                        t = rename_map[t]
                    if t not in new_items:
                        new_items.append(t)
                out_lines.append(f"{prefix}{' '.join(new_items)}")
                i += 1
                continue
        out_lines.append(line)
        i += 1
    return '\n'.join(out_lines), changes


def process_file(path, rename_map, apply_changes):
    with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
        text = fh.read()
    original = text
    fm_changes = 0
    inline_changes = 0
    # split frontmatter and body
    if text.startswith('---\n') or text.startswith('---\r\n'):
        end = text.find('\n---', 4)
        if end != -1:
            fm = text[4:end]
            body = text[end+4:]
            new_fm, fm_changes = rewrite_frontmatter_tags(fm, rename_map)
            new_body, inline_changes = rewrite_inline_tags(body, rename_map)
            text = '---\n' + new_fm + '\n---' + new_body
        else:
            text, inline_changes = rewrite_inline_tags(text, rename_map)
    else:
        text, inline_changes = rewrite_inline_tags(text, rename_map)
    total = fm_changes + inline_changes
    if total > 0 and apply_changes and text != original:
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(text)
    return fm_changes, inline_changes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('vault')
    ap.add_argument('--apply', action='store_true', help='Actually write changes')
    args = ap.parse_args()

    files_changed = 0
    files_scanned = 0
    total_fm = 0
    total_inline = 0
    per_tag = Counter()

    # We'll do a separate pass to count per-tag (re-use the regex)
    # Just call process_file twice if needed — but for speed do in-line counting
    for root, dirs, files in os.walk(args.vault):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            if not f.endswith('.md'):
                continue
            path = os.path.join(root, f)
            files_scanned += 1
            fm, il = process_file(path, RENAME_MAP, args.apply)
            if fm + il > 0:
                files_changed += 1
            total_fm += fm
            total_inline += il

    print(f"Files scanned:  {files_scanned}")
    print(f"Files changed:  {files_changed}")
    print(f"Frontmatter tag changes: {total_fm}")
    print(f"Inline tag changes:      {total_inline}")
    print(f"Total renames:           {total_fm + total_inline}")
    print(f"Mode: {'APPLY (wrote files)' if args.apply else 'DRY RUN (no writes)'}")

if __name__ == '__main__':
    main()
