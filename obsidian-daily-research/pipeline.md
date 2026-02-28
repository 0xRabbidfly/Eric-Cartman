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

## Anthropic

- @bcherny — Boris (solo)
- @alexalbert__ — Alex Albert (solo)
- @DarioAmodei — Dario Amodei (solo)
- @AnthropicAI — Anthropic

## OpenAI

- @OpenAI — OpenAI
- @sama — Sam Altman (solo)
- @markchen90 — Mark Chen (solo)

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

# Settings

> Key-value pairs. Format: `- key: value`
> Only override what you need — defaults are sensible.

- vault_path: ~/Documents/Obsidian Vault
- dailies_folder: Research/Dailies
- library_folder: Research/Library
- items_per_topic: 8
- reading_list_max: 15
- depth: scan
