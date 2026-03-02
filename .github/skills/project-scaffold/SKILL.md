---
name: project-scaffold
description: Interactive wizard that guides you through creating a comprehensive agentic development scaffold. Use when starting a new project or adding AI capabilities to an existing codebase. Asks about project goals, tech stack, team size, and workflows, then generates custom instructions, skills, agents, and MCP configurations.
user-invokable: true
disable-model-invocation: true
metadata:
  author: 0xrabbidfly
  version: "1.0.0"
---

# Project Scaffold Generator

## Purpose
Generate a complete, customized agentic development environment tailored to your specific project needs through guided questions.

---

## Size Limits (Enforced)

All generated artifacts MUST respect these limits:

| Artifact | Min | Max | Action if Exceeded |
|----------|-----|-----|-------------------|
| Root instructions | 50 | 300 | Split to `.github/instructions/` |
| Skills (SKILL.md) | 100 | 500 | Extract to supporting files |
| Agents | 100 | 400 | Split into sub-agents |
| Instructions | 50 | 200 | Split by concern |

## Progressive Disclosure Pattern

Structure ALL generated content using Anthropic's 3-tier pattern:

```
Tier 1: METADATA (~100 tokens)
├── name + description in frontmatter
├── Loaded at startup for ALL installed skills
└── Must clearly indicate WHEN to trigger

Tier 2: INSTRUCTIONS (1-5K tokens)  
├── Full SKILL.md body
├── Loaded only when skill is triggered
└── Core workflow — NOT reference material

Tier 3: RESOURCES (on-demand)
├── Bundled files in skill directory
├── Loaded only when explicitly referenced
└── Templates, checklists, examples, patterns
```

**Generation Rules:**
- Never embed examples >20 lines in SKILL.md — use `See: examples.md`
- Never embed templates in SKILL.md — use `See: templates/[name].template.[ext]`
- Never embed reference material — use `See: reference.md`
- Always create `templates/` subdirectory for reusable code

---

## When to Use
- Starting a new development project
- Adding AI coding assistant capabilities to existing project
- Standardizing team's AI tooling approach
- Migrating from basic to advanced agentic features

## Workflow

### Phase 1: Project Discovery

Ask the user these questions (use multiple-choice when possible):

1. **What type of project is this?**
   - New greenfield project
   - Existing codebase enhancement
   - Migration or refactor
   - Prototype/POC
   - Other (specify)

2. **What is your primary technology stack?**
   - Frontend: [React/Vue/Angular/Svelte/Other]
   - Backend: [Node.js/Python/Java/Go/Ruby/.NET/Other]
   - Database: [PostgreSQL/MySQL/MongoDB/Redis/Other]
   - Infrastructure: [AWS/Azure/GCP/On-prem/Hybrid]

3. **What languages will be used?** (multi-select)
   - JavaScript/TypeScript
   - Python
   - Java/Kotlin
   - C#/.NET
   - Go
   - Rust
   - Other (specify)

4. **Team size and structure?**
   - Solo developer
   - Small team (2-5 people)
   - Medium team (6-15 people)
   - Large team (16+ people)
   - Open source project

5. **What are your primary development workflows?** (multi-select)
   - Unit/integration testing
   - End-to-end testing
   - Code review process
   - CI/CD pipelines
   - Local development
   - Pair programming
   - Documentation generation
   - Performance monitoring
   - Security scanning

6. **Desired AI integration level?**
   - Basic (code completion, simple suggestions)
   - Intermediate (workflow automation, guided tasks)
   - Advanced (autonomous agents, complex orchestration)

7. **What external tools need integration?** (multi-select)
   - Git/GitHub/GitLab
   - Jira/Linear/Asana
   - Slack/Discord
   - Cloud provider CLI
   - Database tools
   - API testing tools
   - Monitoring/logging services
   - Other (specify)

### Phase 2: Generate Core Configuration

Based on answers, create:

1. **`.github/copilot-instructions.md`**
   - Project overview from answers
   - Technology stack guidelines
   - Team conventions (based on team size)

2. **Language-Specific Instructions**
   For each selected language, create `.github/instructions/[language].instructions.md`:
   - Language-specific best practices
   - Framework patterns
   - Common gotchas

3. **Framework Instructions** (if applicable)
   For major frameworks (React, Django, etc.):
   - Framework-specific patterns
   - Project structure conventions
   - Common patterns for this stack

### Phase 3: Generate Recommended Skills

Based on workflows selected, generate skills in `.github/skills/`.

**Required Skill Directory Structure:**
```
.github/skills/[skill-name]/
├── SKILL.md              # Core workflow (MAX 500 lines)
├── checklist.md          # Validation checklist (optional)
├── patterns.md           # Code patterns if >50 lines
├── examples.md           # Extended examples if >20 lines
└── templates/            # Reusable templates
    └── [name].template.[ext]
```

**Testing Workflow** → Create `testing/SKILL.md`:
```markdown
---
name: testing
description: Comprehensive testing workflow including unit, integration, and e2e tests. Use when adding tests or debugging test failures.
---

# Testing Skill {#testing-skill }

## Purpose {#purpose }
Streamline test creation and execution for [PROJECT_STACK]

## When to Use {#when-to-use }
- Writing new tests for features
- Debugging failing tests
- Running test suites
- Updating test coverage

## Instructions {#instructions }

1. **Identify test type needed**:
   - Unit: Single function/component isolation
   - Integration: Multiple components working together
   - E2E: Full user workflow

2. **Generate test scaffold**:
   [Language-specific test template]

3. **Run tests**:
   - Command: [project-specific command]
   - Watch mode: [if applicable]

4. **Validate coverage**:
   - Check coverage report
   - Identify gaps
   - Add missing tests

## Examples {#examples }
[Stack-specific examples]