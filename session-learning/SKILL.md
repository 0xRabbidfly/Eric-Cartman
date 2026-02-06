---
name: session-learning
description: Extract reusable patterns from a Copilot Chat session. Use at the end of long coding sessions to capture workarounds, error fixes, project-specific conventions, and debugging techniques as persistent instructions or skills.
version: 1.0.0
---

# Session Learning Skill

## Purpose

Analyze the current coding session to extract reusable patterns, workarounds, and project-specific knowledge. Unlike Claude Code's automatic hook-based extraction, this is a **manual skill** invoked at session end.

## Primary Objective (Non-Negotiable)

When a session surfaces recurring issues (especially linting, architectural guardrails, security constraints, or repeated user corrections), the primary objective is to **update the project’s developer guidelines** so the same mistakes are less likely to happen again.

This means producing persistent artifacts under `.github/` (instructions/skills) and wiring them into the “front-door” docs developers actually read.

## When to Use

- At the end of a long coding session (30+ min)
- After solving a tricky debugging problem
- When you corrected Copilot multiple times on the same issue
- After discovering a framework quirk or workaround
- When establishing new project conventions

---

## Quick Start

At session end, invoke:

```
Analyze this session and extract any patterns worth learning.
Use the session-learning skill.
```

---

## What Gets Extracted

### Pattern Types

| Pattern | Description | Save Location |
|---------|-------------|---------------|
| **Error Resolution** | How specific errors were diagnosed and fixed | `instructions/*.instructions.md` |
| **User Corrections** | When you corrected Copilot's approach | `copilot-instructions.md` or instructions |
| **Workarounds** | Solutions to framework/library quirks | New skill or instructions file |
| **Debugging Techniques** | Effective debugging patterns | Skills or instructions |
| **Project Conventions** | New conventions established | `copilot-instructions.md` |

### What to Ignore

- Simple typos
- One-time fixes unlikely to recur
- External API issues (not actionable)
- Environment-specific problems

---

## Extraction Workflow

### Phase 1: Session Analysis

Copilot will analyze the conversation to identify:

1. **Repeated corrections** - Did you tell Copilot the same thing multiple times?
2. **Error resolution cycles** - What errors occurred and how were they fixed?
3. **Non-obvious solutions** - Fixes that required specific knowledge
4. **New patterns established** - Code patterns used repeatedly

### Phase 2: Pattern Classification

For each identified pattern, determine:

| Question | Answer Options |
|----------|----------------|
| Is this project-specific? | Yes → Add to instructions or skills |
|  | No → May be general knowledge |
| Will this recur? | Yes → Worth capturing |
|  | No → Skip |
| Is this a workaround or best practice? | Workaround → Document clearly with context |
|  | Best practice → Add to instructions |

### Phase 3: Artifact Generation

Based on classification, generate:

#### Option A: Add to Existing Instructions

If the pattern fits an existing instructions file (e.g., `ui-react.instructions.md`):

```markdown
### [New Pattern Name]

**Context**: [When this applies]

✅ Do:
```tsx
// Correct approach
```

❌ Don't:
```tsx
// Incorrect approach
```

**Why**: [Explanation]
```

#### Option B: Create New Instructions File

For patterns that deserve their own file:

```markdown
---
applyTo: [glob pattern]
---

# [Pattern Name] Instructions

## Context
[When this applies]

## Rules
1. [Rule 1]
2. [Rule 2]

## Examples
...
```

Save to: `.github/instructions/[name].instructions.md`

#### Option C: Create New Skill

For complex patterns with workflows:

```markdown
---
name: [skill-name]
description: [When to use this skill]
version: 1.0.0
---

# [Skill Name]

## Purpose
[What this skill does]

## When to Use
- [Trigger 1]
- [Trigger 2]

## Workflow
...
```

Save to: `.github/skills/[name]/SKILL.md`

---

## Extraction Prompt Template

When analyzing a session, use this structured approach:

```
## Session Learning Analysis

### Session Summary
- Duration: [Approximate length]
- Main tasks: [What was worked on]
- Key challenges: [What problems were solved]

### Patterns Detected

#### 1. [Pattern Name]
- **Type**: [Error Resolution / User Correction / Workaround / Convention]
- **Recurrence Likelihood**: [High / Medium / Low]
- **Project-Specific**: [Yes / No]
- **Summary**: [One-line description]
- **Details**: [Full explanation]
- **Recommended Action**: [Add to X / Create new Y / Skip]

#### 2. [Pattern Name]
...

### Recommended Artifacts

1. **Update `.github/instructions/[file].instructions.md`**:
   - Add: [pattern details]

2. **Create `.github/skills/[name]/SKILL.md`**:
   - Purpose: [what it does]

3. **Update `.github/copilot-instructions.md`**:
   - Add to section: [section name]
   - Content: [what to add]

### Skip These (Not Worth Capturing)
- [Pattern]: [Why skipped]
```

---

## Example Extracted Patterns

### Example 1: Error Resolution

