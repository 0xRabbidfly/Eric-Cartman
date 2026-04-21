# obsidian-vault-lint — Design Document

> Status: draft — pending implementation
> Informed by: Karpathy's LLM Wiki approach (April 2026, ~16M views on X)

---

## Background: Karpathy's LLM Wiki Approach

**Core insight**: instead of RAG (LLM re-reads raw docs every time), maintain a *compiled wiki* — the LLM incrementally builds and maintains a structured markdown knowledge base. Key files: `index.md` (catalog), `log.md` (timeline), entity/concept pages.

**The lint operation** is explicit in his architecture:
> Run every 2-4 weeks, ~10 min. Finds orphan pages, contradictions, stale claims, missing concept pages, broken cross-references.

**Division of labor**:
- LLM handles: cross-referencing, link maintenance, orphan detection, index updates, contradiction flagging
- Human handles: curation, judgment on conflicts, deciding what deserves its own page

**What we already have** maps almost exactly to this — the daily research pipeline = his ingest loop, vault-linker = his lint analysis. The gap is **automated action-taking + scheduling**.

---

## Architecture Overview

Five phases, two modes:
- **Autonomous** — runs unattended, makes safe reversible changes
- **Approval-gated** — produces a diff/proposal file for human review before applying

---

## Phase 1 — Inventory (read-only, always runs)

Reuses `vault_audit_phase2.py` / `vault_audit_phase3.py` as a library. Collects:

- Orphan count + list (no incoming links) — via `ob.orphans()`
- Broken wikilinks pointing to non-existent notes — via `ob.unresolved()`
- Dead-ends in `Research/` (no outgoing links) — via `ob.deadends()`
- Notes in `Research/Library/` missing from Master MOC
- Stale "Recently Added" entries in Master MOC (>7 days old)
- Duplicate/similar tags (SequenceMatcher >0.7, already implemented in phase3)

---

## Phase 2 — Autonomous Fixes (writes, no approval needed)

All changes are logged to the lint report. Supports `--dry-run` to preview without writing.

| Fix | Logic | Safety |
|-----|-------|--------|
| Prune stale MOC "Recently Added" entries | Remove entries older than 7 days | MOC section only, never body |
| Add missing notes to Master MOC | Append under correct numbered folder section, alphabetical insert | Append-only |
| Remove broken wikilinks | Replace `[[broken-slug]]` with plain text `broken-slug` | One note at a time, logged |
| Sort MOC sections alphabetically | Re-order wikilinks within each section | Preserves all links |

---

## Phase 3 — Connection Discovery (LLM-assisted, produces diff for approval)

For the top-20 orphaned Library notes:

1. `ob.search_context(note_title)` to find related notes by content
2. Call xAI API (same key as `obsidian-daily-research`) to score semantic relevance:
   > "Given this note's summary and these candidate notes, which 3 are most related and why?"
3. Output proposed `[[wikilink]]` blocks to append to each orphan's "Related" section

Output: `Research/Logs/vault-lint-YYYY-MM-DD-connections.md` (diff-style, human reviews before applying)

Can also run standalone: `--phase 3 --apply` after review.

---

## Phase 4 — MOC Reorganization

**Autonomous (safe):**
- Remove wikilinks pointing to notes that no longer exist (dead MOC entries)
- Re-sort entries within sections alphabetically
- Deduplicate identical entries in the same section

**Approval-gated (produces proposals):**
- Any Master MOC section with >12 entries → propose a new Topic MOC (e.g. like existing `🤖 MOC - AI Agent Development.md`)
- Suggest folder structure + seed notes for the candidate Topic MOC
- Output: `Research/Logs/vault-lint-YYYY-MM-DD-moc-proposals.md`

---

## Phase 5 — Report & Notification

Writes `Research/Logs/vault-lint-YYYY-MM-DD.md`:

```markdown
# Vault Lint — YYYY-MM-DD

## Health Metrics
- Orphans: 47 → 31 (16 connected this run)
- Broken links fixed: 4
- Missing from Master MOC: 8 added
- Stale MOC entries pruned: 3
- Duplicate tags flagged: 2

## Autonomous Changes
- [list of every write with note path + change type]

## Pending Review
- vault-lint-YYYY-MM-DD-connections.md (16 proposed links)
- vault-lint-YYYY-MM-DD-moc-proposals.md (1 new Topic MOC candidate)
```

Optionally sends a Telegram push notification on completion (same pattern as daily-research).

---

## CLI Interface

```bash
# Full run (all phases, autonomous writes, proposals for approval-gated)
python scripts/lint.py

# Dry run — preview all changes, no writes
python scripts/lint.py --dry-run

# Run specific phase only
python scripts/lint.py --phase 1
python scripts/lint.py --phase 3 --apply   # apply connection proposals after review

# Verbose output
python scripts/lint.py --verbose
```

---

## Scheduling

Use the `schedule` skill to register as a weekly cron (Sundays, 06:00):

```
/schedule obsidian-vault-lint weekly Sunday 06:00
```

Or add to `.github/skills/remote-skills-api/` routes so it can be triggered from mobile.

---

## Files to Create

```
.github/skills/obsidian-vault-lint/
├── DESIGN.md          ← this file
├── SKILL.md           ← to be written after implementation
└── scripts/
    ├── lint.py        ← main entry point
    ├── inventory.py   ← Phase 1 (wraps existing audit scripts)
    ├── fixes.py       ← Phase 2 (autonomous writes)
    ├── connections.py ← Phase 3 (LLM-assisted link discovery)
    └── moc.py         ← Phase 4 (MOC reorganization)
```

---

## Dependencies

- Python 3.10+
- `obsidian.py` (via `.github/skills/obsidian/scripts/obsidian.py`)
- xAI API key (keyring: `automation/xai`, key: `api_key`) — Phase 3 only
- Existing audit scripts in `obsidian-vault-linker/scripts/` for Phase 1 reuse

---

## Open Questions

1. Should Phase 3 LLM calls batch notes or process one at a time? (cost vs. latency)
2. Threshold for "stale" Recently Added entries — 7 days or configurable?
3. Should the report be appended to the daily note or always a standalone log?
4. Conflict resolution: what if a note belongs in two MOC sections?
