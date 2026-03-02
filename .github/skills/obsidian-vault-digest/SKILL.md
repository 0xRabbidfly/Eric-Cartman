---
name: obsidian-vault-digest
description: Scan the Obsidian vault for everything related to a topic and produce a synthesized briefing with citations. Use before writing, researching, or making decisions — to leverage everything you've already captured.
user-invokable: true
argument-hint: "topic or question to synthesize from vault"
disable-model-invocation: true
metadata:
  author: 0xrabbidfly
  version: "1.0.0"
---

# Obsidian Vault Digest

## Purpose

Before you write, research, or decide anything — ask your vault first. This skill searches your entire Obsidian vault for everything related to a topic, reads the matching notes, and produces a **synthesized briefing** with citations back to source notes.

From the article: _"Before Claude writes anything, it launches sub-agents that scan my vault. It finds related Galaxy notes, past newsletters on the topic, previous content pieces, and existing outlines. The result is that content gets built on everything I've ever thought and written, not from a blank page."_

This is the **"what do I already know about X?"** skill.

## When to Use

- Before starting a writing project — find all prior thinking on the topic
- Before a meeting or decision — get a briefing from your own notes
- When you can't remember where you wrote about something
- To find contradictions in your own thinking across notes
- To generate a reading list from your vault on a theme
- When you say: "what do I know about X?", "digest my notes on X", "vault briefing on X", "synthesize X from my vault"

## Prerequisites

- Obsidian must be running with CLI enabled
- Uses the `obsidian.py` wrapper (`.github/skills/obsidian/scripts/obsidian.py`)

---

## Workflow

### Phase 1: Vault Search

Cast a wide net using multiple search strategies:

```powershell
# Direct keyword search
python .github/skills/obsidian/scripts/obsidian.py run search --query "TOPIC" --format json

# Search with context (surrounding lines)
python .github/skills/obsidian/scripts/obsidian.py run search --query "TOPIC" --context --format json

# Tag-based search (if topic maps to a tag)
python .github/skills/obsidian/scripts/obsidian.py run tag-info --tag "TOPIC-TAG" --format json

# Search in specific high-value folders
python .github/skills/obsidian/scripts/obsidian.py run search --query "TOPIC" --path "Research" --format json
python .github/skills/obsidian/scripts/obsidian.py run search --query "TOPIC" --path "Projects" --format json
```

Also search for **synonyms, related terms, and adjacent concepts** — not just the exact keyword. If the topic is "machine learning", also search for "ML", "neural network", "deep learning", "model training", etc.

### Phase 2: Note Reading & Relevance Scoring

For each matched note, read the full content:

```powershell
python .github/skills/obsidian/scripts/obsidian.py read --path "path/to/note.md"
```

Score each note for relevance:

| Score | Criteria |
|-------|----------|
| **5 — Core** | Entire note is about this topic |
| **4 — Major** | Significant section dedicated to topic |
| **3 — Related** | Topic mentioned in meaningful context |
| **2 — Tangential** | Brief mention, useful for breadth |
| **1 — Noise** | Keyword match but not relevant → discard |

Keep notes scoring 3+. Include 2s only if the user asked for a broad digest.

### Phase 3: Synthesis

Organize the extracted knowledge into a structured briefing:

```markdown
## Vault Digest: {Topic}

**Generated**: YYYY-MM-DD | **Sources**: X notes | **Vault**: {name}

### Executive Summary
{3-5 sentence synthesis of everything the vault contains on this topic.
This should read like a briefing — not a list of notes.}

### Key Themes

#### Theme 1: {Theme Name}
{Synthesized narrative drawing from multiple notes}

- {Insight from [[Note A]]}
- {Insight from [[Note B]]}
- {Contrasting view from [[Note C]]}

> "Direct quote from note if particularly well-stated" — [[Source Note]]

#### Theme 2: {Theme Name}
...

#### Theme 3: {Theme Name}
...

### Contradictions & Open Questions
{Places where your notes disagree with each other, or questions you've
asked but never answered. This section is often the most valuable.}

- [[Note A]] suggests X, but [[Note B]] argues Y
- Open question from [[Note C]]: "How does this apply to...?"

### Evolution of Thinking
{If notes span a time range, trace how your thinking evolved}

- **Early** (YYYY-MM): Initially believed X ([[Note]])
- **Later** (YYYY-MM): Shifted to Y after ([[Note]])
- **Current**: Where you stand now

### Source Notes (ranked by relevance)

| # | Note | Relevance | Key Contribution |
|---|------|-----------|-----------------|
| 1 | [[Note A]] | ⭐⭐⭐⭐⭐ | Core framework for understanding X |
| 2 | [[Note B]] | ⭐⭐⭐⭐ | Practical example of X in production |
| 3 | [[Note C]] | ⭐⭐⭐ | Counter-argument worth considering |
| ... | | | |

### Gaps
{Topics adjacent to this one that you have NO notes on — potential research areas}

- No notes found on: [related topic 1], [related topic 2]
```

### Phase 4: Delivery

**Default**: Print the digest to the terminal for immediate use.

**Optional — Save to vault**:
```powershell
@'
{digest content}
'@ | python .github/skills/obsidian/scripts/obsidian.py create --path "Research/Digests/{topic}-digest-{date}.md"
```

**Optional — Append to daily note**:
```powershell
@'

## Vault Digest: {Topic}
{abbreviated version — summary + source links only}
'@ | python .github/skills/obsidian/scripts/obsidian.py run daily-append
```

---

## Modes

### Brief Mode
Summary + source list only. Fast. For quick "do I have anything on this?" checks.

```
Quick check — what do I have on "cataract surgery" in my vault? Use obsidian-vault-digest.
```

### Deep Mode (default)
Full synthesis with themes, contradictions, evolution, and gaps.

```
Give me a deep digest on "agentic workflows" from my vault.
```

### Writing Prep Mode
Optimized for feeding into a writing project. Outputs themes as potential sections, quotes as potential pull-quotes, gaps as areas needing research.

```
I'm writing about AI second brains — digest everything in my vault as writing prep.
```

---

## Rules

- **Cite everything.** Every claim in the digest links back to a `[[Source Note]]`.
- **Synthesize, don't summarize.** A digest is NOT a list of note summaries. It's a narrative that connects ideas across notes.
- **Surface contradictions honestly.** Don't smooth over disagreements in the vault — they're valuable.
- **Respect note boundaries.** Don't modify source notes. The digest is a new artifact.
- **Be transparent about coverage.** State how many notes were searched and how many matched.
- **Time-aware.** If notes have dates, use them to show thinking evolution.

---

## Example Invocations

```
What do I already know about RAG architectures? Digest my vault. Use obsidian-vault-digest.
```

```
I'm preparing for a meeting on our search strategy — give me a vault briefing.
```

```
Digest everything I've captured about Claude Code and Obsidian workflows — deep mode.
```

```
Writing prep mode: I need to write about knowledge management. What's in my vault?
```

---

## Related Skills

- `obsidian` — The composable vault wrapper this skill depends on
- `obsidian-vault-linker` — Strengthens connections; vault-digest reads them
- `content-research-writer` — Uses external sources; vault-digest uses internal ones
- `obsidian-daily-research` — Captures new content; vault-digest synthesizes existing content
- `session-skill-forge` — If you find yourself digesting the same topic often, forge a dedicated skill

