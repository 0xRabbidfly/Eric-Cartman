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

A weekly intelligence digest that mines the entire Obsidian vault corpus and produces a single analytical document. Designed to run every Sunday morning via scheduled task.

## What It Does

The script performs 9 passes over your vault, then picks "The One Thing": one
item from Do This Week or a Blindspot "Note to write", sized to under two hours
and capped at 80 words. Each pick is logged in `Research/one-thing.json`; the next
run marks it done if a Research note by that name has appeared, and an undone
pick carries over under the same name ("Carried over, week N") instead of
returning reworded.

1. **Trend Momentum** — Topics rising and cooling as a share of the notes you save
2. **Thesis Health Check** — Supporting/contradicting evidence, thesis decay detection
3. **Blindspot Detection** — Missing subtopics, high consumption-to-synthesis ratios
4. **Cross-Domain Bridges** — Unusual tag co-occurrences that reveal insight
5. **Zeitgeist Snapshot** — Dominant tensions, what's hot, what disappeared
6. **Actionable Insights** — LEARN/BUILD/WATCH/RECONSIDER recommendations
7. **Prediction Extraction** — Forecasts from sources, resolution tracking
8. **Account Discovery** — X handles worth following, from curated-note provenance
9. **Cost Tracking** — This run's cost plus the week's research spend

Output: `Research/Reports/weekly-brain-YYYY-MM-DD.md`

## Quick Start

```powershell
python .github/skills/obsidian-weekly-brain/scripts/brain.py
```

## Scheduling

Runs locally from Windows Task Scheduler as `WeeklyBrain`, Sundays at 7:00 AM Eastern
(the trigger is pinned to UTC-5, so it fires at 8:00 AM while daylight saving is on):

```powershell
# Register or update the task. Elevated, it also runs while logged off (S4U);
# without admin it registers for the current user and runs while logged on.
.github/skills/obsidian-weekly-brain/scripts/schedule.ps1
```

The task calls `scripts/run-scheduled.ps1`, which writes each run to
`logs/weekly-brain-<timestamp>.log` (UTF-8), ending with the run's cost line. The
log's `Launcher:` line names the process that started the run. The wrapper holds a
named mutex, so a second copy started mid-run logs that and exits without
touching the report. The week's cost row also lands in
`Research/Reports/weekly-costs.md`.

Keep it local. A cloud or Claude Desktop routine cannot run it: `api.x.ai` is
blocked from the cloud sandbox, and the script uses this machine's Windows paths
for the vault and `claude.exe`.


## CLI Options

```
python brain.py                    # Full weekly digest
python brain.py --pass trend       # Run only trend analysis
python brain.py --pass zeitgeist   # Run only zeitgeist
python brain.py --dry-run          # Analyze but don't write to vault
python brain.py --weeks 2          # Lookback window (default 4)
```

## Data Sources

- `Research/Library/` — All research notes (~420 as of 2026-11)
- `Research/Dailies/` — Daily research notes (last 4 weeks)
- `Podcasts/` — Podcast notes (skip transcripts/)
- `Research/connections.json` — Connection graph
- `Research/theses.json` — Thesis tracker data
- `Research/predictions.json` — Prediction tracker (created if needed)
- `Research/one-thing.json` — One Thing history: each ask, weeks open, done/replaced

## Requirements

- Python 3.10+
- Claude Code CLI, logged in to the Max subscription: every LLM call goes through
  `claude --print` first, at no per-call charge
- xAI API key in `~/.config/last30days/.env` (as `XAI_API_KEY`): the fallback when
  the Claude CLI fails. The script exits at startup without it.
- No pip dependencies (stdlib only)

## Step N: Reflection (composable)

Invoke the `skill-reflection` skill with the following context:

- **Calling skill**: `obsidian-weekly-brain`
- **SKILL.md path**: `.github/skills/obsidian-weekly-brain/SKILL.md`
- **Steps completed**: list each pass with pass/fail/skipped + cost data
- **Friction notes**: any workarounds, retries, unexpected errors, or manual interventions

The reflection skill will analyze the run and produce improvement recommendations.
