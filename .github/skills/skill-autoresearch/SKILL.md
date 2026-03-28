---
name: skill-autoresearch
description: Karpathy-style bounded keep-or-revert loop for creating or improving one skill at a time. Use when the user wants to create a new skill or improve an existing one through fixed eval batches, a results ledger, baseline comparisons, and controlled promotion instead of a one-shot draft.
user-invocable: true
disable-model-invocation: false
metadata:
  author: 0xrabbidfly
  version: "1.0.0"
---

# Skill Autoresearch

## Purpose

Apply the core `autoresearch` pattern to skill development in this repo:

- one mutable surface
- one stable harness
- one explicit metric set
- one results ledger
- one keep-or-revert decision per iteration

Use this skill when the goal is not merely to write a `SKILL.md`, but to improve
it empirically through bounded experiments.

**Simplicity criterion**: All else being equal, simpler is better. A small score
gain that adds convoluted workflow steps or brittle guardrails is not worth it.
Conversely, removing instructions and getting equal or better results is a
simplification win — always keep those. When evaluating whether to keep a change,
weigh complexity cost against improvement magnitude. A 2% pass-rate bump that
adds 40 lines of edge-case rules? Probably not worth it. A 2% bump from deleting
redundant steps? Definitely keep. A flat score but 30% fewer instructions? Keep.

This skill is the control plane. It does not replace `skill-creator` or
`session-skill-forge`.

- Use `session-skill-forge` to turn a known workflow into a first draft.
- Use `skill-creator` to help generate prompts, assertions, and benchmark runs.
- Use `skill-autoresearch` when you want the full hill-climbing loop around one
  target skill.

## When to Use

| Trigger | Action |
|---|---|
| "improve this skill systematically" | Start a bounded skill improvement loop |
| "use the Karpathy autoresearch pattern on this skill" | Create the experiment brief and ledger |
| "benchmark this skill and only keep winners" | Run keep-or-revert iterations |
| "create a new skill, but validate it properly" | Draft then test against a no-skill baseline |
| "turn skill design into a measured loop" | Add fixed prompts, scoring, and promotion rules |

## Core Mapping

| Autoresearch | Skill Version |
|---|---|
| `program.md` | experiment brief + this `SKILL.md` |
| `train.py` | one target `SKILL.md` |
| `prepare.py` | stable harness: tests, scripts, wrapper tools, eval prompts |
| `val_bpb` | primary score: pass rate, trigger accuracy, or rubric score |
| `results.tsv` | skill experiment ledger |
| keep / discard | promote / revert candidate revision |

## Workflow

### Phase 1: Define the Research Lane

Choose exactly one target artifact for the loop.

- **Improve existing skill**: mutate only `.github/skills/<name>/SKILL.md` for the
  first iteration block.
- **Create new skill**: create only `.github/skills/<name>/SKILL.md` until the core
  workflow proves useful.

Do not widen scope early. Avoid adding scripts, README updates, or related skill
edits until the core instructions are winning.

If the user asks for broad changes, narrow them to one of these first:

- trigger quality
- workflow clarity
- output format quality
- eval performance
- error handling

### Phase 2: Set Up the Control Plane

Create a sibling workspace for the target skill:

```text
.github/skills/<target-skill>/
.github/skills/<target-skill>-workspace/
  experiment-brief.md
  results.tsv
  iteration-1/
  iteration-2/
```

Use the templates in `templates/`.

Fill in `experiment-brief.md` with:

1. Goal
2. Mode: `create` or `improve`
3. Mutable surface
4. Frozen surfaces
5. Primary metric
6. Secondary metrics
7. Baseline definition
8. Eval batch
9. Keep threshold
10. Stop conditions

The evaluator must remain more stable than the artifact being optimized.

### Phase 3: Establish the Baseline

Before editing the candidate:

1. Capture the current target as the baseline.
2. Define a fixed eval batch, typically 3-5 realistic prompts.
3. Add assertions only where outputs are objectively checkable.
4. Run the baseline eval and record the score in `results.tsv`.

Baseline rules:

- **Existing skill**: baseline is the current skill revision.
- **New skill**: baseline is no skill, or the current manual workflow.

If `skill-creator` already has a useful benchmark harness for the target, reuse
it instead of inventing a new one.

#### How to score an eval run

Each eval prompt is run against the candidate skill and scored on a 0–1 rubric.
The primary metric is the mean score across the batch.

Concrete execution steps:

1. For each eval prompt, invoke the target skill (or simulate invocation by
   providing the skill text as system context to `skill-creator`'s benchmark
   runner if available).
2. Score each output against the rubric. Use binary pass/fail (0 or 1) for
   objective checks (correct format, required sections present, triggers fired).
   Use a 0.0–1.0 scale for subjective quality (clarity, usefulness, tone).
3. Record per-prompt scores in the iteration snapshot directory.
4. Compute the mean as the primary metric for `results.tsv`.

If the eval cannot be automated, score manually — but use the same rubric and
prompts every time. Consistency matters more than automation.

### Phase 4: Run One-Hypothesis Iterations

Each iteration must test one clear idea only.

Good hypotheses:

- tighten the trigger description
- simplify the workflow ordering
- add one missing guardrail
- replace vague output guidance with a strict template
- add one deterministic checkpoint

Bad hypotheses:

