---
name: obsidian-weekly-brain
description: Weekly intelligence digest analyzing the vault corpus for trends, thesis health, blindspots, cross-domain bridges, zeitgeist, predictions and accounts to follow, ending with a self-review against its own section goals. Triggers: "weekly brain", "brain digest", "what did my vault learn this week".
user-invocable: true
argument-hint: "--pass trend|thesis|blindspot|bridge|zeitgeist|predict|discover|cost"
disable-model-invocation: true
metadata:
  author: 0xrabbidfly
  version: "1.0.0"
---

# Obsidian Weekly Brain

## Purpose

A weekly intelligence digest that mines the entire Obsidian vault corpus and produces a single analytical document. Designed to run every Sunday morning via scheduled task.

## What It Does

The script performs 8 passes over your vault, then picks "The One Thing": one
Blindspot "Note to write" or Bridge "Do", sized to under two hours
and capped at 80 words. Each pick is logged in `Research/one-thing.json`; the next
run marks it done if a Research note by that name has appeared, and an undone
pick carries over under the same name ("Carried over, week N") instead of
returning reworded.

1. **Trend Momentum** — Topics rising and cooling as a share of the notes you save
2. **Thesis Health Check** — Each thesis's claim, how its evidence is moving, key dates, best read
3. **Blindspot Detection** — What you keep reading with no Library note; open gaps carry over by name
4. **Cross-Domain Bridges** — New bridge edges between notes from different clusters
5. **Zeitgeist Snapshot** — A 350-450 word essay on the fortnight's biggest idea, rotating subject, with links
6. **Prediction Extraction** — Checkable, dated forecasts from sources and from the digest's own
   essay; due ones are judged against the vault, then the web (cited); a "who's been right" scorecard
7. **Account Discovery** — X handles worth following, from curated-note provenance
8. **Cost Tracking** — This run's cost plus the week's research spend

(Do This Week / Actionable Insights was dropped 2026-11-03: it restated the
Blindspots and Bridges and its items were never done.)

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

## Section goals

What each part of the digest is for, and how to tell it's working. The
self-review at the end of every run judges the run against this table, so
change it here when a goal changes.

| Section | Goal | Working when |
|---|---|---|
| The One Thing | One small, finishable action for the week | <=80 words; picked from Blindspots or Bridges; an undone ask carries over by name; asks actually get done |
| Trend Momentum | Which topics you're reading more or less of | Ranked by share, not raw count; background tags (>12% of notes) excluded; each rising tag links its notes |
| Thesis Health | Per thesis: the claim, how it's moving, key dates, one best read | Every live thesis has a one-line summary; merged theses fold into one line; most active first |
| Blindspots | Gaps between what you read and what the Library holds | <=3 gaps, ~300 words total; a recurring gap keeps its name with "Open since"; long-open gaps shrink to a first step |
| Cross-Domain Bridges | New links across clusters worth testing | Only bridges detected since the last report; each ends in a concrete "Do" |
| Zeitgeist | One argued idea from the fortnight | 350-450 words; subject differs from recent essays unless it dominates; avoids the Blindspot/One Thing topics; 3-5 valid links; any forecast stated with a date |
| Predictions | A scored record of who calls the future right | New calls have a named source, checkable outcome and due date; few "unverifiable"; web verdicts cite a URL; scorecard grows |
| Discover | Accounts worth following | One line per account; nothing suggested more than twice |
| Run | A reliable, cheap, unattended run | One run per Sunday; no ERROR lines or xAI fallbacks; dry runs write nothing |

## Self-review (automatic, last step)

After the report is built, `brain.py` runs the `skill-reflection` skill on the
run itself: one Claude call given `skill-reflection/SKILL.md` as its
instructions, this SKILL.md (purpose and Section goals), measured metrics per
section (word counts, link validity, repeat counts, prediction verdict mix),
the run's ERROR/WARNING lines, the report, and the last two reflections for
repeat detection. It is advisory and never edits this file.

- Full reflection: `Research/Reports/Skill Reflections/obsidian-weekly-brain-YYYY-MM-DD.md`
- The report ends with a short **Self-Review** section: the top recommendations
  and a link to the full reflection.
- Dry runs print the reflection and write nothing.