**Session event**: Spent 15 minutes debugging "Cannot find module '@/lib/auth'"

**Extracted pattern**:
```markdown
### Path Alias Resolution in Tests

When tests fail with "Cannot find module '@/...'", check:

1. `vitest.config.ts` has `resolve.alias` matching `tsconfig.json`
2. Test is using the correct import syntax

✅ Correct vitest.config.ts:
```typescript
resolve: {
  alias: {
    '@': path.resolve(__dirname, './'),
  }
}
```
```

**Save to**: `.github/instructions/testing.instructions.md`

---

### Example 2: User Correction

**Session event**: Corrected Copilot 3x to use Server Components

**Extracted pattern**:
```markdown
## Server Components by Default

ALWAYS prefer Server Components. Only add 'use client' when:
- Component uses useState, useEffect, or other hooks
- Component needs browser APIs (window, document)
- Component needs event handlers (onClick, onChange)

❌ Don't add 'use client' for:
- Components that only render props
- Components that fetch data
- Layout components
```

**Save to**: `.github/copilot-instructions.md` (strengthen existing rule)

---

### Example 3: Framework Workaround

**Session event**: Discovered Fluent UI Button styling issue with Next.js Link

**Extracted pattern**:

Create new skill: `.github/skills/fluent-ui-quirks/SKILL.md`

```markdown
---
name: fluent-ui-quirks
description: Workarounds for Fluent UI v9 quirks in Next.js App Router
version: 1.0.0
---

# Fluent UI Quirks

## Button as Link

Fluent UI Button loses styling when wrapped in Next.js Link.

✅ Correct:
```tsx
<Button as="a" href="/path">Navigate</Button>
```

❌ Incorrect:
```tsx
<Link href="/path"><Button>Navigate</Button></Link>
```
```

---

## Storage Locations

| Artifact Type | Location | When to Use |
|--------------|----------|-------------|
| Quick rules | `.github/copilot-instructions.md` | Universal project rules |
| File-specific rules | `.github/instructions/*.instructions.md` | Rules for specific file patterns |
| Complex workflows | `.github/skills/*/SKILL.md` | Multi-step processes |
| Reference material | `.github/references/*.md` | Documentation, not instructions |

---

## Integration with Verification

After extracting patterns, run verification to ensure new instructions don't conflict:

```
Run verification-loop to check the changes.
```

---

## Session Learning Checklist

Before ending a long session:

- [ ] Were there repeated corrections? → Capture as instruction
- [ ] Did we solve a tricky error? → Document resolution
- [ ] Did we discover a workaround? → Create skill or instruction
- [ ] Did we establish new conventions? → Update copilot-instructions.md
- [ ] Did patterns emerge in the code? → Consider skill creation

---

## Automation Opportunities

While VS Code Copilot doesn't have Claude Code's hook system, you can:

1. **Create a VS Code Task** that prompts for session review:
   ```json
   {
     "label": "Session Learning Review",
     "type": "shell",
     "command": "echo 'Open Copilot Chat and invoke session-learning skill'"
   }
   ```

2. **Set a calendar reminder** for end-of-day session review

3. **Use Copilot Chat history** (when available) to review past sessions

---

## Related Skills

- `code-review` - Uses existing instructions; session-learning creates them
- `project-scaffold` - Initial setup; session-learning evolves over time
- `agentic-evaluator` - Audits instruction quality

---

## Completion Criteria (Definition of “Done”)

This skill is only “done” when:

1. The immediate issue is resolved (or explicitly documented as intentionally deferred), AND
2. The relevant developer guidelines are updated so it won’t regress.

For example, if a session involved lint errors:
- Fix the errors.
- Capture the exact lint-safe patterns that prevented recurrence.
- Update the *relevant* instructions docs (not just a new file) so future changes follow the same patterns.

---

## Required Output (What to Produce)

When patterns are detected, produce at least one of:

1. Update an existing instructions file that already applies to the affected area (preferred).
2. Create a new `.github/instructions/*.instructions.md` if no existing file is appropriate.
3. Create or update a `.github/skills/*/SKILL.md` if it’s a multi-step workflow.

And always add a cross-reference in a “front-door” doc when appropriate:
- `.github/copilot-instructions.md` for repo-wide guidance.
- `.github/instructions/ui-react.instructions.md` for UI/React rules.
- `.github/instructions/api-routes.instructions.md` for API handler rules.

---

## Session-End Checklist (Use Every Time)

- [ ] Identify the highest-cost mistakes that recurred (lint, security, architecture, UX constraints).
- [ ] Fix the immediate issue(s) where feasible.
- [ ] Write down the minimal repeatable rule(s) and the preferred code pattern(s).
- [ ] Update the most relevant existing instructions file(s) FIRST.
- [ ] If needed, add a new instructions file (scoped `applyTo`), but don’t rely on new files alone.
- [ ] Add a cross-reference from `.github/copilot-instructions.md` or another front-door doc.
- [ ] Re-run the validation step that caught the issue (e.g., `npm run lint`) to confirm.