- rewrite the entire skill and its scripts at once
- change prompts, scripts, and evals in the same iteration
- widen the scope because the first result was mediocre

For each iteration:

1. Copy the current winner into an iteration snapshot.
2. Edit only the mutable surface.
3. Run the same eval batch as the baseline using the same scoring rubric.
4. Record scores, observations, and failures in `results.tsv`.
5. Decide `keep`, `discard`, or `crash`.

#### Crash triage

Not all failures are equal:

- **Dumb crash** (skill doesn't parse, missing section, broken template
  reference): fix immediately and re-run. Do not count as a full iteration.
- **Fundamentally broken idea** (the hypothesis itself produces nonsense or
  makes the skill worse in every eval prompt): log status as `crash`, revert
  to the last winner, and move on. Do not spend more than one retry on a
  fundamentally broken direction.

### Phase 5: Keep or Revert

Apply the `autoresearch` promotion rule in adapted form:

- **Keep** when the primary metric improves and no important guardrail regresses.
- **Keep** on a flat score if the skill becomes meaningfully simpler (fewer
  instructions, fewer steps, less conditional logic). Simplification at equal
  performance is always a win.
- **Discard** when the score is worse, the trigger gets noisier, or the review
  burden increases without enough gain. A tiny improvement that adds significant
  complexity is a discard — the complexity cost outweighs the gain.
- **Crash** when the candidate breaks invocation, formatting, or the eval run.

When discarding, revert to the last winning snapshot. Do not manually blend the
losing draft back into the winner.

### Phase 6: Bound the Loop

Do not copy the literal "loop forever" rule from `autoresearch`.

Use bounded batches such as:

- 3 iterations for a small refinement pass
- 5 iterations for a new skill
- stop after 2 consecutive non-improving candidates
- stop once the remaining ideas are broad rewrites instead of clean hypotheses

Ask the user for another batch only after you finish the current one.

#### When you run out of ideas

Do not stop early just because the obvious hypotheses are exhausted. Before
ending a batch:

- Re-read the target skill's related skills for patterns worth borrowing.
- Review eval failures for thematic gaps (are certain prompt types always weak?).
- Check session logs or past `skill-reflection` outputs for friction that the
  current skill doesn't address.
- Try combining two near-miss hypotheses from earlier iterations.
- Try deletion: remove a section or rule and see if the score holds.

Only end the batch when remaining ideas require scope expansion beyond the
mutable surface.

### Phase 7: Promote the Winner

Only after a winning core revision exists should you widen the scope to:

- helper scripts
- README registration
- related skill cross-links
- benchmark expansion
- description optimization for triggering

Promotion order:

1. Winner `SKILL.md`
2. Eval updates
3. Registry and README updates
4. Optional scripts

## Output Format

### Experiment Brief

Always maintain a brief shaped like this:

```markdown
# Skill Experiment Brief

## Goal
<what the skill should do better>

## Target Skill
<skill name>

## Mode
create | improve

## Mutable Surface
<one file or one artifact>

## Frozen Surfaces
- <files or systems that must not change>

## Primary Metric
<pass rate, rubric score, trigger accuracy, etc.>

## Secondary Metrics
- <simplicity>
- <portability>
- <token or time cost if relevant>

## Baseline
<current skill or no-skill workflow>

## Eval Batch
1. <prompt 1>
2. <prompt 2>
3. <prompt 3>

## Keep Threshold
<what qualifies as a winner>

## Stop Conditions
- <condition 1>
- <condition 2>
```

### Results Ledger

Use tab-separated rows with this schema:

```text
iteration	artifact	mode	baseline_score	candidate_score	delta	status	hypothesis	notes
```

Example:

```text
baseline	skill-autoresearch	create	0.00	0.62	0.62	keep	initial draft	structure passes and output is coherent
1	skill-autoresearch	create	0.62	0.71	0.09	keep	added single-surface rule	more consistent decisions across prompts
2	skill-autoresearch	create	0.71	0.68	-0.03	discard	widened scope too early	README and scripts confused the loop
```

## Rules

- Keep one mutable surface per iteration.
- Freeze the evaluator unless the user explicitly asks to redesign it.
- Prefer prompt-only skill revisions before adding scripts.
- Reuse `skill-creator` for benchmark harnesses instead of duplicating them.
- Log every run, including crashes and dead ends.
- Use workspace snapshots (iteration directories) as the default revert
  mechanism. Git commits and resets are optional — use them only if the user
  explicitly sets up a dedicated branch for the experiment.
- Do not commit to the main working branch without the user's approval.
- Treat human judgment as part of the control plane, not an afterthought.
- Only promote README and registry changes after the skill proves value.
- If the skill duplicates an existing one, stop and narrow the scope instead of
  creating another overlapping artifact.

## Example Invocations

```text
Use skill-autoresearch to improve podcast-to-obsidian. Keep the loop bounded to 3 iterations and only mutate SKILL.md.
```

```text
Create a new skill for research-note scoring, but do it with a Karpathy-style keep-or-revert loop.
```

```text
Run skill-autoresearch on session-skill-forge and tell me which instruction changes actually improve the eval prompts.
```

## Related Skills

- `skill-creator` — prompt, assertion, and benchmark generation
- `session-skill-forge` — first-draft skill extraction from a workflow
- `skill-reflection` — capture friction discovered during the loop
- `session-learning` — convert repeated loop lessons into durable repo guidance