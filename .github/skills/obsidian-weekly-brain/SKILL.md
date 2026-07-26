---
name: obsidian-weekly-brain
description: Weekly intelligence digest analyzing the vault corpus for trends, thesis health, blindspots, cross-domain bridges, zeitgeist, actionable insights, and predictions. Triggers: "weekly brain", "brain digest", "what did my vault learn this week".
user-invocable: true
argument-hint: "--pass trend|zeitgeist|thesis|blindspot|bridge|action|predict"
disable-model-invocation: true
metadata:
  author: 0xrabbidfly
  version: "1.0.0"
---

# Obsidian Weekly Brain

## Purpose

A weekly intelligence digest that mines the entire Obsidian vault corpus and produces a single analytical document combining 7 analysis capabilities. Designed to run every Sunday morning via scheduled task.

## What It Does

The script performs 7 analysis passes over your vault:

1. **Trend Momentum** — Rising tags, convergent discoveries across independent sources
2. **Thesis Health Check** — Supporting/contradicting evidence, thesis decay detection
3. **Blindspot Detection** — Missing subtopics, high consumption-to-synthesis ratios
4. **Cross-Domain Bridges** — Unusual tag co-occurrences that reveal insight
5. **Zeitgeist Snapshot** — Dominant tensions, what's hot, what disappeared
6. **Actionable Insights** — LEARN/BUILD/WATCH/RECONSIDER recommendations
7. **Prediction Extraction** — Forecasts from sources, resolution tracking

Output: `Research/Reports/weekly-brain-YYYY-MM-DD.md`

## Quick Start

```powershell
python .github/skills/obsidian-weekly-brain/scripts/brain.py
```


## CLI Options

```
python brain.py                    # Full weekly digest
python brain.py --pass trend       # Run only trend analysis
python brain.py --pass zeitgeist   # Run only zeitgeist
python brain.py --dry-run          # Analyze but don't write to vault
python brain.py --weeks 2          # Lookback window (default 4)
```

## Data Sources

- `Research/Library/` — All ~190 research notes
- `Research/Dailies/` — Daily research notes (last 4 weeks)
- `Podcasts/` — Podcast notes (skip transcripts/)
- `Research/connections.json` — Connection graph
- `Research/theses.json` — Thesis tracker data
- `Research/predictions.json` — Prediction tracker (created if needed)

## Requirements

- Python 3.10+
- xAI API key in `~/.config/last30days/.env` (as `XAI_API_KEY`)
- No pip dependencies (stdlib only)

## Step N: Reflection (composable)

Invoke the `skill-reflection` skill with the following context:

- **Calling skill**: `obsidian-weekly-brain`
- **SKILL.md path**: `.github/skills/obsidian-weekly-brain/SKILL.md`
- **Steps completed**: list each pass with pass/fail/skipped + cost data
- **Friction notes**: any workarounds, retries, unexpected errors, or manual interventions

The reflection skill will analyze the run and produce improvement recommendations.
