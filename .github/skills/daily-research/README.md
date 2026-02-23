# Daily Research Pipeline

Automated daily research pipeline that scans 5 topic tracks across Reddit and X, deduplicates against your Obsidian vault history, and writes a structured daily note with a reading list and per-topic breakdowns.

**Cost**: ~$0.05–0.15/day (~$3/month) using scan mode.

## Quick Start

```powershell
# Full daily run (all 5 topics)
python .github/skills/daily-research/scripts/run.py

# Single topic
python .github/skills/daily-research/scripts/run.py --topic agents

# Preview without writing to vault
python .github/skills/daily-research/scripts/run.py --dry-run

# Just promote #keep items to Library
python .github/skills/daily-research/scripts/run.py --promote-only

# Show all seen URLs (dedup set)
python .github/skills/daily-research/scripts/run.py --show-dedup

# Show estimated token costs after run
python .github/skills/daily-research/scripts/run.py --costs
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
│  Windows Task Scheduler (7:00 AM daily)             │
│  python .github/skills/daily-research/scripts/run.py│
└──────────┬──────────────────────────────────────────┘
           │
           ▼
  1. PROMOTE PASS     Scan previous dailies for #keep tags
           │           → move to Research/Library/{topic}.md
           ▼
  2. VAULT DEDUP      Scan all dailies + library files
           │           → extract every URL seen before (zero tokens)
           ▼
  3. MULTI-TOPIC      For each of 5 topics, run Reddit + X search
     SCAN              in scan mode (gpt-4o-mini synthesis,
           │           gpt-5.x Reddit, grok-4-1-fast X, 5-12 items each)
           ▼
  4. CROSS-DEDUP      Filter out URLs/titles already in vault
           │
           ▼
  5. BATCHED           Single gpt-4o-mini call to produce
     SYNTHESIS         briefing + per-topic headlines
           │
           ▼
  6. WRITE DAILY      Output structured markdown to
     NOTE              Research/Dailies/YYYY-MM-DD.md
```

## Daily Note Structure

```
Research/Dailies/2026-02-23.md
├── YAML frontmatter (date, type, topics, stats)
├── Key Briefing (executive summary)
├── Reading List (top 15, checkboxes, topic tags)
├── Per-topic sections
│   ├── Headline + key points
│   ├── Reddit sources table
│   └── X sources table
└── Promote to Library instructions
```

## Long-Term Memory (`#keep` → Library)

1. Read your daily note in Obsidian
2. Add `#keep` to any reading list item you want to preserve
3. Next pipeline run automatically promotes `#keep` items to `Research/Library/{topic}.md`
4. Tag gets changed to `#kept` so it's not reprocessed

## Scheduled Task

Registered via Windows Task Scheduler at **7:00 AM daily**.

```powershell
# Register (run as Admin)
powershell -ExecutionPolicy Bypass -File .github/skills/daily-research/scripts/schedule.ps1

# Verify
Get-ScheduledTask -TaskName "DailyResearchPipeline" | Format-List TaskName, State
Get-ScheduledTask -TaskName "DailyResearchPipeline" | Get-ScheduledTaskInfo

# Test now
Start-ScheduledTask -TaskName "DailyResearchPipeline"

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
  "keep_tag": "#keep",
  "kept_tag": "#kept",
  "items_per_topic": 8,
  "reading_list_max": 15,
  "depth": "scan"
}
```

Custom topics can be added via a `topics` array in config.json.

## Dependencies

- **Python 3.10+** (stdlib only — zero pip dependencies)
- **API keys** in `~/.config/last30days/.env`:
  - `OPENAI_API_KEY` — Reddit search + synthesis
  - `XAI_API_KEY` — X/Twitter search
- Reuses `last30days` lib modules (openai_reddit, xai_x, normalize, score, dedupe)

## File Structure

```
.github/skills/daily-research/
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
        └── promote.py    # #keep → Library promotion
```
