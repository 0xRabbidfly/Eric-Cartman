---
name: obsidian-vault-lint
description: Weekly vault structural maintenance inspired by Karpathy's LLM Wiki approach. Cleans broken links, adds missing MOC entries, sorts sections, repairs taxonomy drift (tag case, synonym merges, folder routing), and proposes Topic MOCs for oversized sections. Structure only — semantic work belongs to the metabolism pipeline. Schedule weekly for a self-maintaining knowledge base.
argument-hint: "--dry-run | --phase N | --verbose | --stale-days N"
user-invocable: true
disable-model-invocation: false
metadata:
  author: 0xrabbidfly
  version: "2.0.0"
---

# obsidian-vault-lint

## Purpose

Weekly vault maintenance inspired by [Karpathy's LLM Wiki approach](https://x.com/karpathy) (~16M views, April 2026). Instead of RAG (re-reading raw docs every call), the LLM maintains a *compiled wiki* — incrementally building and cleaning a structured knowledge base.

**Scope: structure, not meaning.** This skill keeps the vault's skeleton clean — links resolve, the MOC matches the filesystem, tags are canonical, notes sit in the right folder. It does no semantic analysis. Anything that requires *reading* a note for what it argues is owned by the metabolism pipeline:

| Semantic concern | Owner |
|---|---|
| Connections between notes (supports / contradicts / extends / bridges) | `obsidian-connection-detector` — runs on every note creation → `connections.json` |
| Thesis clustering, contradiction resolution | `obsidian-thesis-tracker` → `theses.json` |
| Emerging topics, rising tags, cross-domain bridges | `obsidian-weekly-brain` (trend momentum + bridges passes) |
| Corpus synthesis into a report | `obsidian-vault-report` |

**Division of labor within this skill:**
- **Autonomous:** broken link cleanup, MOC coverage, alphabetical sorting, dead-entry removal, tag case normalization, synonym merging
- **Approval-gated (Phase 3 + 4):** folder move proposals, orphaned tag flagging, Topic MOC candidates
- **Human:** curation, judgment on conflicts, deciding what gets its own Topic MOC

**Run time:** ~2-5 min for a 500-note vault. No API calls, no API key, no network — pure filesystem work.

---

## When to Use

- Weekly scheduled maintenance (Sundays 06:00 via Windows Task Scheduler)
- After a heavy ingest week when many new Library notes were added
- When vault-linker audit shows high orphan counts
- When Master MOC feels stale or sections are unsorted
- When tags have drifted (new synonyms, inconsistent casing)

**Do not use this for:** "what's connected to what", "what topics are emerging", "what does my vault think". Those are `obsidian-connection-detector`, `obsidian-weekly-brain`, and `obsidian-vault-report` respectively.

---

## Five Phases

### Phase 1 — Inventory (read-only, always runs)
Collects vault health metrics:
- Orphan count (notes with no incoming links)
- Broken wikilinks pointing to non-existent notes
- Dead-ends in Research/ (no outgoing links)
- Library notes missing from Master MOC
- Stale "Recently Added" MOC entries (>7 days, configurable)
- Similar/duplicate tags (>70% similarity via SequenceMatcher)

### Phase 2 — Autonomous Fixes (safe, reversible writes)
| Fix | Logic | Safety |
|-----|-------|--------|
| Prune stale Recently Added | Remove entries older than `--stale-days` | MOC section only |
| Add missing notes to MOC | Insert under correct folder section, alphabetically | Append-only within sections |
| Sort MOC sections | Re-order wikilinks alphabetically within each `##` section | Preserves all links |
| Fix broken wikilinks | Replace `[[broken-slug]]` with plain text `broken-slug` | One file at a time, logged |

All changes logged to the Phase 5 report. Use `--dry-run` to preview without writing.

### Phase 3 — Taxonomy Repair (tag drift + folder routing)

1. Reads the master MOC's `Canonical Tag Guidance` section to build the authoritative tag list
2. For each note in `Research/Library/` (excluding `00 MOC/`):
   - Reads frontmatter tags
   - Checks if any tags are NOT in the canonical list (flags as orphaned tags)
   - Checks if the note is in the wrong folder based on its tags (e.g., a note tagged `rag` sitting in folder `01` instead of `05`)
3. **Auto-applies** tag normalization:
   - Case fixes: `RAG` → `rag`, `AI-Agents` → `ai-agents`
   - Synonym merges: uses the similar_tags pairs from Phase 1 inventory (>80% similarity) where one tag is canonical and the other is not
4. **Approval-gated** outputs (written to `Research/Logs/vault-lint-YYYY-MM-DD-taxonomy.md`):
   - Folder move proposals with reasoning
   - Orphaned tags not in the canonical list
   - Summary of auto-applied tag fixes

| Action | Autonomous | Approval-gated |
|--------|-----------|----------------|
| Tag case normalization | ✓ | |
| Synonym merge (canonical exists) | ✓ | |
| Folder move proposals | | ✓ |
| Orphaned tag flagging | | ✓ |

Pure string/frontmatter work — no LLM call. Emergent topic detection used to live here and does not any more; `obsidian-weekly-brain` does it better over the whole corpus.

### Phase 4 — MOC Reorganization
**Autonomous:**
- Remove dead MOC entries (wikilinks pointing to deleted notes)
- Deduplicate identical entries within sections

**Approval-gated** (writes proposals file):
- Sections with >12 entries -> propose a new Topic MOC
- Output: `Research/Logs/vault-lint-YYYY-MM-DD-moc-proposals.md`

### Phase 5 — Report
Writes `Research/Logs/vault-lint-YYYY-MM-DD.md` with health metrics, all changes, and links to approval-gated proposal files. Includes the taxonomy repair summary (tag fixes applied).

After the report is written (non-dry-run full runs only), the script automatically commits all vault changes to git with message `vault-lint: automated maintenance {date}`.

---

## CLI Usage

```bash
# Full run (all 5 phases)
python .github/skills/obsidian-vault-lint/scripts/lint.py

# Dry run — preview all changes, nothing written
python .github/skills/obsidian-vault-lint/scripts/lint.py --dry-run

# Run specific phase only
python .github/skills/obsidian-vault-lint/scripts/lint.py --phase 1
python .github/skills/obsidian-vault-lint/scripts/lint.py --phase 2
python .github/skills/obsidian-vault-lint/scripts/lint.py --phase 3
python .github/skills/obsidian-vault-lint/scripts/lint.py --phase 4

# Verbose output (per-item detail)
python .github/skills/obsidian-vault-lint/scripts/lint.py --verbose

# Custom stale threshold (default: 7 days)
python .github/skills/obsidian-vault-lint/scripts/lint.py --stale-days 14
```

---

## Scheduling (Windows Task Scheduler)

Create a scheduled task using an XML definition file for reliable Task Scheduler v1.3 configuration:

```powershell
# Save this XML to a file, then register it
$taskXml = @'
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.3" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Weekly obsidian-vault-lint maintenance run</Description>
    <URI>\obsidian-vault-lint</URI>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2026-04-20T06:00:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByWeek>
        <DaysOfWeek>
          <Sunday />
        </DaysOfWeek>
        <WeeksInterval>1</WeeksInterval>
      </ScheduleByWeek>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>S-1-5-21-1397207858-461175-3826805727-1001</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
    <Priority>7</Priority>
    <RestartOnFailure>
      <Interval>PT5M</Interval>
      <Count>2</Count>
    </RestartOnFailure>
    <UseUnifiedSchedulingEngine>true</UseUnifiedSchedulingEngine>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>python</Command>
      <Arguments>.github/skills/obsidian-vault-lint/scripts/lint.py</Arguments>
      <WorkingDirectory>Z:\Projects\Eric-Cartman</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
'@

# Write XML and register the task
$taskXml | Out-File -FilePath "$env:TEMP\obsidian-vault-lint-task.xml" -Encoding Unicode
Register-ScheduledTask -TaskName "obsidian-vault-lint" -Xml (Get-Content "$env:TEMP\obsidian-vault-lint-task.xml" -Raw)
```

Or register via the `/schedule` skill:
```
/schedule obsidian-vault-lint weekly Sunday 06:00
```

---

## Configuration

None. No env vars, no API keys, no network access — every phase is local filesystem work against the vault.

---

## Vault Constants

These paths match the vault structure discovered during development. Update if your vault structure changes:

```python
MASTER_MOC_PATH = "Research/Library/00 MOC/\U0001f5fa️ MOC - Research Library.md"
LIBRARY_FOLDER  = "Research/Library"
MOC_FOLDER      = "Research/Library/00 MOC"
LOG_FOLDER      = "Research/Logs"
```

---

## Files

```
.github/skills/obsidian-vault-lint/
├── DESIGN.md          — architecture decisions and rationale
├── SKILL.md           — this file
└── scripts/
    ├── __init__.py    — package marker
    ├── lint.py        — main entry point (orchestrator)
    ├── inventory.py   — Phase 1: read-only vault health scan
    ├── fixes.py       — Phase 2: autonomous safe writes
    ├── taxonomy.py    — Phase 3: tag normalization + folder routing
    └── moc.py         — Phase 4: MOC dead-entry cleanup + proposals
```

---

## Dependencies

- Python 3.10+
- `obsidian.py` from `.github/skills/obsidian/scripts/`
- Obsidian 1.12+ running with CLI enabled
- Git (at `C:\Program Files\Git\cmd\git.exe`) — for auto-commit after full runs

---

## Output Files (written to vault)

| File | Phase | Written when |
|------|-------|-------------|
| `Research/Logs/vault-lint-YYYY-MM-DD.md` | 5 | Always (full run) |
| `Research/Logs/vault-lint-YYYY-MM-DD-taxonomy.md` | 3 | When tag fixes, folder moves, or orphaned tags are found |
| `Research/Logs/vault-lint-YYYY-MM-DD-moc-proposals.md` | 4 | When sections exceed 12 entries |

---

## Related Skills

| Skill | Relationship |
|-------|--------------|
| `obsidian-connection-detector` | Owns semantic linking (was this skill's Phase 3 until v2.0.0) |
| `obsidian-thesis-tracker` | Clusters those connections into theses |
| `obsidian-weekly-brain` | Owns emergent topic / rising tag detection (was Phase 2.5 Mode B until v2.0.0) |
| `obsidian-vault-linker` | Graph health audit — feeds the orphan counts this skill reports |
| `obsidian-vault-lint-cowork` | Linux-sandbox fork; still carries the old phase layout |

---

## Friction Rule

> If you hit unexpected errors mid-run:
> 1. Complete the step with a workaround
> 2. Immediately invoke `skill-reflection` with the friction details
> 3. Apply P0/P1 fixes to this SKILL.md now
> 4. Save an Agent Memory
> 5. Continue with remaining phases
