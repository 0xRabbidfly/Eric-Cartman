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
- skills | Agent Skills & Tools | 1.1
- models | Frontier Model Releases | 1.0
- mcp | MCP & Tool Use | 1.0
- rag | RAG & AI Search | 0.9

---

# Must-Follow Accounts

> Every tweet from these accounts is captured — no engagement filter, no quality
> filter. Corp accounts are batched into one API call. Individual accounts get
> dedicated solo calls for maximum reliability.
>
> **Format:** `- @handle — Display Name` or `- @handle — Display Name (solo)`
> Append `(solo)` to give an account its own dedicated API call.
> `##` headers are org groups (used for display grouping in the daily note).
> To disable an account, comment it out with `>`.

## Thought Leaders

- @karpathy — Andrej Karpathy (solo)
- @swyx — Swyx / Latent Space (solo)

## Cursor

- @mntruell — Michael Truell (solo)

## Anthropic

- @bcherny — Boris (solo)
- @trq212 - Thariq (solo)
- @DarioAmodei — Dario Amodei (solo)
- @AnthropicAI — Anthropic

## OpenAI

- @OpenAI — OpenAI
- @sama — Sam Altman (solo)

## Google

- @GoogleDeepMind — Google DeepMind
- @JeffDean — Jeff Dean (solo)

## xAI

- @xaborai — xAI

## Mistral

- @MistralAI — Mistral AI

## Meta

- @MetaAI — Meta AI

---

# Discovery Accounts

> Broader builder/practitioner accounts scanned in a SINGLE batch API call.
> Topic-agnostic — captures any post, not just keyword matches.
> This bridges the gap between must-follow (every tweet tracked) and
> keyword search (misses emerging vocabulary and cross-topic content).
> Think of these as "accounts whose tweets I'd stop scrolling to read."
>
> **Format:** `- @handle — Display Name`
> These are always batched (max 10 per API call). No (solo) option.

- @systematicls — sysls (agentic engineering)
- @Hxlfed14 — Himanshu (agent harness deep dives)
- @tanayj — Tanay Jaipuria (AI strategy / moats)
- @ankitxg — Ankit Jain (Aviator / AI eng practices)
- @hardmaru — David Ha (Sakana AI)
- @DrJimFan — Jim Fan (NVIDIA)
- @simonw — Simon Willison (AI tooling / pragmatist)
- @eugeneyan — Eugene Yan (applied AI)

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
