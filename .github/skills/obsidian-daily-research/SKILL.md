---
name: obsidian-daily-research
description: Use this skill when the user wants to run the daily AI research pipeline, scan Reddit or X for AI news, or write today's research into their Obsidian vault. Triggers for 'run the daily research', 'what's new in AI today', 'pull today's research', 'catch me up on agents/MCP/models', 'run the pipeline', 'daily scan'. Also use when the user wants to scan only specific sources (Reddit or X only), specify a vault path, or catch up after missing days.
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

# Intentionally rerun for the same day
python .github/skills/obsidian-daily-research/scripts/run.py --force-rerun

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
6. **Reply Filtering** — Drops replies from topic scans using both `is_reply` API field and text-pattern detection
7. **Quality Filters** — Strict engagement floor (100+ likes on X, 50+ on Reddit — items with unknown engagement are dropped, not bypassed), long-form bonus, priority account boost
8. **Content Classification** — Tags each item as `deep-dive`, `lab-pulse`, or `general`
9. **Cross-Dedup** — Filters out any URLs/titles already in the vault
10. **Must-Follow Scan** — Dedicated per-person X search for tracked accounts. No engagement floor — catches everything they post.
11. **Prominent AI Voices Scan** — Single broad X search for high-engagement (500+ likes) tweets from prominent AI researchers, engineers, and executives. One API call captures what the top minds are saying without hardcoding account names.
12. **Batched Synthesis** — Single gpt-5.2 call to produce daily POW briefing + lab pulse summary + per-topic headlines
13. **Write Daily Note** — Outputs structured markdown to `Research/Dailies/YYYY/MM/YYYY-MM-DD.md`

### Same-Day Run Protection

The pipeline is now single-write by default for each day.

- If today's daily note already exists, the run exits before scanning.
- It does not create `-2`, `-3`, or other suffixed duplicates anymore.
- Use `--force-rerun` only when you intentionally want to regenerate the day.

### Must-Follow Accounts

Dedicated scan for key people — catches everything they post (no engagement floor). Configured in `config.json → must_follow.accounts`:

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

To add/remove accounts, edit the `# Must-Follow Accounts` section in `pipeline.md`.

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
| **Prominent Voices** | High-engagement tweets (500+ likes) from any prominent AI figure, found via broad search | Prominent Voices section with engagement stats |
| **Deep Dives** | Long-form threads (≥800 chars), articles from known domains (substack, arxiv, medium, etc.) | Deep Dives section with checkboxes |
| **General** | Everything else that passes quality filters | Per-topic sections + Reading List |

### Tagging System

Three tags you can add to any item in a daily note:

| Tag | What it does | Processed as |
|-----|-------------|--------------|
| `#keep` | Promote item to `Research/Library/` with LLM-enriched summary | → `#kept` |
| `#good <reason>` | Log as positive feedback. Add a reason for better analysis: `#good deep practical tutorial` | → `#good-noted` |
| `#bad <reason>` | Log as negative feedback. Add a reason: `#bad it was a reply`, `#bad bot-generated`, `#bad self-promo fake official guide` | → `#bad-noted` |

Feedback is accumulated in `scripts/feedback.json` with timestamps, titles, URLs, reasons, and topic context.

### Feedback Learning Loop

The pipeline learns from your `#good` and `#bad` tags across a 14-day rolling window:

1. **Collection** — Each run scans previous dailies for unprocessed `#good`/`#bad` tags (skips blockquote template lines). Captures the reason text after the tag and which topic section the item was in.
2. **Classification** — Reasons are auto-classified into buckets:
   - **Bad buckets**: `reply`, `low-engagement`, `bot`, `self-promo`, `misleading`, `off-topic`, `duplicate`, `stale`
   - **Good buckets**: `long-form`, `original-research`, `practical`, `insider`, `high-signal`
