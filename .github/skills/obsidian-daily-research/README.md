# Daily Research Pipeline

Automated daily research pipeline that scans topic tracks on X, pulls Google News RSS, tracks frontier-lab accounts, deduplicates against your Obsidian vault history, and writes a mobile-friendly daily note.

**Cost**: ~$0.05–0.15/day (~$3/month) using scan mode.

## Quick Start

```powershell
# Full daily run (all 5 topics)
python .github/skills/obsidian-daily-research/scripts/run.py

# Single topic
python .github/skills/obsidian-daily-research/scripts/run.py --topic agents

# Preview without writing to vault
python .github/skills/obsidian-daily-research/scripts/run.py --dry-run


# Show all seen URLs (dedup set)
python .github/skills/obsidian-daily-research/scripts/run.py --show-dedup

# Show estimated token costs after run
python .github/skills/obsidian-daily-research/scripts/run.py --costs
```

## Topics Tracked

| Topic | Slug | Weight | Description |
|-------|------|--------|-------------|
| Agent Development | `agents` | 1.2x | AI agents, agentic coding, frameworks |
| Agent Skills & Tools | `skills` | 1.1x | SKILL.md, copilot skills, MCP tools |
| Frontier Model Releases | `models` | 1.0x | GPT, Claude, Gemini releases & benchmarks |
| MCP & Tool Use | `mcp` | 1.0x | Model Context Protocol, function calling |
| RAG & AI Search | `rag` | 0.9x | RAG pipelines, vector search, embeddings |

## How It Works

```
┌─────────────────────────────────────────────────────┐
│  Windows Task Scheduler (1:00 AM daily)             │
│  python .github/skills/obsidian-daily-research/scripts/run.py│
└──────────┬──────────────────────────────────────────┘
           │
           ▼
  1. VAULT DEDUP      Scan all dailies + library files
           |           -> extract every URL and title seen before (zero tokens)
           v
  2. TOPIC SCANS      One X search per topic, scan mode (grok-4.3)
           v
  3. CROSS-DEDUP      Filter out URLs/titles already in vault
           v
  4. LAB SCAN         Batched X search over lab-group accounts,
           |           chunks of 10, no engagement floor
           v
  5. PROMINENT        One broad X search, 500+ likes, no hardcoded
     VOICES            handles; retries if under the prompt's floor
           v
  6. NEWS             Google News RSS per topic, deduped against
           |           vault by URL + title, then LLM-ranked
           v
  7. SYNTHESIS        One Claude CLI call over ALL of the above ->
           |           POW briefing + lab pulse summary (free on Max)
           v
  8. WRITE DAILY      Output structured markdown to
     NOTE              Research/Dailies/YYYY/MM/YYYY-MM-DD.md
```

## Daily Note Structure

```
Research/Dailies/2026/08/2026-08-03.md
├── YAML frontmatter (date, type, topics, stats)
├── Pipeline Cost callout (calls, tokens, $)
├── Today's POW (the day's lede, synthesized from every source)
├── Lab Pulse (prose rollup + list of lab-account posts)
├── Prominent Voices (high-engagement posts, sorted by likes)
├── News (numbered list, vault-deduped)
├── Research Feed (ranked topic-scan items; 📖 marks long-form)
└── Efficiency Recommendations
```

## Research Library

`Research/Library/` is written automatically by the auto-capture accounts listed in
`pipeline.md`, and is read on every run for deduplication. There is no manual
`#keep` promotion path — it was removed along with the `--promote-only` flag.

## Scheduled Task

Registered via Windows Task Scheduler at **1:00 AM daily**.
The scheduled action runs through `scripts/run-scheduled.ps1`, which writes a timestamped log file to `logs/` for every attempt.
The task is configured to wake the PC, tolerate battery state changes, and run without an active VS Code session or interactive desktop login.

```powershell
# Register (run as Admin)
powershell -ExecutionPolicy Bypass -File .github/skills/obsidian-daily-research/scripts/schedule.ps1

# Verify
Get-ScheduledTask -TaskName "DailyResearchPipeline" | Format-List TaskName, State
Get-ScheduledTask -TaskName "DailyResearchPipeline" | Get-ScheduledTaskInfo

# Test now
Start-ScheduledTask -TaskName "DailyResearchPipeline"

# Tail the latest scheduled-run log
Get-ChildItem .github/skills/obsidian-daily-research/logs |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1 |
  Get-Content -Tail 100

# Remove
Unregister-ScheduledTask -TaskName "DailyResearchPipeline"
```

## Configuration

Edit `scripts/config.json`:

```json
{
  "vault_path": "C:\\Users\\nuno_\\Documents\\Obsidian Vault",
  "dailies_folder": "Research/Dailies",
  "library_folder": "Research/Library",
  "items_per_topic": 8,
  "reading_list_max": 15,
  "depth": "scan"
}
```

Custom topics can be added via a `topics` array in config.json.

## Dependencies

- **Python 3.10+** (stdlib only — zero pip dependencies)
- **API keys** in `~/.config/last30days/.env`:
  - `XAI_API_KEY` — all X search (pinned to `grok-4.3`)
  - `XAI_API_KEY` — X/Twitter search
- Reuses `last30days` lib modules (openai_reddit, xai_x, normalize, score, dedupe)

## File Structure

```
.github/skills/obsidian-daily-research/
├── SKILL.md              # Agent instructions
├── README.md             # This file
└── scripts/
    ├── run.py            # Main orchestrator
    ├── config.json       # Vault path + settings
    ├── schedule.ps1      # Task Scheduler setup
    └── lib/
        ├── __init__.py
        ├── vault.py      # Obsidian vault R/W + dedup
        ├── topics.py     # 5 topic tracks with search queries
```
