---
name: obsidian-vault-linker
description: Discover missing links, orphaned notes, thematic clusters, and connection opportunities across the Obsidian vault. Use when your knowledge base feels fragmented or you suspect hidden connections between notes.
user-invokable: true
disable-model-invocation: true
metadata:
  author: 0xrabbidfly
  version: "1.0.0"
---

# Obsidian Vault Linker

## Purpose

Analyze the Obsidian vault to surface **hidden connections** between notes — missing bidirectional links, thematic clusters, orphaned content, and linking opportunities the user hasn't noticed.

From the article: _"It finds notes that should be linked to each other but aren't... surfaces thematic connections across years of notes instantly, finding clusters of ideas I had forgotten I'd written about."_

This is the **knowledge gardening** skill — it doesn't create new content, it strengthens the connective tissue of your existing knowledge base.

## When to Use

- Vault has grown organically and linking has been inconsistent
- After importing a batch of new notes
- You want to discover thematic clusters you've forgotten
- Before a writing project — find everything related to a topic
- Periodic vault hygiene (monthly)
- When you say: "find missing links", "what's connected?", "link my vault", "vault audit"

## Prerequisites

- Obsidian must be running with CLI enabled
- Uses the `obsidian.py` wrapper (`.github/skills/obsidian/scripts/obsidian.py`)

---

## Workflow

### Phase 1: Vault Reconnaissance

Gather structural data about the vault:

```powershell
# Get vault info
python .github/skills/obsidian/scripts/obsidian.py info

# List all files
python .github/skills/obsidian/scripts/obsidian.py run files --format json

# Get orphaned notes (no incoming or outgoing links)
python .github/skills/obsidian/scripts/obsidian.py run orphans --format json

# Get unresolved links (broken references)
python .github/skills/obsidian/scripts/obsidian.py run unresolved --format json

# Get dead-end notes (no outgoing links)
python .github/skills/obsidian/scripts/obsidian.py run deadends --format json

# Get all tags with counts
python .github/skills/obsidian/scripts/obsidian.py run tags --format json
```

Record:
- Total note count
- Orphan count and list
- Unresolved link count
- Dead-end count
- Tag distribution

### Phase 2: Thematic Cluster Detection

For a user-specified topic (or the top 5 tags by count):

```powershell
# Search for thematic content
python .github/skills/obsidian/scripts/obsidian.py run search --query "TOPIC" --format json

# Get context around matches
python .github/skills/obsidian/scripts/obsidian.py run search --query "TOPIC" --context --format json
```

For each cluster found:
1. Read the relevant notes to understand their content
2. Identify notes that discuss the same concept but don't link to each other
3. Identify notes that would benefit from a new **MOC (Map of Content)** note

### Phase 3: Link Opportunity Analysis

For each pair of notes that should be linked:

| Field | Value |
|-------|-------|
| Note A | `path/to/note-a.md` |
| Note B | `path/to/note-b.md` |
| Relationship | [semantic similarity / shared concept / continuation / contrast / evidence] |
| Confidence | [High / Medium / Low] |
| Suggested link text | `See also [[Note B]] for ...` |

### Phase 4: Report Generation

Produce a structured linking report:

```markdown
## Vault Link Analysis Report

**Vault**: [name] | **Notes**: X | **Date**: YYYY-MM-DD

### Health Metrics
| Metric | Count | Status |
|--------|-------|--------|
| Total notes | X | — |
| Orphaned notes | X | 🔴 / 🟡 / 🟢 |
| Unresolved links | X | 🔴 / 🟡 / 🟢 |
| Dead-end notes | X | 🟡 |
| Avg links per note | X | — |

### 🔗 Missing Link Opportunities (Top 20)

1. **[[Note A]]** ↔ **[[Note B]]**
   - Relationship: Both discuss [concept]
   - Confidence: High
   - Suggested: Add `See also [[Note B]]` to Note A's "Related" section

2. ...

### 🏝️ Orphaned Notes Worth Connecting

1. **[[Orphan Note]]** — discusses [topic], could link to [[X]], [[Y]]
2. ...

### 🗺️ Suggested MOC (Map of Content) Notes

1. **[[MOC - Topic Name]]** — would connect: [[A]], [[B]], [[C]], [[D]]
   - These 4 notes all discuss [theme] but have zero cross-links
2. ...

### 🔴 Broken Links (Unresolved)

1. `[[Non-existent Note]]` referenced in [[Source Note]]
   - Suggestion: Create the note / Fix the link to [[Correct Name]]
2. ...

### 🏷️ Tag Cleanup Opportunities

1. Tags `#topic-a` (12 uses) and `#topicA` (3 uses) appear to be duplicates
2. Tag `#old-project` (8 uses) — all notes are from 2024, consider archiving
```

### Phase 5: Apply Links (with user approval)

After user reviews the report:

```powershell
# Append a "Related" section to a note
@'

## Related

- [[Note B]] — shared concept on [topic]
- [[Note C]] — contrasting view on [topic]
'@ | python .github/skills/obsidian/scripts/obsidian.py append --path "path/to/note-a.md"
```

Only apply links the user explicitly approves. Never silently modify notes.

---

## Modes

### Quick Mode (default)
Scoped to a single topic or folder. Fast, focused.

```
Find missing links about "machine learning" in my vault. Use obsidian-vault-linker.
```

### Full Audit Mode
Whole-vault analysis. Takes longer, produces comprehensive report.

```
Run a full vault link audit. Use obsidian-vault-linker.
```

---

## Rules

- **Read-only by default.** Never modify notes without explicit user approval.
- **Confidence thresholds.** Only suggest High/Medium confidence links. Skip speculative ones.
- **Respect vault structure.** Don't suggest flattening folders or reorganizing — just linking.
- **Use Obsidian link syntax.** Always `[[Note Name]]` or `[[path/to/note|Display Text]]`.
- **Limit output.** Cap at 20 link suggestions per run. User can ask for more.

---

## Example Invocations

```
Find hidden connections in my vault about "agentic workflows". Use obsidian-vault-linker.
```

```
Which of my notes are orphaned and should be connected? Use vault-linker.
```

```
Run a full vault link audit and show me what's disconnected.
```

---

## Related Skills

- `obsidian` — The composable vault wrapper this skill depends on
- `obsidian-vault-digest` — Reads vault content for synthesis; vault-linker strengthens the graph
- `obsidian-daily-research` — Creates new notes; vault-linker connects them to existing ones

