---
name: skill-reflection
description: Generic post-workflow self-reflection that any skill can invoke at the end of its run. Analyzes friction encountered during execution and produces advisory recommendations for improving the calling skill's SKILL.md. Use when a skill finishes (success or failure) and wants to capture improvement opportunities.
argument-hint: skill name, step results, friction notes
user-invokable: true
---

# Skill Reflection (Composable)

## Purpose

A composable "after-action review" that any skill calls at the end of its workflow.
It receives structured information about what happened and produces concrete,
prioritized recommendations for improving the calling skill's SKILL.md.

**This skill does not modify SKILL.md files automatically** — it produces advisory
output. The user decides what to apply.

## When to Use

- At the end of any multi-step skill workflow
- After a skill encounters friction (errors, workarounds, retries)
- After a successful run that still had rough edges
- When a user says "reflect on that run" or "what could be improved"

## Design Principles

1. **Generic** — knows nothing about specific skills; receives context as input
2. **Composable** — called inline by other skills, not standalone
3. **Advisory** — produces recommendations, never edits SKILL.md directly
4. **Cumulative** — tracks friction history to detect repeat issues

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

If the caller didn't provide structured input, ask:
> What skill just ran, and what friction did you encounter?

### 2. Categorize Friction

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

### 3. Read the Calling Skill's SKILL.md

Read the SKILL.md to understand:
- What steps are documented
- What troubleshooting/error tables exist
- What estimates or assumptions are stated
- Whether the friction point is already addressed (but poorly)

### 4. Check Friction History

Look for previous reflection output in the vault or in `.github/sessions/`:

```
Search for: "SKILL REFLECTION — <skill-name>"
```

If the **same friction category + same step** appears in a previous reflection:
- **Escalate to P0** (repeat friction = must fix)
- Note: "This is a repeat issue — first seen on [date]"

### 5. Produce Recommendations

Output using this format:

```
--- SKILL REFLECTION — <skill-name> ---

Run summary: Steps 1-N completed | <X> passed, <Y> failed, <Z> skipped
Friction points: <count>

Friction encountered:
  1. [Step X] <category>
     What happened: <description>
     Workaround used: <what the user/agent actually did>
     → Recommendation: <specific change to SKILL.md>

  2. [Step Y] <category>
     What happened: <description>
     → Recommendation: <specific change to SKILL.md>

Prioritized recommendations for <skill-name>/SKILL.md:
  R1. (P0 - breaking)  <change needed to prevent failure next time>
  R2. (P1 - quality)   <improvement to reduce manual steps or retries>
  R3. (P2 - nice)      <minor doc, timing, or clarity improvement>

Repeat friction: [none | list of issues seen before with dates]

No SKILL.md changes made — recommendations are advisory.
To apply: ask Copilot to "apply <skill-name> reflection recommendations from last run".
---
```

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
```
