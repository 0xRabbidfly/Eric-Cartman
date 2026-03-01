---
name: session-context-audit
description: Audit the health and coherence of all AI context files. Use when the AI behaves inconsistently, misapplies rules, or you suspect context drift after many sessions of incremental changes.
version: 1.0.0
user-invokable: true
disable-model-invocation: true
---

# Session Context Audit

## Purpose

A lightweight diagnostic that checks the **health, coherence, and coverage** of all context files the AI reads at session startup. Think of it as a linter for your AI's operating instructions.

From the article: _"The context compounds the more you invest in it."_ But compounding can go wrong — contradictions creep in, rules go stale, coverage gaps emerge. This skill catches those issues before they degrade output quality.

The difference from `session_context_optimizer`: session_context_optimizer does deep restructuring. Session-context-audit is a quick health check — run it often, act on red flags.

## When to Use

- The AI keeps making the same mistake despite instructions
- After merging a large PR that changed project conventions
- Before onboarding a new team member to the repo
- Monthly hygiene (takes ~2 minutes)
- After running `session-learning` several times (accumulated instructions)
- When you say: "audit my context", "why do you keep getting this wrong?", "check your instructions"

---

## Workflow

### Phase 1: File Discovery

Scan for all context files the AI consumes:

```
.github/copilot-instructions.md           → Root context
.github/instructions/*.instructions.md     → Scoped instructions
.github/skills/*/SKILL.md                  → Skill manifests
.claude/CLAUDE.md                          → Claude-specific context (if present)
.claude/settings.json                      → Claude settings (if present)
```

For each file, record: path, line count, last git modification date, section headings.

### Phase 2: Health Checks

Run automated checks in this order:

#### Check 1: Freshness

| File | Last Modified | Age | Status |
|------|--------------|-----|--------|
| copilot-instructions.md | 2026-02-15 | 12 days | 🟢 Fresh |
| auth.instructions.md | 2025-11-03 | 116 days | 🟡 Aging |
| testing.instructions.md | 2025-08-20 | 191 days | 🔴 Stale |

**Thresholds**: 🟢 < 30 days | 🟡 30–90 days | 🔴 > 90 days

#### Check 2: Contradictions

Cross-reference rules across all files. Common contradiction patterns:
- "Prefer X" in one file vs. "Avoid X" in another
- Different naming conventions in different scoped files
- Import style rules that conflict (e.g., barrel exports vs. direct imports)

Report each contradiction with file paths and line numbers.

#### Check 3: Duplication

Find rules that appear in more than one file. Score by similarity:
- **Exact duplicate**: identical text in 2+ files
- **Semantic duplicate**: same rule, different wording
- **Partial overlap**: rule in root that's also in a scoped file with slight differences

#### Check 4: Coverage Gaps

Compare instruction coverage against actual project structure:

```
app/api/**         → covered by api-routes.instructions.md? ✅
app/**/*.tsx       → covered by ui-react.instructions.md? ✅
lib/auth/**        → covered by auth.instructions.md? ✅
lib/server/**      → covered by server-graph-ai.instructions.md? ✅
**/*.module.css    → covered by styling.instructions.md? ✅
**/*.test.ts       → covered by any instructions? ❌ GAP
middleware.ts      → covered by any instructions? ❌ GAP
```

#### Check 5: Scope Accuracy

For each scoped `.instructions.md` file, verify:
- The `applyTo` glob actually matches files that exist
- The rules inside are relevant to those file types
- No rules that should be global are hidden in scoped files

#### Check 6: Skill Manifest Health

For each `SKILL.md`:
- Has required frontmatter (`name`, `description`)
- Description is a useful trigger phrase (not too vague, not too specific)
- Has `## When to Use` section
- Has `## Related Skills` section (composability)
- No dead cross-references to skills that don't exist

### Phase 3: Report Card

```markdown
## Context Health Report

**Date**: YYYY-MM-DD | **Files**: X | **Total lines**: X

### Overall Grade: [A / B / C / D / F]

| Category | Status | Issues |
|----------|--------|--------|
| Freshness | 🟢 / 🟡 / 🔴 | X stale files |
| Contradictions | 🟢 / 🔴 | X contradictions found |
| Duplication | 🟢 / 🟡 | X duplicated rules |
| Coverage | 🟢 / 🟡 | X gaps detected |
| Scope accuracy | 🟢 / 🟡 | X mismatches |
| Skill health | 🟢 / 🟡 | X issues |

### 🔴 Critical Issues (fix now)
1. [Contradiction between X and Y]
2. [Stale rule referencing removed dependency]

### 🟡 Warnings (fix soon)
1. [Duplicated rule in 2 files]
2. [Coverage gap for test files]

### 🟢 Healthy
- [List of things working well — positive reinforcement]

### Recommended Actions
1. [ ] [Specific fix with file path]
2. [ ] [Specific fix with file path]
3. [ ] Run `session_context_optimizer` for deeper restructuring (if grade < B)
```

---

## Grading Rubric

| Grade | Criteria |
|-------|----------|
| **A** | 0 contradictions, 0 stale files, ≤ 2 duplications, full coverage |
| **B** | 0 contradictions, ≤ 1 stale file, ≤ 4 duplications, minor gaps |
| **C** | 1 contradiction OR 2+ stale files OR significant gaps |
| **D** | 2+ contradictions OR widespread staleness |
| **F** | Contradictions actively causing wrong AI behavior |

---

## Rules

- **Report only, never auto-fix.** This is a diagnostic, not a surgeon.
- **Be specific.** Every issue must include file path, line number, and exact text.
- **Prioritize by impact.** Contradictions > Staleness > Duplication > Gaps.
- **Suggest the right tool.** Point to `session_context_optimizer` for restructuring, `session-learning` for adding rules.
- **Keep it fast.** This should complete in under 60 seconds for a typical project.

---

## Example Invocations

```
Audit my context files — something feels off. Use session-context-audit.
```

```
Quick health check on my instructions before I onboard a new dev.
```

```
Why do you keep using client components when I told you not to? Audit your context.
```

---

## Related Skills

- `session_context_optimizer` — Deep restructuring (use when audit grade < B)
- `session-learning` — Adds new instructions (may introduce duplication — audit catches it)
- `repo-state-sync` — Updates onboarding context; audit verifies it's coherent
- `code-review` — Consumes instructions; audit ensures they're trustworthy

