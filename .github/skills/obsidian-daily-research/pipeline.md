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
- skills | LLM Agent Skills & AI Developer Tools | 1.1
- models | Frontier Model Releases | 1.0
- sdd | Spec Driven Development & AI frameworks | 1.0
- sdlc | Software development lifecycle & AI | 0.9


---

# Must-Follow Accounts

> Every tweet from these accounts is captured — no engagement floor.
> All original posts are included regardless of like count.
>
> **Format:** `- @handle — Display Name` or `- @handle — Display Name (solo)`
> Append `(solo)` to give an account its own dedicated API call.
> `##` headers group accounts in the daily note — but some names are functional.
> A group named after a lab (`Anthropic`, `OpenAI`, `Google`, `Meta`, `Mistral`,
> `SpaceXAI`, `Moonshot` — see `LAB_GROUP_MAP` in `scripts/run.py`) marks its accounts
> as speaking for that lab: they bypass the engagement floor and are promoted into
> the **Lab Pulse** section. Any other group name is display-only. So use org
> groups for lab voices, role groups (Thought Leaders, Researcher, Tool Builder)
> for the commentary layer — and add a `LAB_GROUP_MAP` entry when adding a new lab.
> To disable an account, comment it out with `>`.

## Thought Leaders

- @karpathy — Andrej Karpathy (solo)
- @swyx — Swyx / Latent Space (solo)
- @elonmusk — Elon Musk, founder of xAI / SpaceX / Tesla (solo)

## Researcher

- @emollick — Ethan Mollick, Wharton professor on AI adoption in real workflows (solo)

## Tool Builder

- @theo — Theo Browne (t3.gg), coding agents / MCP / editor tooling (solo)
- @mntruell — Michael Truell, Cursor (solo)

## Anthropic

- @bcherny — Boris (solo)
- @trq212 - Thariq (solo)
- @DarioAmodei — Dario Amodei (solo)
- @AnthropicAI — Anthropic
- @claudedevs — ClaudeDevs (solo)

## OpenAI

- @OpenAI — OpenAI
- @sama — Sam Altman (solo)
- @gdb — Greg Brockman, OpenAI co-founder and president (solo)

## Google

- @GoogleDeepMind — Google DeepMind
- @JeffDean — Jeff Dean (solo)

## SpaceXAI

> @xai is dead post-SpaceXAI merger — @SpaceXAIMemphis is the live official
> handle, and the one that carries lab/facility content over product marketing.
- @SpaceXAIMemphis — SpaceXAI Memphis, lab / facility content (solo)

## Mistral

- @MistralAI — Mistral AI

## Meta

- @MetaAI — Meta AI

## Moonshot

- @kimi_moonshot — Moonshot AI, Kimi long-context / agentic models (solo)

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
- xai_model: auto

# Auto-Capture Accounts

> Tweets from these accounts that contain article/blog URLs are automatically
> captured as Research Library notes via the obsidian-linked-research skill.
> No #keep tag needed — articles are ingested immediately.
> Format: `- @handle`

- @claudedevs
