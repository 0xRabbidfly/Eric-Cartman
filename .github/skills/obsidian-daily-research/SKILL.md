---
name: obsidian-daily-research
description: Daily AI research pipeline → Obsidian vault. Scans Reddit + X for agents, skills, models, MCP, RAG topics. Deduplicates against vault history, writes structured daily notes with Lab Pulse, Deep Dives, and categorized reading lists. Tag #keep to promote to long-term library.
argument-hint: daily research, run pipeline, what's new in AI
user-invokable: true
disable-model-invocation: true
metadata:
  author: 0xrabbidfly
  version: "1.0.0"
---

# Daily Research Pipeline

## Purpose

Automated daily research pipeline that scans 5 topic tracks across Reddit and X,
deduplicates against your Obsidian vault history, and writes a structured daily note
with a Lab Pulse rollup, Deep Dives section, and per-topic breakdowns.

**Cost**: ~$0.10-0.30/day (~$6/month) using scan mode with gpt-5.2 synthesis.

## Quick Start

```
# Full daily run (all 5 topics)
python .github/skills/obsidian-daily-research/scripts/run.py

# Single topic
python .github/skills/obsidian-daily-research/scripts/run.py --topic agents

# Preview without writing to vault
python .github/skills/obsidian-daily-research/scripts/run.py --dry-run

# Just promote #keep items to Library
python .github/skills/obsidian-daily-research/scripts/run.py --promote-only
```

## How It Works

### Pipeline Flow

1. **Promote Pass** — Scans previous dailies for `#keep` tags, promotes those items to `Research/Library/{topic}.md`
2. **Feedback Pass** — Scans previous dailies for `#good` / `#bad` tags, logs them to `feedback.json`, marks as processed
3. **Vault Dedup** — Scans all dailies + library files (including year/month subfolders), extracts every URL and title seen before (zero tokens — filesystem only)
4. **Multi-Topic Scan** — For each of 5 topics, runs Reddit + X search in scan mode (auto-selected model, no enrichment, 5-12 items each)
5. **Spam Detection** — Filters out misleading content (claim/link mismatches like fake "official guides", engagement bait)
6. **Quality Filters** — Engagement floor (100+ likes on X, 50+ on Reddit), long-form bonus, priority account boost
7. **Content Classification** — Tags each item as `deep-dive`, `lab-pulse`, or `general`
8. **Cross-Dedup** — Filters out any URLs/titles already in the vault
9. **Must-Follow Scan** — Dedicated per-person X search for tracked accounts. **No filters** — every tweet is captured.
10. **Batched Synthesis** — Single gpt-5.2 call to produce daily POW briefing + lab pulse summary + per-topic headlines
11. **Write Daily Note** — Outputs structured markdown to `Research/Dailies/YYYY/MM/YYYY-MM-DD.md`

### Must-Follow Accounts

Dedicated scan for key people — every tweet is captured regardless of engagement or quality filters. Configured in `config.json → must_follow.accounts`:

| Account | Group | Why |
|---------|-------|-----|
| @karpathy | Thought Leaders | Andrej Karpathy — frontier model insights |
| @daboris | Anthropic | Boris — Claude Code team |
| @alexalbert__ | Anthropic | Alex Albert — Anthropic prompt eng |
| @AnthropicAI | Anthropic | Official Anthropic account |
| @OpenAI | OpenAI | Official OpenAI account |
| @sama | OpenAI | Sam Altman |
| @markchen90 | OpenAI | Mark Chen — OpenAI eng lead |
| @GoogleDeepMind | Google | Google DeepMind |
| @JeffDean | Google | Jeff Dean |
| @xaborai | xAI | xAI official |
| @MistralAI | Mistral | Mistral AI |
| @ylecun | Meta | Yann LeCun |
| @MetaAI | Meta | Meta AI |
| @Alibaba_Qwen | Alibaba | Alibaba Qwen team |

To add/remove accounts, edit the `must_follow.accounts` array in `scripts/config.json`.

### Topics Tracked

| Topic | Slug | Weight |
|-------|------|--------|
| Agent Development | `agents` | 1.2x |
| Agent Skills & Tools | `skills` | 1.1x |
| Frontier Model Releases | `models` | 1.0x |
| MCP & Tool Use | `mcp` | 1.0x |
| RAG & AI Search | `rag` | 0.9x |

### Content Categories

Each item gets classified into one of three categories:

| Category | What it catches | Where it appears |
|----------|----------------|------------------|
| **Lab Pulse** | Posts from Anthropic, OpenAI, Google, Meta, Mistral and their lead devs | Dedicated Lab Pulse section at the top |
| **Deep Dives** | Long-form threads (≥400 chars), articles from known domains (substack, arxiv, medium, etc.) | Deep Dives section with checkboxes |
| **General** | Everything else that passes quality filters | Per-topic sections + Reading List |

