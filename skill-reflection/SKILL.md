---
name: skill-reflection
description: Generic post-workflow self-reflection that any skill can invoke at the end of its run. Analyzes friction encountered during execution and produces advisory recommendations for improving the calling skill's SKILL.md. Use when a skill finishes (success or failure) and wants to capture improvement opportunities.
argument-hint: skill name, step results, friction notes
user-invocable: true
disable-model-invocation: false
metadata:
  author: 0xrabbidfly
  version: "1.0.0"
---

# Skill Reflection (Composable)

## Purpose

A composable "after-action review" that any skill calls at the end of its workflow.
It receives structured information about what happened and produces concrete,
prioritized recommendations for improving the calling skill's SKILL.md.

**This skill does not modify SKILL.md files automatically** — it produces advisory
output. The user decides what to apply.

The primary output is a structured reflection report. If memory capture, immediate
fixes, or workflow resumption are needed, treat those as explicit caller-side
follow-up actions after the report is produced.

## When to Use

- At the end of any multi-step skill workflow
- After a skill encounters friction (errors, workarounds, retries)
- After a successful run that still had rough edges
- When a user says "reflect on that run" or "what could be improved"
- **Mid-run (inline)**: When a skill step fails and the agent applies a workaround — trigger immediately, don't wait for end of session
- **Self-healing loop**: When another skill's friction rule fires (see obsidian skill for the canonical pattern)

## Design Principles

1. **Generic** — knows nothing about specific skills; receives context as input
2. **Composable** — called inline by other skills, not standalone
3. **Advisory** — produces recommendations, never edits SKILL.md directly
4. **Cumulative** — tracks friction history to detect repeat issues
5. **Inline-capable** — can run mid-workflow, not just at end of session
6. **Follow-up aware** — may recommend memory capture or immediate fixes, but those actions remain outside the core reflection output contract

---

## How Other Skills Compose With This

### Embedding the reflection step

Add this as the **final step** in any skill's SKILL.md:

```markdown
### Step N: Reflection (composable)

Invoke the `skill-reflection` skill with the following context:

- **Calling skill**: `<skill-name>`
- **SKILL.md path**: `.github/skills/<skill-name>/SKILL.md`
- **Steps completed**: list each step with pass/fail/skipped
- **Friction notes**: any workarounds, retries, unexpected errors, or manual interventions

The reflection skill will analyze the run and produce improvement recommendations.
```

Preferred invocation shape:

```
Run skill-reflection for <skill-name>.
SKILL.md path: .github/skills/<skill-name>/SKILL.md
Steps completed:
  1. <step name> - PASS
  2. <step name> - FAIL
  3. <step name> - SKIPPED
Friction:
  - <issue 1>
  - <issue 2>
Run duration: <optional>
```

This exact shape is not required, but it is the preferred caller format because
it reduces follow-up questions and makes repeat-friction detection easier.

### Example: calling from a deployment skill

```
Run skill-reflection for azure-local-deploy.
Steps completed:
  0. Prerequisites check — PASS
  1. Docker build — PASS (took 4min, estimate was 2min)
  2. ACR push — FAIL, Zscaler blocked. Used --insecure workaround.
  3. App Service deploy — PASS after retry
  4. Smoke test — PASS
  5. Rollback — SKIPPED

Friction:
  - Zscaler blocked ACR push on first attempt
  - Docker build slower than documented estimate
```

### Example: calling from branch-wrapup

```
Run skill-reflection for branch-wrapup.
Steps completed:
  1. Build — PASS
  2. Typecheck — FAIL (3 errors), fixed, re-ran — PASS
  3. Lint — PASS
  4. Test — PASS
  5. Security scan — SKIPPED (no scanner configured)
  6. Code review — PASS
  7. Commit — PASS

Friction:
  - Typecheck errors were caused by a pattern the skill doesn't warn about
  - Security scan step has no fallback when scanner isn't installed
```

---

## Reflection Workflow

When invoked, follow these steps in order.

### 1. Parse the Run Context

Extract from the caller's input:

| Field | Required | Description |
|-------|----------|-------------|
| Calling skill name | Yes | Which skill just ran |
| SKILL.md path | Yes | Where to find the skill definition |
| Steps + status | Yes | Each step with PASS / FAIL / SKIPPED |
| Friction notes | No | Free-text description of issues encountered |
| Run duration | No | Total wall time if available |

