---
name: obsidian-vault-lint-cowork
description: Cowork-native fork of obsidian-vault-lint. Same 5-phase weekly maintenance pipeline (broken-link cleanup, MOC coverage, alphabetical sort, xAI-assisted connection discovery, Topic-MOC proposals) but runs without the Obsidian CLI dependency. Pure-Python over the vault's markdown filesystem — safe to invoke from a Cowork scheduled task in the Linux sandbox. Schedule weekly for a self-maintaining knowledge base.
argument-hint: "--dry-run | --phase N | --phase 3 --apply | --verbose"
user-invocable: true
disable-model-invocation: false
metadata:
  author: 0xrabbidfly
  version: "1.0.0-cowork"
  forked-from: obsidian-vault-lint v1.1.0
---

# obsidian-vault-lint-cowork

Cowork-native fork of `obsidian-vault-lint`. Same five phases, same logic, same output files — but no dependency on the Windows Obsidian binary, so it can run end-to-end inside a Cowork scheduled task.

## Why a fork

The original skill calls `obsidian.com` (Obsidian's Windows CLI) for every vault read/write/graph query. That works great under Windows Task Scheduler but cannot run in Cowork's Linux sandbox because the binary is a Windows `.exe`. This fork replaces the CLI with direct filesystem operations against the vault's `.md` files — same observable behavior, zero external binary dependencies (other than Python and optionally `git`).

## What runs in the Cowork sandbox

- Phase 1 — Inventory (read-only): orphan detection via wikilink graph walk, broken-link scan, dead-end detection, MOC coverage check, stale-Recently-Added detection, similar-tag detection
- Phase 2 — Autonomous fixes: prune stale, add missing-to-MOC, alphabetical sort, demote broken `[[wikilinks]]` to plain text
- Phase 3 — Connection discovery: xAI API call for orphaned Library notes (requires `XAI_API_KEY` env var; `keyring` not used in sandbox)
- Phase 4 — MOC reorganization: dead-entry removal, intra-section dedup, Topic-MOC proposals for sections >12 entries
- Phase 5 — Report at `Research/Logs/vault-lint-YYYY-MM-DD.md`, then `git add -A && git commit` if a `.git` is present and `git` is on PATH

## Configuration

| Env var | Default | Purpose |
|---------|---------|---------|
| `VAULT_PATH` | auto-discovered | Absolute path to the vault root. Auto-discovery checks: Windows `C:/Users/nuno_/Documents/Obsidian Vault`, then Linux sandbox mount `/sessions/*/mnt/Documents/Obsidian Vault` |
| `XAI_API_KEY` | unset | xAI key for Phase 3. If unset, Phase 3 is skipped with a warning |
| `XAI_MODEL` | `grok-3` | Model for connection scoring |

## CLI usage

```bash
# From the vault root (or anywhere — VAULT_PATH env var or auto-discovery handles it):
python .github/skills/obsidian-vault-lint-cowork/scripts/lint.py
python .github/skills/obsidian-vault-lint-cowork/scripts/lint.py --dry-run
python .github/skills/obsidian-vault-lint-cowork/scripts/lint.py --phase 1
python .github/skills/obsidian-vault-lint-cowork/scripts/lint.py --phase 3 --apply
python .github/skills/obsidian-vault-lint-cowork/scripts/lint.py --verbose
```

## Scheduling via Cowork

This fork is designed to be triggered by a Cowork scheduled task. The task's prompt should:

1. Ensure `C:\Users\nuno_\Documents` is connected (`request_cowork_directory` if needed)
2. Ensure `Z:\Projects` is connected (so the script files are reachable)
3. Run the script via bash, reading the resulting report file
4. Post a summary in chat

A working scheduled-task setup ships with this fork; see the chat history when the fork was created, or the `Scheduled` sidebar entry `obsidian-vault-weekly-lint`.

## Vault constants

```python
MASTER_MOC_PATH = "Research/Library/00 MOC/\U0001f5fa️ MOC - Research Library.md"
LIBRARY_FOLDER  = "Research/Library"
MOC_FOLDER      = "Research/Library/00 MOC"
LOG_FOLDER      = "Research/Logs"
```

## Files

```
.github/skills/obsidian-vault-lint-cowork/
├── SKILL.md           — this file
└── scripts/
    ├── __init__.py    — package marker
    ├── obsidian.py    — pure-Python vault adapter (Cowork-native replacement for the Obsidian CLI wrapper)
    ├── lint.py        — main entry point (orchestrator)
    ├── inventory.py   — Phase 1: read-only vault health scan
    ├── fixes.py       — Phase 2: autonomous safe writes
    ├── connections.py — Phase 3: xAI-assisted link discovery
    └── moc.py         — Phase 4: MOC dead-entry cleanup + proposals
```

## Differences from the original

- No subprocess to `obsidian.com`. All vault operations are `pathlib` + `re`.
- `orphans()` / `unresolved` / `deadends` are computed from a wikilink graph built in memory by scanning all `.md` files once per run.
- Tag detection parses `#tag-name` patterns from note content (excludes fenced code blocks).
- Git commit uses `git` from PATH, not the hardcoded Windows path.
- `keyring` is optional. If unavailable, Phase 3 reads `XAI_API_KEY` from env only.
- Default vault path auto-discovers between Windows and Linux-sandbox locations.

The phase logic itself — what counts as a stale entry, how MOC sections are sorted, how the xAI prompt is composed — is unchanged.