### Tagging System

Three tags you can add to any item in a daily note:

| Tag | What it does | Processed as |
|-----|-------------|--------------|
| `#keep` | Promote item to `Research/Library/` with LLM-enriched summary | → `#kept` |
| `#good` | Log as positive feedback (good result, want more like this) | → `#good-noted` |
| `#bad` | Log as negative feedback (noisy, irrelevant, low quality) | → `#bad-noted` |

Feedback is accumulated in `scripts/feedback.json` with timestamps, titles, and URLs. Stats are shown in the daily note footer.

### Long-Term Memory

1. Read your daily note in Obsidian
2. Add `#keep` to any reading list item you want to preserve
3. Next pipeline run automatically promotes `#keep` items to `Research/Library/{topic}.md`
4. Tag gets changed to `#kept` so it's not reprocessed

### Daily Note Structure

```
Research/Dailies/2026/02/2026-02-26.md
├── YAML frontmatter (date, type, topics, stats, must_follow_tweets, deep_dives, lab_pulse)
├── Today's POW (vivid daily summary — the one thing that matters most)
├── Must Follow 📌 (every tweet from tracked accounts, grouped by org)
│   ├── Anthropic (AnthropicAI, alexalbert__, daboris)
│   ├── OpenAI (OpenAI, sama, markchen90)
│   ├── Google (GoogleDeepMind, JeffDean)
│   ├── Thought Leaders (karpathy)
│   └── ...other groups
├── Lab Pulse 🧪 (model provider rollup + table of lab posts)
├── Deep Dives 📖 (long-form threads and articles, checkboxes)
├── Reading List (top 15, checkboxes, topic tags)
├── Per-topic sections
│   ├── Headline + key points
│   ├── Reddit sources table
│   └── X sources table
├── Promote to Library instructions
└── Rate Results (feedback tag instructions + stats)
```

## Configuration

Edit `scripts/config.json`:
- `vault_path` — Path to your Obsidian vault
- `dailies_folder` — Base subfolder for daily notes (default: `Research/Dailies`). Notes are auto-organized into `YYYY/MM/` subfolders.
- `library_folder` — Subfolder for library notes (default: `Research/Library`)
- `items_per_topic` — Max items per topic (default: 8)
- `reading_list_max` — Max reading list items (default: 15)
- `must_follow.accounts` — List of X accounts to track (every tweet captured, no filters)
- `feedback_tags` — Tag names for feedback system (`#good`, `#bad`)

Custom topics can be added via a `topics` array in config.json.

### Quality Filters

Post-scoring filters applied inside `run_topic_scan()` via `config.json → quality_filters`:

| Filter | What it does | Config key |
|--------|-------------|------------|
| **Spam detection** | Drops fake "official guide" link bait, engagement farming posts. Catches claim/link mismatches and low-effort patterns. | `spam_detection.enabled`, `claim_link_mismatch_patterns`, `low_effort_patterns` |
| **Engagement floor** | Drops Reddit items with `score < 50` and X items with `likes < 100`. Lab/priority accounts bypass the floor. | `min_engagement.reddit_score`, `min_engagement.x_likes` |
| **Long-form bonus** | +15 pts for X posts with ≥400 chars (threads) and Reddit links to article domains (medium, substack, arxiv, etc.) | `long_form_bonus`, `long_form_min_chars`, `article_domains` |
| **Priority accounts** | +20 pts for posts from tracked accounts. Frontier lab releases always surface. | `priority_accounts.x`, `priority_account_bonus` |
| **Lab accounts** | Accounts from the 5 major labs, used for Lab Pulse rollup. Bypass engagement floor. | `lab_accounts.anthropic`, `lab_accounts.openai`, etc. |

### Followed Accounts

The `followed_accounts.x` list in config.json tracks accounts you follow. These get priority scoring. Since the Grok API doesn't expose your X follow graph, maintain this list manually.

To customize, edit the `quality_filters` block in `scripts/config.json`.

## Scheduling

Run `scripts/schedule.ps1` to register a Windows Task Scheduler task at 7:00 AM daily.

### Step N: Reflection (composable)

Invoke the `skill-reflection` skill with the following context:

- **Calling skill**: `<skill-name>`
- **SKILL.md path**: `.github/skills/<skill-name>/SKILL.md`
- **Steps completed**: list each step with pass/fail/skipped
- **Friction notes**: any workarounds, retries, unexpected errors, or manual interventions

The reflection skill will analyze the run and produce improvement recommendations.

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