Normalize status variants such as "passed", "failed", "ok", or "done" to
`PASS`, `FAIL`, or `SKIPPED` before analyzing the run.

If the caller didn't provide structured input, ask:
> What skill just ran, and what friction did you encounter?

Use this minimum-context rule:

- If the caller provides the calling skill name and a usable step list, proceed even
  if `SKILL.md path`, friction notes, or run duration are missing.
- If the caller provides the skill name but no step list, ask only for the missing
  steps and statuses.
- If the caller provides friction notes but not the calling skill name, ask first
  which skill just ran.
- Never ask for optional fields when the required fields are already sufficient to
  produce a recommendation report.

### 2. Reflect On the Run

Before categorizing, walk through these prompts to surface friction that the caller may not have explicitly reported:

1. **Commands that failed or needed workarounds** — did any step's commands throw errors, need flag changes, or require rewriting before they worked?
2. **False positives in scans** — did any automated check flag legitimate code that should be exempted or allowlisted?
3. **Missing checks** — were there issues found manually that the automated steps didn't catch?
4. **Step sequencing** — would a different order have saved time or caught blockers earlier?
5. **New patterns in the codebase** — did new file locations, file types, or conventions appear that the skill doesn't yet handle?
6. **Time sinks** — which steps required the most retries or additional investigation?

Add any findings to the friction list alongside what the caller already reported.

### 3. Categorize Friction

Classify each friction point into one of these **generic categories**:

| Category | Description | Examples |
|----------|-------------|---------|
| **Prerequisite gap** | A tool, auth, or config needed but missing or misconfigured | CLI not installed, auth expired, env var missing |
| **Command failure** | A documented command failed and needed a workaround | Wrong flag, API changed, syntax error in script |
| **Environment issue** | Network, proxy, permissions, or platform-specific problem | Zscaler, firewall, file permissions, OS difference |
| **Timing mismatch** | Step took much longer/shorter than documented | Cold start, download, build time wrong |
| **Undocumented error** | Error message not covered in troubleshooting | New error not in the skill's error table |
| **Missing step** | A manual action was needed that isn't in the skill | Had to run an extra command between steps |
| **Ambiguous instruction** | A step was unclear and required interpretation | Vague wording, missing parameter, unclear order |

### 4. Read the Calling Skill's SKILL.md

Read the SKILL.md to understand:
- What steps are documented
- What troubleshooting/error tables exist
- What estimates or assumptions are stated
- Whether the friction point is already addressed (but poorly)

If `SKILL.md path` is missing but the calling skill name is present, say that the
path was not provided and continue with the rest of the reflection instead of
blocking the run.

### 5. Check Friction History

Look for previous reflection output in the vault or in `.github/sessions/`:

```
Search for: "SKILL REFLECTION — <skill-name>"
```

If those history sources are unavailable, say so explicitly instead of assuming
there is no repeat friction.

If the **same friction category + same step** appears in a previous reflection:
- **Escalate to P0** (repeat friction = must fix)
- Note: "This is a repeat issue — first seen on [date]"

### 6. Produce Recommendations

Output using this verbose format:

```
--- SKILL REFLECTION — <skill-name> ---

Run summary: Steps 1-N completed | <X> passed, <Y> failed, <Z> skipped
Friction points: <count>

Friction encountered:
  1. [Step X] <category>
     What happened: <description>
    Evidence: <error text, command output, timing, or observed symptom if available>
    Confidence: <high | medium | low>
     Workaround used: <what the user/agent actually did>
     → Recommendation: <specific change to SKILL.md>

  2. [Step Y] <category>
     What happened: <description>
    Evidence: <supporting signal if available>
    Confidence: <high | medium | low>
     → Recommendation: <specific change to SKILL.md>

Prioritized recommendations for <skill-name>/SKILL.md:
  R1. (P0 - breaking)  <change needed to prevent failure next time>
    Why this priority: <one sentence>
  R2. (P1 - quality)   <improvement to reduce manual steps or retries>
    Why this priority: <one sentence>
  R3. (P2 - nice)      <minor doc, timing, or clarity improvement>
    Why this priority: <one sentence>

Repeat friction: [none | list of issues seen before with dates]

Self-improvement rule:
  If the same friction point appears in two consecutive runs,
  escalate to P0 and flag as a required fix before the next run.

No SKILL.md changes made — recommendations are advisory.
To apply: tell Copilot "apply the <skill-name> reflection recommendations and fix the SKILL.md".
---
```

