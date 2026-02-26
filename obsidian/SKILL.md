---
name: obsidian
description: Composable Obsidian vault operations via CLI. Use when ANY task needs to read, write, search, tag, or query the Obsidian vault. This is the ONLY correct way to interact with the vault. Provides typed wrappers around the Obsidian CLI (v1.12+). Requires Obsidian to be running. Use when user says "save to vault", "obsidian", "research note", "daily note", "tag", "summarize and save", or any vault operation.
argument-hint: search query, create note, daily append, tags
user-invokable: true
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
> Do NOT route vault writes through other skills (e.g. daily-research, session-log).
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
❌  import from daily-research/scripts  # never route through other skills
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

## Composing with Other Skills

### From daily-research
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

## Dependencies

- Python 3.10+ (stdlib only — subprocess + json)
- Obsidian running with CLI enabled
- No pip dependencies
````
