---
name: obsidian-thesis-tracker
description: >
  Track emerging theses across vault notes and auto-generate draft reports when evidence
  accumulates. Use when checking thesis status, or auto-triggered by weekly lint.
  Triggers: "what theses are forming", "thesis status", "check for emerging patterns".
version: 1.0.0
---

# Obsidian Thesis Tracker

Tracks emerging theses across vault notes by analyzing connection clusters and
auto-generates draft reports when evidence accumulates.

## What it does

1. Reads `Research/connections.json` (from connection-detector)
2. Groups connections by theme/cluster (notes that are densely interconnected)
3. Identifies emerging theses — clusters with 5+ supporting connections
4. Checks for unresolved contradictions (2+ contradicting connections with no resolution)
5. When a thesis crosses the threshold, generates a draft report using obsidian-vault-report
6. Maintains `Research/theses.json` tracking active theses and their evidence

## Usage

```bash
# Analyze connections and update theses
python scripts/tracker.py

# Print current thesis status
python scripts/tracker.py --status

# Auto-generate reports for mature theses
python scripts/tracker.py --auto-report
```

## Configuration

- Vault path: `C:\Users\nuno_\Documents\Obsidian Vault`
- xAI API key: loaded from env var `XAI_API_KEY` or `~/.config/last30days/.env`
- Model: `grok-4.3`
- Input: `Research/connections.json` (from obsidian-connection-detector)
- Output: `Research/theses.json`

## Integration

- **obsidian-connection-detector** feeds data in via `connections.json`
- Tracker can trigger **obsidian-vault-report** for auto-synthesis
- Weekly lint can call `tracker.py --status` to include thesis status in the report
