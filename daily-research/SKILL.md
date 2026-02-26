---
name: daily-research
description: Daily AI research pipeline → Obsidian vault. Scans Reddit + X for agents, skills, models, MCP, RAG topics. Deduplicates against vault history, writes structured daily notes. Tag #keep to promote to long-term library.
argument-hint: daily research, run pipeline, what's new in AI
user-invokable: true
---

# Daily Research Pipeline

## Purpose

Automated daily research pipeline that scans 5 topic tracks across Reddit and X,
deduplicates against your Obsidian vault history, and writes a structured daily note
with a reading list and per-topic breakdowns.

**Cost**: ~$0.05-0.15/day (~$3/month) using scan mode with gpt-4o-mini.

## Quick Start

```
# Full daily run (all 5 topics)
python .github/skills/daily-research/scripts/run.py

# Single topic
python .github/skills/daily-research/scripts/run.py --topic agents

# Preview without writing to vault
python .github/skills/daily-research/scripts/run.py --dry-run

# Just promote #keep items to Library
python .github/skills/daily-research/scripts/run.py --promote-only
```

## How It Works

### Pipeline Flow

1. **Promote Pass** — Scans previous dailies for `#keep` tags, promotes those items to `Research/Library/{topic}.md`
2. **Vault Dedup** — Scans all dailies + library files, extracts every URL and title seen before (zero tokens — filesystem only)
3. **Multi-Topic Scan** — For each of 5 topics, runs Reddit + X search in scan mode (gpt-4o-mini, no enrichment, 5-12 items each)
4. **Cross-Dedup** — Filters out any URLs/titles already in the vault
5. **Batched Synthesis** — Single gpt-4o-mini call to produce briefing + per-topic headlines
6. **Write Daily Note** — Outputs structured markdown to `Research/Dailies/YYYY-MM-DD.md`

### Topics Tracked

| Topic | Slug | Weight |
|-------|------|--------|
| Agent Development | `agents` | 1.2x |
| Agent Skills & Tools | `skills` | 1.1x |
| Frontier Model Releases | `models` | 1.0x |
| MCP & Tool Use | `mcp` | 1.0x |
| RAG & AI Search | `rag` | 0.9x |

### Long-Term Memory

1. Read your daily note in Obsidian
2. Add `#keep` to any reading list item you want to preserve
3. Next pipeline run automatically promotes `#keep` items to `Research/Library/{topic}.md`
4. Tag gets changed to `#kept` so it's not reprocessed

### Daily Note Structure

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

## Configuration

Edit `scripts/config.json`:
- `vault_path` — Path to your Obsidian vault
- `dailies_folder` — Subfolder for daily notes (default: `Research/Dailies`)
- `library_folder` — Subfolder for library notes (default: `Research/Library`)
- `items_per_topic` — Max items per topic (default: 8)
- `reading_list_max` — Max reading list items (default: 15)

Custom topics can be added via a `topics` array in config.json.

### Quality Filters

Post-scoring filters applied inside `run_topic_scan()` via `config.json → quality_filters`:

| Filter | What it does | Config key |
|--------|-------------|------------|
| **Engagement floor** | Drops Reddit items with `score < 50` and X items with `likes < 50` (~1K views). Items with unknown engagement pass through. | `min_engagement.reddit_score`, `min_engagement.x_likes` |
| **Long-form bonus** | +10 pts for X posts with ≥500 chars (threads) and Reddit links to article domains (medium, substack, arxiv, etc.) | `long_form_bonus`, `long_form_min_chars`, `article_domains` |
| **Priority accounts** | +15 pts for posts from followed accounts (Anthropic, OpenAI, key devs). Frontier lab releases always surface. | `priority_accounts.x`, `priority_accounts.reddit_subreddits`, `priority_account_bonus` |

To customize, edit the `quality_filters` block in `scripts/config.json`.

## Scheduling

Run `scripts/schedule.ps1` to register a Windows Task Scheduler task at 7:00 AM daily.

## Dependencies

- Reuses `last30days` lib modules (openai_reddit, xai_x, normalize, score, dedupe)
- Composes with `obsidian` skill for all vault I/O (read, write, search, list files)
- API keys from `~/.config/last30days/.env` (OPENAI_API_KEY, XAI_API_KEY)
- Python 3.10+ (stdlib only — zero pip dependencies)
- Obsidian must be running with CLI enabled

## Related Skills

- **obsidian** — Vault operations (composed — required)
- **last30days** — Full deep research (use for `#deep-dive` tagged topics)
- **session-log** — Capture coding session insights