Recommendation writing rules:

- Point to the affected step, section, or table in the calling skill whenever you
  can, not just the skill as a whole.
- Name the type of change needed: reorder a step, add a prerequisite check,
  document an error, clarify wording, or add a fallback.
- Tie each recommendation to the observed friction, not to a hypothetical future
  issue that did not occur in the run.
- Prefer concrete edits over generic advice such as "improve docs" or "make it clearer."
- Include evidence only when the run actually provides it; do not invent quotes,
  timings, or error strings.
- When context is missing, say `unknown`, `not provided`, or `not checked`
  explicitly instead of implying that nothing was found.

Optionally append a short follow-up block after the advisory report when useful:

```
Caller follow-up:
  - Memory capture: [required | optional | not needed]
  - Immediate fix before next run: [none | P0 item]
  - Resume parent workflow: [yes | no]
```

Skip this follow-up block on clean runs unless the parent workflow explicitly
requires memory capture or a resume signal.

### 7. Optional Caller Follow-Up: Capture Agent Memory

If the invoking workflow's rules require durable memory capture and the Obsidian
path is available, the caller can save the friction + resolution after the
reflection report is produced. Use the `obsidian` skill's Agent Memory pattern:

```powershell
@'
---
tags: [agent-memory, lesson]
source-skill: <calling-skill-name>
captured: <YYYY-MM-DD>
confidence: high
---
# Skill Reflection: <calling-skill-name> — <short friction summary>

## Context
<What skill was running, what step failed>

## Insight
<The key takeaway — what to do differently next time>

## Recommendations Applied
<List P0/P1 fixes that were applied to the SKILL.md>
'@ | python .github/skills/obsidian/scripts/obsidian.py create --path "Agent Memories/reflection-<skill-name>-<date>.md"
```

Search first to avoid duplicates:
```powershell
python .github/skills/obsidian/scripts/obsidian.py search "<skill-name> <friction-keyword>" --path "Agent Memories" --format json
```

### 8. Optional Caller Follow-Up: Self-Healing (Inline Mode)

When reflection is triggered **mid-run** (not end-of-session), the invoking
agent may use the advisory output to decide whether to self-heal before
continuing the parent workflow:

1. Produce the reflection output as normal (steps 1–6)
2. Evaluate the priority of each recommendation:
  - **P0 (breaking)** → Caller should apply the fix to the SKILL.md before continuing the parent workflow
  - **P1 (quality)** → Caller may apply if the fix is simple, else note it for later
  - **P2 (nice)** → Caller can defer it
3. Optionally capture Agent Memory if the parent workflow requires it
4. Resume the parent skill's remaining steps

This turns reflection from a post-mortem into a **live self-healing loop**.

## Priority Definitions

| Priority | Meaning | Action |
|----------|---------|--------|
| **P0 - breaking** | This friction will cause the skill to fail again next time | Must update SKILL.md before next run |
| **P1 - quality** | This friction causes retries, confusion, or wasted time | Should update SKILL.md soon |
| **P2 - nice** | Minor clarity or timing improvement | Update when convenient |

## Escalation Rule

> If the same friction point (same category + same step) appears in **two consecutive runs**,
> automatically escalate it to P0 regardless of original priority.

This prevents known issues from lingering as "nice to fix" indefinitely.

---

## When There's No Friction

If a run completed cleanly with no friction:

```
--- SKILL REFLECTION — <skill-name> ---

Run summary: Steps 1-N completed | all passed
Friction points: 0
Repeat friction: none

✅ Clean run — no recommendations.
Skill is working as documented.
---
```

Still log it if persisting to vault — clean runs are useful signal too.

---

## Anti-Patterns

```
❌ Auto-editing the calling skill's SKILL.md     — always advisory
❌ Inventing friction that wasn't reported        — only analyze what happened
❌ Generic advice ("add more docs")               — recommendations must be specific and actionable
❌ Skipping the history check                     — repeat detection is the core value
❌ Running without knowing which skill called     — always require the caller identity
❌ Treating follow-up actions as core output      — memory capture and fixes belong to the caller workflow
```
