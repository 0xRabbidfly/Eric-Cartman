---
name: obsidian-vault-lint
description: Weekly vault maintenance pipeline inspired by Karpathy's LLM Wiki approach. Cleans broken links, adds missing MOC entries, sorts sections, discovers orphan connections via xAI, repairs taxonomy drift, detects emergent topic clusters, and proposes Topic MOCs for oversized sections. Schedule weekly for a self-maintaining knowledge base.
argument-hint: "--dry-run | --phase N | --phase 2.5 | --phase 3 --apply | --verbose"
user-invocable: true
disable-model-invocation: false
metadata:
  author: 0xrabbidfly
  version: "1.2.0"
---

# obsidian-vault-lint

## Purpose

Weekly vault maintenance inspired by [Karpathy's LLM Wiki approach](https://x.com/karpathy) (~16M views, April 2026). Instead of RAG (re-reading raw docs every call), the LLM maintains a *compiled wiki* — incrementally building and cleaning a structured knowledge base.

**Division of labor:**
- **Autonomous (this skill):** broken link cleanup, MOC coverage, alphabetical sorting, dead-entry removal, tag normalization, synonym merging
- **LLM-assisted (Phase 3):** semantic connection discovery for orphaned notes (approval-gated)
- **Approval-gated (Phase 2.5):** folder move proposals, emergent cluster proposals
- **Human:** curation, judgment on conflicts, deciding what gets its own Topic MOC

**Run time:** ~2-5 min for a 500-note vault. Phase 2.5 adds ~30s (frontmatter reads). Phase 3 adds ~1 min/5 orphans (xAI API calls).

---

## When to Use

- Weekly scheduled maintenance (Sundays 06:00 via Windows Task Scheduler)
- After a heavy ingest week when many new Library notes were added
- When vault-linker audit shows high orphan counts
- When Master MOC feels stale or sections are unsorted
- When tags have drifted (new synonyms, inconsistent casing)
- When a flurry of recent notes suggests a new topic is emerging

---

## Six Phases

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

### Phase 2.5 — Backward Propagation (taxonomy drift + emergent clusters)

Runs in two modes every cycle, between autonomous fixes and connection discovery.

**Mode A — Taxonomy Drift Repair:**

1. Reads the master MOC's `Canonical Tag Guidance` section to build the authoritative tag list
2. Reads the master MOC's section structure to map folder names to topic headings
3. For each note in `Research/Library/` (excluding `00 MOC/`):
   - Reads frontmatter tags
   - Checks if any tags are NOT in the canonical list (flags as orphaned tags)
   - Checks if the note is in the wrong folder based on its tags (e.g., a note tagged `rag` sitting in folder `01` instead of `05`)
   - Produces proposals: tag corrections, folder moves, orphaned tag warnings
4. **Auto-applies** tag normalization:
   - Case fixes: `RAG` → `rag`, `AI-Agents` → `ai-agents`
   - Synonym merges: uses the similar_tags pairs from Phase 1 inventory (>80% similarity) where one tag is canonical and the other is not
5. **Approval-gated** outputs (written to `Research/Logs/vault-lint-YYYY-MM-DD-backprop.md`):
   - Folder move proposals with reasoning
   - Orphaned tags not in the canonical list
   - Summary of auto-applied tag fixes

| Action | Autonomous | Approval-gated |
|--------|-----------|----------------|
| Tag case normalization | ✓ | |
| Synonym merge (canonical exists) | ✓ | |
| Folder move proposals | | ✓ |
| Orphaned tag flagging | | ✓ |

**Mode B — Emergent Cluster Detection:**

1. Looks at notes added in the last 30 days (by `date_saved` frontmatter)
2. Groups them by shared tag pairs
3. If 3+ recent notes share a tag combination that doesn't have its own MOC section heading, proposes creating one
4. Output to the proposals file: "3 new notes about [topic] — propose new MOC section?"

This catches organic topic growth: when several articles arrive about a new theme (e.g., "post-quantum + cryptography"), the system surfaces it before manual curation would notice.

### Phase 3 — Connection Discovery (LLM-assisted, approval-gated)
For the top-20 orphaned Library notes (batched 5 at a time):
1. Searches vault for related notes via content search
2. Calls xAI API to score semantic relevance (model: `grok-3`, configurable via `XAI_MODEL` env var)
3. Outputs proposed `[[wikilinks]]` to `Research/Logs/vault-lint-YYYY-MM-DD-connections.md`

Human reviews the file, then runs `--phase 3 --apply` to append links to each orphan's `## Related` section.

**Requires:** `XAI_API_KEY` env var or `keyring automation/xai / api_key`

### Phase 4 — MOC Reorganization
**Autonomous:**
- Remove dead MOC entries (wikilinks pointing to deleted notes)
- Deduplicate identical entries within sections

**Approval-gated** (writes proposals file):
- Sections with >12 entries -> propose a new Topic MOC
- Output: `Research/Logs/vault-lint-YYYY-MM-DD-moc-proposals.md`

### Phase 5 — Report
Writes `Research/Logs/vault-lint-YYYY-MM-DD.md` with health metrics, all changes, and links to approval-gated proposal files. Includes backward propagation summary (tag fixes applied, emergent clusters found).

After the report is written (non-dry-run full runs only), the script automatically commits all vault changes to git with message `vault-lint: automated maintenance {date}`.

---

## CLI Usage

```bash
# Full run (all 6 phases)
python .github/skills/obsidian-vault-lint/scripts/lint.py

# Dry run — preview all changes, nothing written
python .github/skills/obsidian-vault-lint/scripts/lint.py --dry-run

# Run specific phase only
python .github/skills/obsidian-vault-lint/scripts/lint.py --phase 1
python .github/skills/obsidian-vault-lint/scripts/lint.py --phase 2
python .github/skills/obsidian-vault-lint/scripts/lint.py --phase 2.5
python .github/skills/obsidian-vault-lint/scripts/lint.py --phase 3
python .github/skills/obsidian-vault-lint/scripts/lint.py --phase 4

# Apply connection proposals after reviewing the diff file
python .github/skills/obsidian-vault-lint/scripts/lint.py --phase 3 --apply

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

| Env var | Default | Purpose |
|---------|---------|---------|
| `XAI_API_KEY` | keyring fallback | xAI API key for Phase 3 |
| `XAI_MODEL` | `grok-3` | Model for connection scoring |

**Keyring (preferred):**
```bash
python -c "import keyring; keyring.set_password('automation/xai', 'api_key', '<your-key>')"
```

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
    ├── backprop.py    — Phase 2.5: taxonomy drift repair + emergent clusters
    ├── connections.py — Phase 3: xAI-assisted link discovery
    └── moc.py         — Phase 4: MOC dead-entry cleanup + proposals
```

---

## Dependencies

- Python 3.10+
- `obsidian.py` from `.github/skills/obsidian/scripts/`
- Obsidian 1.12+ running with CLI enabled
- `keyring` (stdlib alternative: `XAI_API_KEY` env var) — Phase 3 only
- xAI API key — Phase 3 only
- Git (at `C:\Program Files\Git\cmd\git.exe`) — for auto-commit after full runs

---

## Output Files (written to vault)

| File | Phase | Written when |
|------|-------|-------------|
| `Research/Logs/vault-lint-YYYY-MM-DD.md` | 5 | Always (full run) |
| `Research/Logs/vault-lint-YYYY-MM-DD-backprop.md` | 2.5 | When tag fixes, folder moves, or clusters are found |
| `Research/Logs/vault-lint-YYYY-MM-DD-connections.md` | 3 | When proposals exist |
| `Research/Logs/vault-lint-YYYY-MM-DD-moc-proposals.md` | 4 | When sections exceed 12 entries |

---

## Friction Rule

> If you hit unexpected errors mid-run:
> 1. Complete the step with a workaround
> 2. Immediately invoke `skill-reflection` with the friction details
> 3. Apply P0/P1 fixes to this SKILL.md now
> 4. Save an Agent Memory
> 5. Continue with remaining phases
