# Agentic Evaluator — Quick Checklist

Use this checklist for fast manual audits. For automated scoring, use the full skill.

---

## Foundation (25 points)

- [ ] **Root instructions exist** (5 pts)
  - `.github/copilot-instructions.md` OR
  - `AGENTS.md` OR
  - `.claude/claude.md`

- [ ] **Root instructions quality** (5 pts)
  - [ ] Has project context/overview
  - [ ] Lists tech stack
  - [ ] Defines non-negotiables
  - [ ] 50+ lines

- [ ] **Organized structure** (5 pts)
  - [ ] `.github/skills/` folder
  - [ ] `.github/instructions/` folder
  - [ ] `.github/agents/` folder (if agents used)

- [ ] **README documents AI usage** (5 pts)
  - [ ] Mentions available skills
  - [ ] Explains how to invoke agents

- [ ] **MCP config exists** (5 pts)
  - [ ] `.github/mcp.json` OR `.vscode/mcp.json`
  - [ ] Valid JSON schema

---

## Skills (25 points)

- [ ] **Skills folder exists** (3 pts)
  - [ ] `.github/skills/` with at least 1 skill

- [ ] **Valid frontmatter** (5 pts)
  - [ ] `name:` present (lowercase-hyphenated)
  - [ ] `description:` present (includes "Use when...")

- [ ] **"When to Use" section** (4 pts)
  - [ ] Bullet list of trigger scenarios
  - [ ] Clear, actionable items

- [ ] **Examples included** (4 pts)
  - [ ] Code snippets or commands
  - [ ] Expected outputs shown

- [ ] **Right-sized** (4 pts)
  - [ ] 100-500 lines per skill
  - [ ] Single workflow focus

- [ ] **Cover key workflows** (5 pts)
  - [ ] Testing OR deployment OR domain-specific
  - [ ] At least 2 skills total

---

## Agents (20 points)

- [ ] **Agents folder exists** (2 pts)
  - [ ] `.github/agents/` with at least 1 agent

- [ ] **Valid frontmatter** (4 pts)
  - [ ] `name:` present
  - [ ] `description:` present
  - [ ] `tools:` array declared

- [ ] **Clear mission** (4 pts)
  - [ ] Single responsibility stated
  - [ ] Workflow with numbered phases

- [ ] **Handoff patterns** (3 pts)
  - [ ] References other agents (`@agent-name`)
  - [ ] Or explains when to use vs. other agents

- [ ] **Right-sized** (3 pts)
  - [ ] 100-400 lines per agent

- [ ] **Tools match MCP** (4 pts)
  - [ ] Declared tools exist in MCP config
  - [ ] No orphaned tool references

---

## Instructions (20 points)

- [ ] **Instructions folder exists** (2 pts)
  - [ ] `.github/instructions/` with at least 1 file

- [ ] **Has `applyTo` patterns** (4 pts)
  - [ ] Valid glob in frontmatter
  - [ ] Patterns are specific (not `**/*`)

- [ ] **Has code examples** (5 pts)
  - [ ] ✅ Good pattern shown
  - [ ] ❌ Bad pattern shown
  - [ ] Explanation of why

- [ ] **Right-sized** (4 pts)
  - [ ] 50-200 lines per file

- [ ] **Coverage analysis** (5 pts)
  - [ ] Major folders have matching instructions
  - [ ] No critical gaps (e.g., API routes, auth)

---

## Consistency (10 points)

- [ ] **Naming conventions** (2 pts)
  - [ ] Skills: `lowercase-hyphenated`
  - [ ] Agents: `lowercase-hyphenated` or `kebab-case`
  - [ ] Instructions: `context.instructions.md`

- [ ] **No duplicates** (2 pts)
  - [ ] No agent/prompt pairs for same purpose
  - [ ] No overlapping skills

- [ ] **Cross-refs resolve** (2 pts)
  - [ ] `@agent-name` references exist
  - [ ] "See: skill" links work

- [ ] **Version fields** (2 pts)
  - [ ] Mature skills have `version:` in frontmatter

- [ ] **Supporting files organized** (2 pts)
  - [ ] Templates in skill subdirectories
  - [ ] No loose files in `.github/`

---

## Scoring

Add up points from each section:

| Category | Your Score | Max |
|----------|------------|-----|
| Foundation | ___ | 25 |
| Skills | ___ | 25 |
| Agents | ___ | 20 |
| Instructions | ___ | 20 |
| Consistency | ___ | 10 |
| **TOTAL** | ___ | **100** |

### Grade Scale

| Score | Grade |
|-------|-------|
| 90-100 | A |
| 80-89 | B |
| 70-79 | C |
| 60-69 | D |
| <60 | F |
