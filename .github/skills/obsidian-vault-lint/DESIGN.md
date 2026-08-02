# obsidian-vault-lint — Design Document

> Status: implemented — v2.0.0
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

## v2.0.0 — Scope Split with the Metabolism Pipeline

The original design gave the lint an LLM-assisted connection-discovery phase (Phase 3)
and, later, an emergent-cluster detector (Phase 2.5 Mode B). Both were built before the
metabolism pipeline existed. Once it did, they were the weaker duplicate:

| Removed | Superseded by | Why the replacement wins |
|---------|---------------|--------------------------|
| Phase 3 — Connection Discovery (`connections.py`) | `obsidian-connection-detector` | Runs on *every note creation* instead of weekly; classifies each edge as supports/contradicts/extends/bridges instead of emitting an unlabelled `[[wikilink]]`; persists to `connections.json` where the thesis tracker can consume it. The lint version only ever looked at the top-20 orphans and required a manual `--phase 3 --apply` round trip. |
| Phase 2.5 Mode B — Emergent Clusters | `obsidian-weekly-brain` (trend momentum + cross-domain bridges) | Reasons over the whole corpus with an LLM rather than counting shared tag *pairs* among the last 30 days of notes, and does not depend on `date_saved` frontmatter being present. |

The resulting boundary is worth stating plainly, because it is what keeps the two
systems from re-growing into each other:

> **The lint touches structure. The metabolism pipeline touches meaning.**
> If a decision requires reading a note for what it argues, it does not belong here.

Practical consequences:
- The lint no longer makes network calls and needs no xAI key. It cannot fail on a
  rate limit, a model deprecation, or an expired credential.
- Phase numbering is now contiguous: 2.5 became Phase 3, and Phases 4/5 kept their
  numbers. `--phase 2.5` and `--apply` are gone.
- The proposals file `vault-lint-YYYY-MM-DD-backprop.md` is now
  `vault-lint-YYYY-MM-DD-taxonomy.md`. Older files stay as historical logs; nothing
  reads them back.

`obsidian-vault-lint-cowork` has not been re-split — it still carries the pre-2.0
phase layout.

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

## Phase 3 — Taxonomy Repair (autonomous fixes + proposals)

For every note in `Research/Library/` (excluding `00 MOC/`):

1. Read the master MOC's `Canonical Tag Guidance` section for the authoritative tag list
2. Parse the note's frontmatter tags
3. **Auto-apply** tag case normalization (`RAG` → `rag`) and synonym merges, using the
   >0.8-similarity pairs from Phase 1 where exactly one side is canonical
4. **Propose** a folder move when the note's tags score higher against a different
   library bucket than the one it sits in
5. **Flag** tags absent from the canonical list

Output: `Research/Logs/vault-lint-YYYY-MM-DD-taxonomy.md` (folder moves and orphaned tags
for review; applied tag fixes listed for the record)

No LLM call — pure frontmatter and string work.

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
- vault-lint-YYYY-MM-DD-taxonomy.md (5 folder move proposals)
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
python scripts/lint.py --phase 3   # taxonomy repair only

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

## Files

```
.github/skills/obsidian-vault-lint/
├── DESIGN.md          ← this file
├── SKILL.md
└── scripts/
    ├── lint.py        ← main entry point
    ├── inventory.py   ← Phase 1 (wraps existing audit scripts)
    ├── fixes.py       ← Phase 2 (autonomous writes)
    ├── taxonomy.py    ← Phase 3 (tag normalization + folder routing)
    └── moc.py         ← Phase 4 (MOC reorganization)
```

---

## Dependencies

- Python 3.10+
- `obsidian.py` (via `.github/skills/obsidian/scripts/obsidian.py`)
- Existing audit scripts in `obsidian-vault-linker/scripts/` for Phase 1 reuse

No API keys and no network access as of v2.0.0.

---

## Open Questions

1. Threshold for "stale" Recently Added entries — 7 days or configurable?
2. Should the report be appended to the daily note or always a standalone log?
3. Conflict resolution: what if a note belongs in two MOC sections?
4. Should Phase 4's Topic MOC proposals defer to `obsidian-weekly-brain`'s topic
   analysis, or is section size a purely structural signal that belongs here?
