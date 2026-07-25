---
name: obsidian-vault-report
description: Generate synthesis reports from the Obsidian vault corpus. Use when user says "write a report", "research paper", "strategy doc", "synthesize", "what does our vault say about X", or any request to analyze and combine knowledge from existing vault notes into a new document.
argument-hint: write a report on X, synthesize findings about Y, strategy paper on Z
user-invocable: true
disable-model-invocation: true
metadata:
  author: 0xrabbidfly
  version: "1.0.0"
---

# Vault Report Generator

## Purpose

Mines the Obsidian vault corpus (Library, Dailies, Podcasts) to synthesize structured reports that connect, analyze, and distill existing knowledge. Reports are first-class vault citizens — wikilinked to source notes, tagged, and registered in the Master MOC.

## When to Use

| Trigger | Action |
|---------|--------|
| "write a report on X" | Full synthesis — search, read, analyze, write |
| "what does our vault say about X" | Quick synthesis — lighter analysis |
| "strategy paper on X" | Full synthesis with recommendations |
| "find contradictions about X" | Contradiction-focused analysis |
| Auto-triggered by obsidian-thesis-tracker | Draft report from accumulated evidence |

## Pipeline

1. **SEARCH** — Query the vault using the obsidian skill's search. Cast a wide net: search by keywords, tags, and related concepts. Target `Research/Library/`, `Research/Dailies/`, `Podcasts/`.
2. **READ** — Read all matching notes. Extract key claims, data points, quotes, and source metadata.
3. **ANALYZE** — Identify patterns, contradictions, supporting evidence, gaps in knowledge. Group findings by theme.
4. **SYNTHESIZE** — Write the report following the template below.
5. **LINK** — Add wikilinks to every source note cited. Add a `## Sources` section with full vault links.
6. **WRITE** — Save to `Research/Reports/<slug>.md` using the obsidian skill or direct filesystem write.
7. **REGISTER** — Update the Master MOC's Reports section (create it if it doesn't exist).

## Report Template

````markdown
---
type: report
status: draft
tags: [report, <topic-tags>]
created: YYYY-MM-DDTHH:MM:SSZ
sources: <count>
query: "<original research question>"
---

**Query:** <research question>
**Sources:** <N> vault notes analyzed
**Date:** YYYY-MM-DD
---

> [!abstract]+ Executive Summary
> 3-5 sentence synthesis of key findings.

---

## Key Findings

1. **Finding 1** — explanation with [[wikilink to source note]]
2. **Finding 2** — explanation with [[wikilink to source note]]
...

## Analysis

### Theme 1
Multi-paragraph analysis connecting multiple sources...

### Theme 2
...

## Contradictions & Open Questions

- Contradiction between [[note A]] and [[note B]]: ...
- Open question: ...

## Recommendations
1. Actionable recommendation
2. ...

## Knowledge Gaps

What the vault does NOT cover that would strengthen this analysis.

## Sources

| Note | Section | Key Claim |
|------|---------|-----------|
| [[note-slug]] | Key Ideas #3 | "claim text" |
| ... | ... | ... |
````

## Quality Bar

- Reports should be analytical, not summarative — add perspective the individual notes don't have
- Every claim must link to its source note
- Contradictions are valuable — surface them prominently
- Knowledge gaps are valuable — they tell the user what to research next
- The executive summary should be standalone — readable without the full report

## Dependencies

- Composes with **obsidian** skill for vault search and I/O
- Uses xAI API (grok-4.3) for synthesis if needed, but the agent should do most of the analysis itself
- Reports folder: `Research/Reports/`

## Related Skills

- **obsidian-connection-detector** — detects relationships between notes
- **obsidian-thesis-tracker** — auto-triggers reports when evidence accumulates
- **obsidian-linked-research** — imports external content (this skill synthesizes internal content)