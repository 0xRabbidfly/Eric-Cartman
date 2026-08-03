# Daily Research Pipeline Config

> Single config file for the daily research pipeline.
> Edit sections below to customize topics, accounts, and settings.
> Lines starting with `>` are comments. Blank lines are ignored.
> To disable an item temporarily, comment it out with `>`.

---

# Topics

> Research topics scanned daily. Format: `- slug | Display Name | weight`
> Weight controls score multiplier (default 1.0). Higher = more prominent.

- agents | Agent Development | 1.2
- harness | LLM Harness Engineering & Agent Scaffolding | 1.1
- adlc | Agentic Development Lifecycle | 1.1
- sdd | Spec Driven Development & AI frameworks | 1.0
- sdlc | Software development lifecycle & AI | 0.9


---

# Must-Follow Accounts

> **Only accounts in a lab group are scanned.** A group whose name is in
> `LAB_GROUP_MAP` (`scripts/run.py`) — Anthropic, OpenAI, Google, SpaceXAI,
> Mistral, Meta, Moonshot — gets a dedicated X search, batched in chunks of 10,
> with no engagement floor. Those results feed the **Lab Pulse** section.
>
> Accounts in non-lab groups (Thought Leaders, Researcher, Tool Builder) are
> **not scanned**. They still earn their place here: every handle on this list
> bypasses the topic-scan engagement floor and gets a +20 relevance boost, so
> deleting them would quietly degrade topic-scan ranking. They reach the note via
> Prominent Voices, which covers them at 500+ likes.
>
> **Format:** `- @handle — Display Name`, plus `(org)` for official company or
> product accounts. Only `(org)` accounts feed the **Lab Pulse** rollup; people at
> those same labs render under **Prominent Voices**, bypassing its 500-like floor
> because the lab scan has no floor. The split matters: measured over 14 days,
> every sub-500 post came from an org account, while every researcher post
> cleared 500.
>
> To disable an account, comment it out with `>`. There is no `(solo)` flag —
> everything batches.

## Thought Leaders

- @karpathy — Andrej Karpathy
- @elonmusk — Elon Musk, founder of xAI / SpaceX / Tesla

## Researcher

- @emollick — Ethan Mollick, Wharton professor on AI adoption in real workflows

## Tool Builder

- @theo — Theo Browne (t3.gg), coding agents / MCP / editor tooling
- @mntruell — Michael Truell, Cursor

## Anthropic

- @bcherny — Boris
- @trq212 - Thariq
- @DarioAmodei — Dario Amodei
- @AnthropicAI — Anthropic (org)
- @claudedevs — ClaudeDevs (org)

## OpenAI

- @OpenAI — OpenAI (org)
- @sama — Sam Altman
- @gdb — Greg Brockman, OpenAI co-founder and president

## Google

- @GoogleDeepMind — Google DeepMind (org)
- @JeffDean — Jeff Dean

## SpaceXAI

> @xai is dead post-SpaceXAI merger — @SpaceXAIMemphis is the live official
> handle, and the one that carries lab/facility content over product marketing.
- @SpaceXAIMemphis — SpaceXAI Memphis, lab / facility content (org)

## Mistral

- @MistralAI — Mistral AI (org)

## Meta

- @MetaAI — Meta AI (org)

## Moonshot

- @kimi_moonshot — Moonshot AI, Kimi long-context / agentic models (org)

---

# Settings

> Key-value pairs. Format: `- key: value`
> Only override what you need — defaults are sensible.

- vault_path: ~/Documents/Obsidian Vault
- dailies_folder: Research/Dailies
- library_folder: Research/Library
- items_per_topic: 8
- reading_list_max: 15
- depth: scan
- prominent_ai_min_likes: 500
> Long-form articles linked from the day's posts are judged by the synthesis call
> and the best are written to Research/Library via the obsidian-linked-research
> skill. The bar is deliberately high — a primary source worth re-reading in three
> months — so an empty pick is the normal outcome. This caps how many run per day;
> each is a Claude CLI subprocess that can take minutes. Set to 0 to disable.
- auto_capture_max: 3
> xai_model is PINNED, not `auto`. Auto-resolution picks the highest grok version
> number with no price check, which moved the pipeline onto grok-4.5 on 2026-08-02
> — 8.1x the per-call cost of 4.3 ($0.021 -> $0.173) at an unchanged call count,
> taking projected spend from ~$11/mo to $88/mo. Search does not need the newer
> model; analysis runs on Claude CLI. Re-check before changing this.
- xai_model: grok-4.3
> Analysis (POW briefing, lab pulse summary, news scoring) runs on Claude CLI,
> which is free on a Max account. This model is only the fallback for when the
> CLI is unavailable — a judgment task, so it gets the stronger model even
> though search does not.
- xai_synthesis_model: grok-4.5

# Auto-Capture Accounts

> Tweets from these accounts that contain article/blog URLs are automatically
> captured as Research Library notes via the obsidian-linked-research skill.
> No #keep tag needed — articles are ingested immediately.
> Format: `- @handle`

- @claudedevs
