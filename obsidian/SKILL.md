---
name: obsidian
description: Composable Obsidian vault operations via CLI. Use when ANY task needs to read, write, search, tag, or query the Obsidian vault. This is the ONLY correct way to interact with the vault. Provides typed wrappers around the Obsidian CLI (v1.12+). Requires Obsidian to be running. Use when user says "save to vault", "obsidian", "research note", "daily note", "tag", "summarize and save", or any vault operation.
argument-hint: search query, create note, daily append, tags
user-invokable: true
disable-model-invocation: false
---

# Obsidian Skill (Composable)

## Purpose

Thin, composable wrapper around the [Obsidian CLI](https://help.obsidian.md/cli).
Other skills import `obsidian.py` to interact with the vault instead of
reimplementing filesystem reads/writes.

**Prerequisite**: Obsidian must be running with CLI enabled
(Settings → General → Command line interface).

## CRITICAL — Usage Rules

> **This skill is the SOLE interface for all vault operations.**
> Do NOT create temporary Python scripts, helper files, or intermediary modules.
> Do NOT route vault writes through other skills (e.g. obsidian-daily-research, session-log).
> Instead, call the wrapper **directly inline** in the terminal.

### How to call (correct)

**Preferred: Pipe content via PowerShell single-quoted heredoc (`@'...'@`).**
This avoids backtick/dollar-sign escaping issues entirely.
The script is at `.github/skills/obsidian/scripts/obsidian.py`.

```powershell
# ═══ PREFERRED — Pipe via heredoc (handles backticks, $, any markdown) ═══

# Create a note — content piped from stdin
@'
---
tags: [topic-a, topic-b]
status: unread
---
# My Note Title

Body with `backticks`, $variables, and **any** markdown.
'@ | python .github/skills/obsidian/scripts/obsidian.py create --path "Research/Library/my-note.md"

# Append to existing note
@'
## New Section

More content here.
'@ | python .github/skills/obsidian/scripts/obsidian.py append --path "Research/Library/my-note.md"

# Prepend to existing note
@'
**Updated 2026-02-23**
'@ | python .github/skills/obsidian/scripts/obsidian.py prepend --file "Recipe"

# Overwrite an existing note
@'
# Replacement content
'@ | python .github/skills/obsidian/scripts/obsidian.py create --path "Research/Library/my-note.md" --overwrite

# Read a note
python .github/skills/obsidian/scripts/obsidian.py read --path "Research/Library/my-note.md"

# Vault info
python .github/skills/obsidian/scripts/obsidian.py info
```

```powershell
# ═══ SIMPLE — python -c one-liner (only for short content without special chars) ═══
python -c "import sys; sys.path.insert(0,'.github/skills/obsidian/scripts'); from obsidian import Obsidian; ob=Obsidian(); print(ob.create(path='Research/Library/my-note.md', content='# Title\n\nBody text').text)"
```

> **IMPORTANT**: Always use `@'...'@` (single-quoted heredoc), never `@"..."@`
> (double-quoted). Double-quoted heredocs still interpret backticks and `$`.

### Unicode / UTF-8

The wrapper auto-configures UTF-8 on Windows (`sys.stdin.reconfigure`),
so Unicode characters (arrows, em-dashes, etc.) survive the pipe.

If you still see encoding issues, set PowerShell's pipe encoding **once per
session** (or permanently in your `$PROFILE`):

```powershell
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

Or set the environment variable system-wide (survives reboots):

```powershell
[System.Environment]::SetEnvironmentVariable("PYTHONUTF8", "1", "User")
```

### What NOT to do

```
❌  create_file("_save_post.py", ...)   # never create temp scripts
❌  create_file("_tmp_note.py", ...)    # never create temp scripts, use pipe
❌  import from obsidian-daily-research/scripts  # never route through other skills
❌  Write content to a .md file on disk # vault writes go through CLI only
❌  Multiple tool calls for one note    # one pipe call is enough
❌  @"..."@ (double-quoted heredoc)     # still mangles backticks and $
```

## Quick Reference

```python
from obsidian import Obsidian

ob = Obsidian()                              # auto-discovers vault
ob = Obsidian(vault="My Vault")              # explicit vault

# --- Files ---
ob.read("Recipe")                            # read by name
ob.read(path="Notes/Recipe.md")              # read by path
ob.create("Trip to Paris", content="# Paris", template="Travel")
ob.append("Recipe", "## New Section")
ob.prepend("Recipe", "**Updated 2026-02-23**")
ob.move("Recipe", to="Archive/Recipe.md")
ob.rename("Recipe", name="Old Recipe")
ob.delete("Scratch Note")
ob.file_info("Recipe")                       # size, dates, path

# --- Search ---
ob.search("meeting notes")                   # vault-wide search
ob.search("TODO", path="Projects", limit=10) # scoped
ob.search_context("meeting notes")           # with line context

# --- Daily Notes ---
ob.daily()                                   # open daily note
ob.daily_read()                              # read daily note
ob.daily_append("- [ ] Buy groceries")
ob.daily_prepend("## Morning Check-in")
ob.daily_path()                              # get path even if not created

# --- Properties (frontmatter) ---
ob.property_read("status", file="Recipe")
ob.property_set("status", "published", file="Recipe")
ob.property_remove("draft", file="Recipe")
ob.properties(file="Recipe")                 # all properties

# --- Tags ---
ob.tags()                                    # all tags with counts
ob.tag_info("keep")                          # files containing tag
ob.tags_for_file("Recipe")                   # tags on specific file

# --- Links / Graph ---
ob.backlinks("Recipe")                       # incoming links
ob.links("Recipe")                           # outgoing links
ob.orphans()                                 # unlinked files
ob.unresolved()                              # broken links
ob.deadends()                                # files with no outlinks

# --- Tasks ---
ob.tasks()                                   # all tasks
ob.tasks(todo=True)                          # incomplete only
ob.tasks(daily=True)                         # today's daily note
ob.task_toggle(file="Recipe", line=8)
ob.task_done(file="Recipe", line=8)

# --- Vault / Files listing ---
ob.vault_info()                              # name, path, size
ob.files(folder="Research", ext="md")        # list files
ob.folders()                                 # list folders
ob.outline("Recipe")                         # heading tree

# --- Templates ---
ob.templates()                               # list templates
ob.template_read("Travel", resolve=True)

# --- Bookmarks ---
ob.bookmarks()
ob.bookmark(file="Recipe", title="Fav Recipe")

# --- Raw ---
ob.run("search", query="test", format="json")  # any CLI command
ob.eval("app.vault.getFiles().length")          # run JS in Obsidian
```

## Agent Memory (Composable)

### Purpose

Agents have long-term memory. When an agent discovers something worth persisting
beyond the current session, it writes to the `Agent Memories/` folder in the
Obsidian vault — **autonomously, without being asked**.

This is the agent equivalent of "writing it down so you don't forget."

### When to Trigger (Agent Self-Assessment)

After completing any significant action, the agent evaluates:

| Signal | Example | Save? |
|--------|---------|-------|
| **Non-obvious workaround discovered** | Zscaler blocks ACR push → `--insecure` flag | Yes |
| **Project-specific convention learned** | "This repo uses barrel exports for all modules" | Yes |
| **User preference observed** | User always wants vitest over jest | Yes |
| **Decision with rationale** | Chose SQLite over Postgres for local dev because… | Yes |
| **Recurring error pattern + fix** | TS2345 on this codebase always means missing generic | Yes |
| **Research insight worth keeping** | "Obsidian CLI v1.12 broke --format=json on search" | Yes |
| **Complex task completed — lessons learned** | Multi-file refactor; order mattered because… | Yes |
| **Routine, well-documented action** | Ran `npm install` successfully | No |
| **Trivial lookup** | Checked a file path | No |

**Threshold**: If the agent thinks "I'd want to know this next time," save it.

### Memory Note Format

All memories go to `Agent Memories/` with this structure:

```markdown
---
tags: [agent-memory, <category>]
source-skill: <skill-name-or-session>
captured: <YYYY-MM-DD>
confidence: high | medium | low
---
# <Concise Title>

## Context
<What was happening when this was discovered>

## Insight
<The actual thing worth remembering — specific and actionable>

## Evidence
<Command output, error message, or reasoning that supports this>
```

Categories: `workaround`, `convention`, `preference`, `decision`, `pattern`, `insight`, `lesson`

### How to Save a Memory (Inline)

```powershell
@'
---
tags: [agent-memory, workaround]
source-skill: branch-wrapup
captured: 2026-03-01
confidence: high
---
# Zscaler Blocks ACR Push on First Attempt

## Context
During branch-wrapup step 2 (ACR push), the push failed with a TLS error.

## Insight
On this network, ACR pushes require `--insecure-registry` flag due to Zscaler MITM.
Add the registry to Docker daemon.json insecure-registries list for a permanent fix.

## Evidence
`Error: x509: certificate signed by unknown authority`
Workaround: `docker push --insecure myregistry.azurecr.io/app:latest`
'@ | python .github/skills/obsidian/scripts/obsidian.py create --path "Agent Memories/zscaler-blocks-acr-push.md"
```

### Deduplication

Before creating a memory, search for existing ones on the same topic:

```powershell
python .github/skills/obsidian/scripts/obsidian.py search "<keyword>" --path "Agent Memories" --format json
```

If a matching memory exists:
- **Same insight** → skip (don't duplicate)
- **New detail on same topic** → append to existing note
- **Contradicts previous memory** → update with new evidence, bump `confidence`

### Memory Recall

At session start or when facing a tricky problem, agents should search memories:

```powershell
# Recall relevant memories before tackling a problem
python .github/skills/obsidian/scripts/obsidian.py search "<problem keywords>" --path "Agent Memories" --format json
```

---

## Friction Self-Healing (Composable)

### Purpose

When a skill hits significant friction **mid-run**, the agent doesn't just note it
for later — it triggers `skill-reflection` immediately as part of the current
ReACT loop, then applies the recommendations before continuing.

This is **self-healing**: the agent fixes the skill that's failing *while it's failing*.

### When to Trigger (Inline, Not End-of-Session)

| Friction Signal | Action |
|----------------|--------|
| A skill step fails and needs a workaround | Trigger `skill-reflection` after the workaround succeeds |
| 2+ retries on the same operation | Trigger `skill-reflection` with retry details |
| Had to deviate from documented steps | Trigger `skill-reflection` with the deviation |
| Encoding / environment / auth issue | Trigger `skill-reflection` + save Agent Memory |
| A SKILL.md instruction was wrong or ambiguous | Trigger `skill-reflection`, apply fix immediately |

### Self-Healing Workflow

```
1. Agent is running skill X, step N
2. Step N fails or requires workaround
3. Agent completes step N with workaround
4. Agent IMMEDIATELY invokes skill-reflection:
     "Run skill-reflection for <skill-X>.
      Steps completed so far: ...
      Friction: <what just happened>"
5. skill-reflection produces recommendations
6. Agent evaluates recommendations:
   - P0 (breaking) → Apply fix to SKILL.md NOW, before continuing
   - P1 (quality)  → Apply fix to SKILL.md NOW if simple, else note for later
   - P2 (nice)     → Note for end of session
7. Agent saves an Agent Memory about the friction + fix
8. Agent continues with remaining steps of skill X
```

### Example: Self-Healing During branch-wrapup

```
Running branch-wrapup, step 3 (lint) fails:
  "eslint found 2 errors in generated files that should be excluded"

Agent workaround: added generated/ to .eslintignore

Agent immediately runs:
  "Run skill-reflection for branch-wrapup.
   Steps: 1-build PASS, 2-typecheck PASS, 3-lint FAIL (workaround applied)
   Friction: ESLint flagged generated files. SKILL.md doesn't mention
   excluding generated directories from lint."

skill-reflection returns:
  R1. (P0) Add 'exclude generated/ from lint' to branch-wrapup step 3

Agent applies R1 to branch-wrapup/SKILL.md immediately.
Agent saves memory: "Generated files trigger lint errors — exclude them."
Agent continues with step 4 (test).
```

---

## Composing with Other Skills

### From obsidian-daily-research
```python
from obsidian import Obsidian
ob = Obsidian()

# Dedup via indexed search instead of regex scanning
existing = ob.search_context("some article title", format="json")

# Write daily note
ob.daily_append(formatted_content)

# Promote #keep items
ob.property_set("promoted", "true", file="2026-02-23")
```

### From session-log
```python
ob = Obsidian()
ob.create(
    f"Session {date}",
    content=session_markdown,
    path=f"Sessions/{date}.md"
)
```

### From content-research-writer
```python
ob = Obsidian()
ob.create("Agentic RAG Research", content=draft, template="Research")
ob.property_set("status", "draft", file="Agentic RAG Research")
ob.property_set("sources", "12", file="Agentic RAG Research", type="number")
```

## Setup

1. Obsidian 1.12+ with Catalyst license
2. Settings → General → Enable "Command line interface"
3. Windows: Ensure `Obsidian.com` is in the Obsidian install folder
   (usually `%LOCALAPPDATA%\Programs\obsidian\`)
4. Either add that folder to PATH, or the wrapper auto-discovers it.

**Changelog**: <https://obsidian.md/changelog/>
Check before updating the skill to catch breaking CLI changes or new features to wrap.

## Upgrading After a CLI Update

When Obsidian ships a new CLI version, run the sync audit to discover what changed:

```powershell
# 1. Coverage report — what's wrapped vs unwrapped right now
python .github/skills/obsidian/scripts/cli_sync.py

# 2. Diff against last-synced manifest — what's NEW since you last updated
python .github/skills/obsidian/scripts/cli_sync.py --diff

# 3. Generate a Markdown upgrade guide (checklist of what to add/update)
python .github/skills/obsidian/scripts/cli_sync.py --guide

# 4. After updating obsidian.py + SKILL.md, snapshot the new CLI state
python .github/skills/obsidian/scripts/cli_sync.py --save
```

### Upgrade Workflow

1. **Update Obsidian** to the new version, restart it
2. Run `--diff` to see new/removed commands and parameters since last sync
3. Run `--guide` to get a task checklist (pipe to a file if large: `--guide > upgrade.md`)
4. Update `obsidian.py` — add methods for new commands, add params to existing methods
5. Update the **Quick Reference** section in this SKILL.md
6. Update `README.md` method table if categories changed
7. Run `--save` to snapshot the new CLI state as the baseline for next time
8. Commit: `feat(obsidian): sync wrapper with CLI vX.Y.Z`

### Manifest

The file `scripts/.cli-manifest.json` tracks the last-synced CLI version and full
command inventory. It's checked into git so the diff works across sessions.

## Dependencies

- Python 3.10+ (stdlib only — subprocess + json)
- Obsidian running with CLI enabled
- No pip dependencies

## Friction Rule

> If you hit unexpected errors, encoding issues, missing CLI commands, or had to
> retry/workaround anything while using this skill:
> 1. **Immediately** invoke `skill-reflection` with the friction details (don't wait for end of session)
> 2. Apply any P0/P1 recommendations to the relevant SKILL.md right now
> 3. Save an Agent Memory about the friction and resolution
> 4. Then continue with the current task
>
> This is the self-healing loop — skills get better every time they break.
````
