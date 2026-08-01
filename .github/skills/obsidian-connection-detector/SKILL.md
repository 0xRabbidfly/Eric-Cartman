---
name: obsidian-connection-detector
description: >
  Detect and classify relationships between vault notes. Use when a new note is created,
  or to scan for connections across the corpus. Triggers: "find connections",
  "what relates to X", or auto-called by other skills after note creation.
version: 1.0.0
---

# Obsidian Connection Detector

Detects and classifies relationships between Obsidian vault notes using AI-powered analysis.

## What it does

1. Takes a note path (or scans recent notes)
2. Extracts key claims/theses from the note
3. Searches the vault for related notes (by tags, keywords, concepts)
4. Classifies each relationship as: **supports**, **contradicts**, **extends**, or **bridges**
5. Writes connection entries to a tracker file (`Research/connections.json`)
6. Optionally adds a `## Connections` section to the source note with classified links

## Usage

```bash
# Detect connections for a specific note
python scripts/detect.py --note "Research/Library/01.../some-note.md"

# Scan the 5 most recently modified Library notes
python scripts/detect.py --scan-recent 5

# Full corpus scan (expensive — calls xAI API for every candidate pair)
python scripts/detect.py --scan-all
```

## Configuration

- Vault path: `C:\Users\nuno_\Documents\Obsidian Vault`
- xAI API key: loaded from env var `XAI_API_KEY` or `~/.config/last30days/.env`
- Model: `grok-4.5`
- Output: `Research/connections.json` inside the vault

## Integration

This skill feeds data into **obsidian-thesis-tracker**, which clusters connections
into emerging theses and can auto-generate reports.

## Step N: Reflection (composable)

Invoke the `skill-reflection` skill with the following context:

- **Calling skill**: `obsidian-connection-detector`
- **SKILL.md path**: `.github/skills/obsidian-connection-detector/SKILL.md`
- **Steps completed**: list each step with pass/fail/skipped
- **Friction notes**: any workarounds, retries, unexpected errors, or manual interventions

The reflection skill will analyze the run and produce improvement recommendations.