3. **Analysis** — Patterns are extracted: which buckets dominate, which topics produce the most bad results, what good items have in common.
4. **Proposals** — Concrete improvement suggestions are generated and rendered in the daily note's **Feedback Insights** section. Examples:
   - "3/5 bad items were replies → reply filter may need strengthening"
   - "All 4 good items were long-form → consider boosting `long_form_bonus`"
   - "Topic X produces 60% of bad items → search queries may be too broad"
5. **Advisory only** — Proposals appear in the daily note for you to review. No auto-applied config changes.

The more reasons you add to your tags, the more precise the proposals become. Tags without reasons still count but get classified as `unclassified`.

### Long-Term Memory

1. Read your daily note in Obsidian
2. Add `#keep` to any reading list item you want to preserve
3. Next pipeline run automatically promotes `#keep` items to `Research/Library/{topic}.md`
4. Tag gets changed to `#kept` so it's not reprocessed

### Daily Note Structure

```
Research/Dailies/2026/02/2026-02-26.md
├── YAML frontmatter (date, type, topics, stats, must_follow_tweets, prominent_voices, deep_dives, lab_pulse)
├── Today's POW (vivid daily summary — the one thing that matters most)
├── Must Follow 📌 (tweets from tracked accounts, no engagement floor, grouped by org)
│   ├── Anthropic (AnthropicAI, alexalbert__, daboris)
│   ├── OpenAI (OpenAI, sama, markchen90)
│   ├── Google (GoogleDeepMind, JeffDean)
│   ├── Thought Leaders (karpathy)
│   └── ...other groups
├── Prominent Voices 🎙️ (high-engagement 500+ likes tweets from top AI minds, sorted by likes)
├── Lab Pulse 🧪 (model provider rollup + table of lab posts)
├── Deep Dives 📖 (long-form threads ≥800 chars and articles, checkboxes)
├── Reading List (top 15, checkboxes, topic tags)
├── Per-topic sections
│   ├── Headline + key points
│   ├── Reddit sources table
│   └── X sources table
├── Promote to Library instructions
├── Rate Results (feedback tag instructions with examples + stats)
├── Feedback Insights 🔍 (pattern analysis + improvement proposals from last 14 days)
└── Efficiency Recommendations
```

## Configuration

Edit `pipeline.md` (single source of truth):
- `vault_path` — Path to your Obsidian vault
- `dailies_folder` — Base subfolder for daily notes (default: `Research/Dailies`). Notes are auto-organized into `YYYY/MM/` subfolders.
- `library_folder` — Subfolder for library notes (default: `Research/Library`)
- `items_per_topic` — Max items per topic (default: 8)
- `reading_list_max` — Max reading list items (default: 15)
- `# Must-Follow Accounts` section — List of X accounts to track (no engagement floor — catches everything)
- `feedback_tags` — Tag names for feedback system (`#good`, `#bad`)

Custom topics can be added via a `topics` array in config.json.

### Quality Filters

Post-scoring filters applied inside `run_topic_scan()` via `config.json → quality_filters`:

| Filter | What it does | Config key |
|--------|-------------|------------|
| **Spam detection** | Drops fake "official guide" link bait, engagement farming posts. Catches claim/link mismatches and low-effort patterns. | `spam_detection.enabled`, `claim_link_mismatch_patterns`, `low_effort_patterns` |
| **Reply filtering** | Drops replies from topic scans using `is_reply` API field and text-pattern detection (`@someone` prefix). Applied to all topic scans. | N/A (always on) |
| **Engagement floor** | Drops Reddit items with `score < 50` and X items with `likes < 100`. Items with unknown engagement are dropped (not bypassed). Lab/priority accounts bypass the floor. Must-follow accounts have no floor. | `min_engagement.reddit_score`, `min_engagement.x_likes` |
| **Long-form bonus** | +15 pts for X posts with ≥800 chars (threads) and Reddit links to article domains (medium, substack, arxiv, etc.) | `long_form_bonus`, `long_form_min_chars`, `article_domains` |
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
