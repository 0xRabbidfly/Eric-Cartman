---
name: session_context_optimizer
description: Audit and restructure the AI's own context files for efficiency. Use when copilot-instructions.md feels bloated, stale, or disorganized — or when you want the AI to propose how it would restructure its own operating context for maximum session efficiency.
version: 1.1.0
user-invokable: true
disable-model-invocation: true
---

# Session Context Optimizer

## Purpose

Let the AI analyze and restructure its own context files — `.github/copilot-instructions.md`, `.github/instructions/*.instructions.md`, `.claude/CLAUDE.md`, and skill manifests — to make them more efficient, less redundant, and better organized.

Inspired by the **meta-optimization** pattern: _"Ask Claude how it would restructure the CLAUDE.md to be even more efficient, then let it update the file itself."_

The insight: context files accumulate organically over sessions. Rules get duplicated, conventions drift, sections become overloaded. Periodically letting the AI audit and compress its own operating context makes every future session cheaper and sharper.

## When to Use

- Context files feel bloated or contain redundant sections
- You've been adding instructions for weeks without cleanup
- The AI keeps misapplying rules (signal of conflicting or unclear context)
- After a major project phase change (old context no longer relevant)
- Periodically (every 2–4 weeks) as context hygiene
- When you say: "optimize your own instructions", "clean up your context", "meta-optimize", "session_context_optimizer"

---

## Workflow

### Phase 1: Context Inventory

Gather and read ALL context files the AI consumes at session startup:

```
1. .github/copilot-instructions.md           (root context)
2. .github/instructions/*.instructions.md     (scoped instruction files)
3. .claude/CLAUDE.md                          (if present)
4. .github/skills/*/SKILL.md                  (skill manifests — scan headers only)
5. Any memory.md or session state files
```

For each file, note:
- Line count and section count
- Last meaningful update (git blame or frontmatter date)
- Topic coverage (what rules/conventions it contains)

### Phase 2: Structural Analysis

Analyze the context corpus for:

| Issue | Description | Action |
|-------|-------------|--------|
| **Duplication** | Same rule stated in 2+ files | Consolidate to single authoritative location |
| **Contradiction** | Conflicting rules (e.g., "use Server Components" vs. hook-heavy examples) | Resolve — keep the intended behavior |
| **Staleness** | Rules referencing removed packages, old patterns, or completed migrations | Remove or archive |
| **Bloat** | Verbose explanations where a concise rule suffices | Compress |
| **Gaps** | Areas the project uses heavily but has no instructions for | Flag for user decision |
| **Poor hierarchy** | Critical rules buried deep; niche rules at top | Re-order by frequency of impact |
| **Scope mismatch** | Rules in root that only apply to one file pattern (should be scoped) | Move to appropriate `.instructions.md` |

### Phase 3: Optimization Proposal

Present findings as a structured report BEFORE making changes:

```markdown
## Meta-Optimization Report

### Summary
- Files analyzed: X
- Total context lines: X
- Estimated after optimization: X (Y% reduction)

### Findings

#### 🔴 Contradictions (must fix)
1. [File A, line X] says "..." but [File B, line Y] says "..."
   → Recommended resolution: ...

#### 🟡 Duplications (should consolidate)
1. [Rule] appears in [File A] and [File B]
   → Keep in [File A], remove from [File B] because ...

#### 🟢 Staleness (safe to remove)
1. [Rule about X] — package X was removed in commit abc123
   → Delete

#### 📊 Restructuring Suggestions
1. Move section [X] from root to [scoped file] (only applies to *.tsx)
2. Promote section [Y] higher — it's the most frequently violated rule
3. Compress section [Z] from 40 lines to 8

### Questions for You
1. [Rule X] — is this still relevant? (I can't determine from code alone)
2. [Convention Y] — should this become a skill instead of an instruction?
```

### Phase 4: Apply Changes (with user approval)

After user reviews and approves (or modifies) the proposal:

1. Apply all approved changes across context files
2. Ensure no orphaned cross-references
3. Run `npm run lint` and `npm run build` to verify nothing broke
4. Produce a one-line summary of each file changed

### Phase 5: Self-Interview (Optional)

If the user requests it, enter **interview mode**:

> "What information do you still need to do your best work on this project?"

Ask up to 5 targeted questions about the project, then update context files with the answers. Focus on:
- Deployment environment details
- Team conventions not yet documented
- Common error patterns the user encounters
- Preferences the AI keeps getting wrong

---

## Output Format

The optimization report (Phase 3) is the primary deliverable. Changes to files happen only after user approval.

---

## Rules

- **NEVER delete context without showing the user first.** Always propose, then apply.
- **Preserve intent.** Compression means fewer words, not lost meaning.
- **Respect scoping.** Don't move scoped rules to root. Don't put global rules in scoped files.
- **One source of truth.** Every rule lives in exactly one place. Other files reference it, not duplicate it.
- **Measure the delta.** Report before/after line counts so the user sees the compression.

---

## Example Invocations

```
Optimize my copilot instructions. Use session_context_optimizer.
```

```
My instructions feel bloated — audit and compress them.
```

```
Interview me about what's missing from your context, then update your files.
```

---

## Related Skills

- `session-learning` — Adds new patterns; session_context_optimizer consolidates them
- `repo-state-sync` — Updates onboarding section; session_context_optimizer restructures the whole file
- `code-review` — Consumes instructions; session_context_optimizer improves what it reads
- `session-context-audit` — Lighter-weight health check; session_context_optimizer does deeper restructuring

