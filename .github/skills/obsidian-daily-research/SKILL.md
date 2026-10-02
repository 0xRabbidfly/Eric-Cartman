---
name: obsidian-daily-research
description: Use this skill when the user wants to run the daily AI research pipeline, scan X for AI news, or write today's research into their Obsidian vault. Triggers for 'run the daily research', 'what's new in AI today', 'pull today's research', 'catch me up on agents/MCP/models', 'run the pipeline', 'daily scan'. Also use when the user wants to scan only specific sources, specify a vault path, or catch up after missing days.
argument-hint: daily research, run pipeline, what's new in AI
user-invocable: true
disable-model-invocation: true
metadata:
   author: 0xrabbidfly
   version: "1.0.1"
---

# Daily Research Pipeline

## Purpose

Automated daily research pipeline that scans topic tracks on X (weekly), pulls
Google News RSS, tracks lab accounts, deduplicates against your Obsidian vault history, and
writes a mobile-friendly daily note.

**Cost**: ~$0.20–0.30/day, ~$0.65 on the weekly topic-scan day (~$8–9/month). xAI
bills X search per post fetched (since 2026-09-21), so topic scans — the costliest
section for the fewest new items — run once a week (`topic_scan_day`, default
Monday) over a 7-day window. Search runs on a pinned `grok-4.3`; analysis
(briefing, lab summary, news scoring) runs on Claude CLI and is free on a Max
account, with `grok-4.5` as the fallback.

## Quick Start

```
# Full daily run (topic scans only on topic_scan_day)
python .github/skills/obsidian-daily-research/scripts/run.py

# Single topic
python .github/skills/obsidian-daily-research/scripts/run.py --topic agents

# Preview without writing to vault
python .github/skills/obsidian-daily-research/scripts/run.py --dry-run

# Run topic scans today even if it is not topic_scan_day
python .github/skills/obsidian-daily-research/scripts/run.py --topics-now

# Intentionally rerun for the same day
python .github/skills/obsidian-daily-research/scripts/run.py --force-rerun

```

## How It Works

### Pipeline Flow

1. **Vault Dedup** — Scans all dailies + library files (including year/month subfolders), extracts every URL and title seen before (zero tokens — filesystem only)
2. **Multi-Topic Scan** — One X search per topic in scan mode, weekly on `topic_scan_day` (7-day window). Other days the note records `research_feed: skipped`, which the drift check ignores
3. **Spam Detection** — Filters out misleading content (claim/link mismatches like fake "official guides", engagement bait)
4. **Reply Filtering** — Drops replies from topic scans using both `is_reply` API field and text-pattern detection
5. **Quality Filters** — Engagement floor (100+ likes on X), long-form bonus, priority-account boost. Every handle in the must-follow roster bypasses the floor and gets the boost, whether or not it is scanned.
6. **Content Classification** — Tags each item as `deep-dive`, `lab-pulse`, or `general`
7. **Cross-Dedup** — Filters out any URLs/titles already in the vault
8. **Lab Account Scan** — Batched X search over the lab-group accounts only, in chunks of 10 (`allowed_x_handles` caps at 10 and truncates silently past it). No engagement floor, so it catches the sub-500 posts Prominent Voices structurally cannot see. Results split by account type: `(org)` accounts feed the Lab Pulse rollup, lab researchers are folded into Prominent Voices.
9. **Prominent AI Voices Scan** — One broad X search for high-engagement (500+ likes) posts, no hardcoded account names. Retries when the result lands under the prompt's own floor.
10. **Google News RSS** — Per-topic RSS fetch, deduplicated against vault history by URL and title, then LLM-scored and ranked
11. **Batched Synthesis** — One Claude CLI call producing the POW briefing and lab pulse summary, reading topic scans, news, prominent voices and lab posts together
12. **Article Capture** — Article URLs linked from the day's posts are offered to the synthesis call, which picks any worth a permanent note. Those run through the `obsidian-linked-research` skill into `Research/Library`. Capped by `auto_capture_max`, validated against the candidate list, and skipped on `--dry-run`.
    - **Feed Capture** — Every post from the feeds under `# Capture Feeds` in `pipeline.md` (currently `https://claude.dev/rss.xml`) is captured, with no synthesis judgment. The vault is the manifest: an item is pending until a Library note's `url:` (or `**Cross-posted**:` line) matches it, so a failed capture retries next run. Capped by `feed_capture_max` (default 5). `run.py --feeds-only` runs only this stage.
    - **Captures are verified, not trusted.** Each capture is a headless `claude -p` run started from the repo root, and success means the note exists in `Research/Library` afterwards. The exit code is not the test: a run whose tool calls are denied prints a refusal and exits 0. That is how every capture failed silently between 2026-09-25 and 2026-10-02, while the log said "added". The scheduled task starts in `.github\`, where the repo's `.claude/settings.local.json` allowlist does not apply.
13. **Write Daily Note** — Outputs structured markdown to `Research/Dailies/YYYY/MM/YYYY-MM-DD.md`
14. **Sync Hand-off** — Leaves Obsidian running so Sync can push the note off this machine. Writes land on the vault filesystem and Sync only pushes while the desktop app runs, so a scheduled run with the app closed keeps its note local, where any other device asked to open it reports the file missing. Prints one `[sync]` line, never raises; `OBSIDIAN_AUTOLAUNCH=0` opts out and accepts the lag.

### Same-Day Run Protection

The pipeline is now single-write by default for each day.

- If today's daily note already exists, the run exits before scanning.
- It does not create `-2`, `-3`, or other suffixed duplicates anymore.
- Use `--force-rerun` only when you intentionally want to regenerate the day.

### Must-Follow Accounts

`pipeline.md` is the source of truth for accounts, topics, paths and settings.

Only accounts in a **lab group** (a `##` header matching `LAB_GROUP_MAP` in
`scripts/run.py`) are scanned, batched in chunks of 10.

