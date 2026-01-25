---
name: agentic-evaluator
description: Evaluates any repository's agentic development maturity. Use when auditing a codebase for best practices in agents, skills, instructions, MCP config, and prompts. Produces a scored report with specific remediation steps.
version: 1.0.0
---

# Agentic Evaluator Skill

## Purpose

Score a repository's implementation of agentic development patterns and provide actionable remediation guidance. Works on any codebase—your own or external repos.

## When to Use

- Auditing a new repository before contributing
- Evaluating your project's agentic maturity
- Onboarding to a codebase with agentic features
- CI gate to enforce minimum agentic standards
- Comparing multiple repos' agentic implementations

## Quick Start

```
Evaluate this repository's agentic development patterns.
Generate a scored report using the agentic-evaluator skill.
```

---

## Scoring Categories (100 points)

| Category | Points | Focus |
|----------|--------|-------|
| Foundation | 25 | Root instructions, structure, MCP config |
| Skills | 25 | Frontmatter, examples, right-sizing |
| Agents | 20 | Tools, mission, handoffs |
| Instructions | 20 | applyTo patterns, coverage |
| Consistency | 10 | Naming, no duplicates, cross-refs |

## Scoring Rubric

| Score | Grade | Interpretation |
|-------|-------|----------------|
| 90-100 | A | Excellent — Production-ready |
| 80-89 | B | Good — Minor improvements needed |
| 70-79 | C | Adequate — Noticeable gaps |
| 60-69 | D | Developing — Significant work needed |
| <60 | F | Foundational — Start with basics |

---

## Evaluation Workflow

### Phase 1: Discovery Scan

Scan for agentic artifacts at these locations:

```
├── .github/
│   ├── copilot-instructions.md
│   ├── skills/*/SKILL.md
│   ├── agents/*.md
│   ├── instructions/*.instructions.md
│   ├── prompts/*.md
│   ├── commands/*.md
│   ├── references/*.md
│   └── mcp.json
├── .claude/
│   ├── claude.md
│   └── skills/
├── .cursor/
│   └── prompts/
├── .vscode/
│   └── mcp.json
└── AGENTS.md
```

Record file counts and line counts per artifact type.

### Phase 2: Foundation (25 points)

| Check | Points | Criteria |
|-------|--------|----------|
| Root instructions exist | 5 | `.github/copilot-instructions.md` OR `AGENTS.md` OR `.claude/claude.md` |
| Root instructions quality | 5 | Has project context, tech stack, non-negotiables (50+ lines) |
| `.github/` structure | 5 | Organized folders for artifacts |
| README mentions agentic features | 5 | Documents how to use AI assistance |
| MCP config exists | 5 | `.github/mcp.json` or `.vscode/mcp.json` |

### Phase 3: Skills (25 points)

| Check | Points | Criteria |
|-------|--------|----------|
| Skills folder exists | 2 | `.github/skills/` present |
| Valid frontmatter | 4 | `name` + `description` in YAML |
| "When to Use" section | 3 | Clear trigger scenarios |
| Examples included | 3 | Concrete code/command examples |
| Right-sized | 3 | 100-500 lines (not monolithic) |
| Progressive disclosure | 5 | 3-tier: metadata → body → bundled files |
| Cover key workflows | 5 | Testing, deployment, or domain-specific |

**Progressive Disclosure** (per Anthropic guidance):
1. **Metadata** (~100 tokens): `name` + `description` loaded at startup
2. **Instructions** (1-5K tokens): Full SKILL.md body loaded when triggered
3. **Resources** (on-demand): Bundled files referenced by name, loaded only as needed

✅ Good: `See: templates/component.template.tsx for scaffolding`
❌ Bad: Embedding 200-line template directly in SKILL.md

**Frontmatter schema:**
```yaml
---
name: required        # lowercase-hyphenated
description: required # includes "Use when..." trigger
version: optional     # semantic versioning
---
```

### Phase 4: Agents (20 points)

| Check | Points | Criteria |
|-------|--------|----------|
| Agents folder exists | 2 | `.github/agents/` present |
| Valid frontmatter | 3 | `name`, `description`, `tools` declared |
| Clear mission | 4 | Single responsibility, defined workflow |
| Handoff patterns | 3 | References other agents (`@agent-name`) |
| Skill references | 3 | Uses `See: skill-name` for capabilities |
| Right-sized | 2 | 100-400 lines |
| Tools match MCP | 3 | Declared tools are available |

**Frontmatter schema:**
```yaml
---
name: required
description: required
model: optional       # e.g., "Claude Opus 4.5 (copilot)"
target: optional      # e.g., "vscode"
tools: required       # array of allowed tools
---
```

### Phase 5: Instructions (20 points)

| Check | Points | Criteria |
|-------|--------|----------|
| Instructions folder exists | 2 | `.github/instructions/` present |
| Has `applyTo` patterns | 4 | Valid glob patterns in frontmatter |
| Has code examples | 5 | Good/bad pattern comparisons |
| Right-sized | 4 | 50-200 lines with concrete guidance |
| Coverage analysis | 5 | Patterns match actual codebase files |

**Frontmatter schema:**
```yaml
---
applyTo: required     # glob pattern(s)
excludeAgent: optional
---
```

### Phase 6: Consistency (10 points)