Within a lab group, `(org)` marks an official company or product account. Only
those feed the **Lab Pulse** rollup, which renders as prose with no tweet list —
a lab post appears exactly once in the note. Researchers at the same labs render
under **Prominent Voices**, bypassing its 500-like floor because the lab scan has
none. Over 14 days every sub-500 post came from an org account and every
researcher post cleared 500, so the split matches how the two actually post.

Accounts in non-lab groups
are not scanned but stay on the list: every must-follow handle bypasses the
topic-scan engagement floor and earns a priority-score bonus, so removing them
would quietly degrade ranking. They reach the note through Prominent Voices.

### Content Categories

Each item gets classified into one of three categories:

| Category | What it catches | Where it appears |
|----------|----------------|------------------|
| **Lab Pulse** | Posts from Anthropic, OpenAI, Google, SpaceXAI, Meta, Mistral, Moonshot and their lead devs — sourced from both the must-follow scan (primary) and topic scans. Membership comes from the account's `##` group in `pipeline.md` matching `LAB_GROUP_MAP` in `scripts/run.py` | Dedicated Lab Pulse section at the top |
| **Prominent Voices** | High-engagement tweets (`prominent_ai_min_likes`, default 500+) from any prominent AI figure, found via broad search. Items with unverifiable like counts are kept — the search query itself enforces the floor. | Prominent Voices section with engagement stats |
| **Deep Dives** | Long-form threads (≥400 chars), articles from known domains (substack, arxiv, medium, etc.) | 📖 badge on the item in Research Feed |
| **General** | Everything else that passes quality filters | Research Feed |

### Tags

The daily note carries no action tags. The `#keep` promote path and the
`#good`/`#bad` feedback loop were both removed — the feedback tags accumulated in
`feedback.json` with nothing reading them, so tagging changed nothing.

`Research/Library` is still written automatically by the auto-capture accounts,
the capture feeds, and the article-capture step, and is still read for deduplication.

### Daily Note Structure

```
Research/Dailies/2026/08/2026-08-03.md
├── YAML frontmatter (date, type, topics, stats)
├── Pipeline Cost callout (calls, tokens, $)
├── Today's POW (the day's lede — synthesized from ALL sources: topic scans,
│                news headlines, prominent voices, and lab posts)
├── Lab Pulse 🧪 (prose rollup + list of lab-account posts)
├── Prominent Voices 🎙️ (high-engagement posts, list, sorted by likes)
├── News 📰 (numbered list, Google News RSS, vault-deduped)
├── Research Feed (merged topic-scan items, ranked; 📖 marks long-form)
└── Efficiency Recommendations
```

## Configuration

Edit `pipeline.md` for runtime configuration. It is the single source of truth for
topics, must-follow accounts, and pipeline settings.

### Quality Filters

Post-scoring filters applied inside `run_topic_scan()` via `config.json → quality_filters`:

| Filter | What it does | Config key |
|--------|-------------|------------|
| **Spam detection** | Drops fake "official guide" link bait, engagement farming posts. Catches claim/link mismatches and low-effort patterns. | `spam_detection.enabled`, `claim_link_mismatch_patterns`, `low_effort_patterns` |
| **Reply filtering** | Drops replies from topic scans using `is_reply` API field and text-pattern detection (`@someone` prefix). Applied to all topic scans. | N/A (always on) |
| **Engagement floor** | Drops X items with `likes < 100`. Items with unknown engagement are dropped (not bypassed). Lab/priority accounts bypass the floor. Must-follow accounts have no floor. | `min_engagement.x_likes` |
| **Long-form bonus** | +15 pts for X posts with ≥400 chars (threads). | `long_form_bonus`, `long_form_min_chars` |
| **Priority accounts** | +20 pts for posts from tracked accounts. Frontier lab releases always surface. | `priority_accounts.x`, `priority_account_bonus` |
| **Lab accounts** | Accounts whose `pipeline.md` group is a lab name in `LAB_GROUP_MAP`. Used for the Lab Pulse rollup; bypass engagement floor. Derived at parse time — not hand-edited. | `lab_accounts.anthropic`, `lab_accounts.openai`, etc. |

To customize scoring behavior beyond what `pipeline.md` exposes, edit the quality
filter defaults in `scripts/run.py`.

## Scheduling

Run `scripts/schedule.ps1` to register a Windows Task Scheduler task at 1:00 AM daily.

### Step N: Reflection (composable)

Invoke the `skill-reflection` skill with the following context:

- **Calling skill**: `<skill-name>`
- **SKILL.md path**: `.github/skills/<skill-name>/SKILL.md`
- **Steps completed**: list each step with pass/fail/skipped
- **Friction notes**: any workarounds, retries, unexpected errors, or manual interventions

The reflection skill will analyze the run and produce improvement recommendations.

## Dependencies

- Reuses `last30days` lib modules (xai_x, normalize, score, dedupe)
- Composes with `obsidian` skill for all vault I/O (read, write, search, list files)
- API keys via keyring (`automation/api`), env vars, or `~/.config/last30days/.env` (OPENAI_API_KEY, XAI_API_KEY)
- Python 3.10+ (stdlib only — zero pip dependencies)
- Obsidian must be running with CLI enabled

## Related Skills

- **obsidian** — Vault operations (composed — required)
- **last30days** — Full deep research (use for `#deep-dive` tagged topics)