| Check | Points | Criteria |
|-------|--------|----------|
| Naming conventions | 2 | lowercase-hyphenated |
| No duplicates | 2 | No redundant agent/prompt pairs |
| Cross-refs resolve | 2 | `@agent-name` and "See: skill" work |
| Version fields | 2 | Mature skills have `version:` |
| Supporting files organized | 2 | Templates in skill subdirs |

### Phase 7: Generate Report

Output using this structure:

```markdown
# Agentic Evaluation Report

**Repository**: [name]
**Evaluated**: [timestamp]
**Overall Score**: X/100 (Grade: X)

## Score Breakdown

| Category | Score | Max | Notes |
|----------|-------|-----|-------|
| Foundation | X | 25 | ... |
| Skills | X | 25 | ... |
| Agents | X | 20 | ... |
| Instructions | X | 20 | ... |
| Consistency | X | 10 | ... |

## Artifacts Found

| Type | Count | Avg Lines | Status |
|------|-------|-----------|--------|
| Skills | X | X | ✅/⚠️/❌ |
| Agents | X | X | ✅/⚠️/❌ |
| Instructions | X | X | ✅/⚠️/❌ |

## Issues Found

### P0 (Critical)
- [ ] Issue → Remediation

### P1 (High)
- [ ] Issue → Remediation

### P2 (Medium)
- [ ] Issue → Remediation

## Recommendations

1. **Quick Win**: [Lowest effort, highest impact]
2. **Next Step**: [Logical follow-up]
3. **Long Term**: [Strategic improvement]
```

---

## Size Guidelines Reference

| Artifact | Min | Max | Notes |
|----------|-----|-----|-------|
| Root instructions | 50 | 300 | Project overview, non-negotiables |
| Skills | 100 | 500 | Single workflow focus |
| Agents | 100 | 400 | Clear mission, defined workflow |
| Instructions | 50 | 200 | File-specific patterns |

**Signals to split:**
- File exceeds max by >20%
- Multiple unrelated concerns
- "When to Use" has >5 distinct scenarios

---

## Skill Development Best Practices

From [Anthropic's Agent Skills guidance](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills):

### Start with Evaluation
- Identify gaps by running agents on representative tasks
- Observe where they struggle or need additional context
- Build skills incrementally to address shortcomings

### Structure for Scale
- When SKILL.md becomes unwieldy, split into separate files
- Reference bundled files by name: `See: reference.md`
- Keep mutually exclusive contexts in separate paths
- Code serves as both executable tools AND documentation

### Think from Claude's Perspective
- Monitor how Claude uses your skill in real scenarios
- Watch for unexpected trajectories or overreliance
- Pay special attention to `name` and `description` — Claude uses these to decide whether to trigger the skill

### Iterate with Claude
- Ask Claude to capture successful approaches into reusable context
- When it goes off track, ask it to self-reflect on what went wrong
- Discover what context Claude actually needs vs. anticipating upfront

### Security Considerations
- Install skills only from trusted sources
- Audit bundled files before use — check code dependencies
- Watch for instructions connecting to external network sources
- Review scripts that Claude might execute

---

## Remediation Patterns

When files exceed size limits, use these splitting strategies:

### Oversized Skill (>500 lines)

**Split into:**
```
skill-name/
├── SKILL.md           # Core workflow (100-300 lines)
├── reference.md       # Detailed reference material
├── patterns.md        # Code patterns and examples  
├── checklist.md       # Validation checklist
└── templates/         # Reusable templates
    ├── component.template.tsx
    └── test.template.ts
```

### Oversized Agent (>400 lines)

**Split into sub-agents:**
```
.github/agents/
├── workflow-orchestrator.md    # Main agent, coordinates
├── workflow-analyzer.md        # Sub-agent: analysis phase
├── workflow-implementer.md     # Sub-agent: implementation
└── workflow-validator.md       # Sub-agent: validation
```

### Oversized Instructions (>200 lines)

**Split by concern:**
```
.github/instructions/
├── typescript.instructions.md     # Language patterns
├── react-components.instructions.md  # Framework patterns
└── api-routes.instructions.md     # API patterns
```

---

## Example: Minimal Repo

```markdown
# Agentic Evaluation Report

**Repository**: basic-express-app
**Overall Score**: 35/100 (Grade: F)

## Artifacts Found
| Type | Count |
|------|-------|
| Root instructions | 0 |
| Skills | 0 |

## Issues Found

### P0 (Critical)
- [ ] No root instructions → Create `.github/copilot-instructions.md`

### Recommendations
1. **Quick Win**: Create copilot-instructions.md with project overview
```

---

## Example: Well-Configured Repo

```markdown
# Agentic Evaluation Report

**Repository**: ai-hub-portal
**Overall Score**: 92/100 (Grade: A)

## Score Breakdown
| Category | Score | Max |
|----------|-------|-----|
| Foundation | 25 | 25 |
| Skills | 23 | 25 |
| Agents | 19 | 20 |
| Instructions | 18 | 20 |
| Consistency | 7 | 10 |

## Issues Found

### P2 (Medium)
- [ ] 2 skills missing `version:` → Add version to mature skills
```

---

## Running the Evaluator

**On current repo:**
```
Evaluate this repository using the agentic-evaluator skill.
```

**On external repo:**
```
Clone [repo-url] and evaluate its agentic patterns.
```

**With threshold:**
```
Evaluate this repo. Fail if score < 70.
```

---

## Related Skills

- `project-scaffold` — Generate missing artifacts identified by evaluator

## Supporting Files

- `checklist.md` — Quick manual validation
- `report-template.md` — Output format
