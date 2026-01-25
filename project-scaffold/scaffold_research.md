# Project Scaffold Research: Agentic Development Starter Package

## Executive Summary

This document provides a comprehensive framework for creating development project scaffolds with agentic features. It synthesizes best practices from Anthropic, VS Code, GitHub Copilot, and Cursor teams to guide the creation of custom instructions, skills, agents, and MCP configurations.

---

## Table of Contents

1. [Core Concepts](#core-concepts)
2. [Architecture Overview](#architecture-overview)
3. [Meta-Prompt Workflow](#meta-prompt-workflow)
4. [Design Principles](#design-principles)
5. [File Structure Standards](#file-structure-standards)
6. [Implementation Guide](#implementation-guide)
7. [Skill Template](#skill-template)
8. [Best Practices](#best-practices)
9. [Resources](#resources)

---

## Core Concepts

### What is an Agentic Development Scaffold?

An agentic development scaffold is a pre-configured project structure that includes:

- **Custom Instructions**: Project-specific guidance for AI coding assistants
- **Skills**: Modular, reusable capabilities for specialized tasks
- **Agents**: Specialized AI workers with domain-specific contexts
- **Sub-agents**: Focused task delegators for complex workflows
- **MCP Servers**: Model Context Protocol integrations for external tools
- **Commands**: Quick-access shortcuts for common workflows

### Progressive Disclosure Architecture

The fundamental principle organizing all agentic features:

1. **Discovery** (Metadata): Name + description loads first (~100 tokens)
2. **Instructions** (Body): Full content loads when relevant (~1-5K tokens)
3. **Resources** (On-demand): Referenced files load only when needed

This three-tier system enables efficient context management while supporting dozens of installed capabilities.

---

## Architecture Overview

```
project-root/
├── .github/
│   ├── copilot-instructions.md          # Workspace-wide instructions
│   ├── skills/                           # Project-specific skills
│   │   ├── testing/
│   │   │   ├── SKILL.md
│   │   │   └── test-template.js
│   │   ├── deployment/
│   │   │   ├── SKILL.md
│   │   │   └── deploy-checklist.md
│   │   └── code-review/
│   │       └── SKILL.md
│   ├── instructions/                     # Conditional instructions
│   │   ├── typescript.instructions.md
│   │   ├── python.instructions.md
│   │   └── api.instructions.md
│   └── agents/                           # Custom agents
│       ├── backend-specialist.md
│       └── ui-designer.md
├── .claude/
│   ├── claude.md                         # Claude Code instructions
│   └── skills/                           # Legacy skill location
├── .cursor/
│   └── prompts/                          # Cursor-specific prompts
├── .vscode/
│   ├── settings.json                     # MCP server configs
│   └── extensions.json
└── AGENTS.md                             # Root agent instructions
```

---

## Meta-Prompt Workflow

### The "New Project Wizard" Skill

This meta-skill guides you through creating a comprehensive project scaffold by asking targeted questions about your project goals, then generating appropriate configurations.

**Location**: `.github/skills/project-scaffold/SKILL.md`

**Purpose**: Interactive project setup that creates custom instructions, skills, and configurations tailored to your specific needs.

**Usage**: When starting a new project, invoke this skill to:
1. Answer questions about project type, stack, team size, and workflows
2. Receive generated custom instructions and skill recommendations
3. Get a pre-configured directory structure
4. Obtain MCP server suggestions for your toolchain

---

## Design Principles

### From Anthropic Engineering

#### 1. **Context as Finite Resource**
> "Find the smallest set of high-signal tokens that maximize the likelihood of your desired outcome."

**Application**:
- Keep instructions minimal and focused
- Use metadata for discovery, full content only when needed
- Reference files by name rather than embedding content

#### 2. **Right Altitude Specificity**
Avoid two extremes:
- ❌ Too specific: Brittle, hardcoded logic
- ❌ Too vague: Assumes shared understanding with AI

✅ **Sweet spot**: Specific guidance with flexible heuristics

#### 3. **Evaluation-Driven Development**
- Start with representative tasks
- Observe where agents struggle
- Build skills incrementally to address gaps
- Iterate based on real usage, not anticipated needs

#### 4. **Tool Clarity**
- Tools must be self-contained and unambiguous
- If humans can't choose which tool to use, agents can't either
- Minimal viable tool sets prevent confusion

### From VS Code/Copilot

#### 5. **Specialization Over Generalization**
Create focused skills for specific workflows rather than monolithic configurations.

#### 6. **Composition Patterns**
Skills should combine naturally for complex multi-step processes.

#### 7. **Short and Self-Contained Instructions**
> "Each instruction should be a single, simple statement."

#### 8. **Context Degradation Awareness**
Model accuracy decreases as token count increases. Design for efficiency.

---

## File Structure Standards

### 1. Custom Instructions

#### `.github/copilot-instructions.md`
**Purpose**: Single workspace-wide instruction file
**Scope**: Applies to all files in project
**Use for**: Project-wide coding standards, architectural patterns, team conventions

```markdown
# Project Custom Instructions

## Architecture
This project uses [architecture pattern]. Follow these principles:
- Principle 1
- Principle 2

## Code Style
- Style guideline 1
- Style guideline 2

## Team Conventions
- Convention 1
- Convention 2
```

#### `*.instructions.md` (Conditional)
**Purpose**: File-type-specific instructions
**Location**: `.github/instructions/`
**Use for**: Language-specific guidelines, framework patterns

```markdown
---
name: TypeScript Guidelines
description: Coding standards for TypeScript files
applyTo: "**/*.ts,**/*.tsx"
---

# TypeScript-Specific Guidelines

## Type Safety
- Always define explicit return types for functions
- Use interfaces for object shapes
- Prefer unknown over any

## Project Patterns
- Follow the repository pattern for data access
- Use dependency injection for services
```

### 2. Skills (SKILL.md)

#### Frontmatter (Required)
```yaml
---
name: skill-name              # Lowercase, hyphens, max 64 chars
description: Clear explanation of what this skill does and when to use it. Max 1024 characters.
---
```

#### Body Structure
```markdown
# Skill Name

## Purpose
Brief explanation of the skill's goal.

## When to Use
- Use case 1
- Use case 2
- Use case 3

## Instructions
Step-by-step procedures:

1. First step with clear action
2. Second step with expected outcome
3. Third step with validation

## Examples
Concrete examples of usage.

## Supporting Files
Reference files in this directory:
- `template.js` - Boilerplate code
- `checklist.md` - Validation checklist
```

### 3. Agents

#### `.github/agents/[agent-name].md`
**Purpose**: Specialized agent with domain-specific context
**Use for**: Complex workflows requiring focused expertise

```markdown
# Agent Name

## Role
Describe the agent's specialized function.

## Context
Domain-specific knowledge the agent needs.

## Capabilities
- Capability 1
- Capability 2

## Workflow
1. Task breakdown approach
2. Decision-making criteria
3. Output format

## Constraints
- Constraint 1
- Constraint 2
```

### 4. MCP Server Configuration

#### `.vscode/settings.json`
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "./src"]
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "${env:GITHUB_TOKEN}"
      }
    }
  }
}
```

---

## Implementation Guide

### Phase 1: Discovery & Planning

#### Questions to Answer:

1. **Project Type**
   - New greenfield project?
   - Existing codebase enhancement?
   - Migration/refactor?

2. **Technology Stack**
   - Primary languages?
   - Frameworks & libraries?
   - Build tools & package managers?

3. **Team Context**
   - Solo developer?
   - Small team (2-5)?
   - Large team (6+)?

4. **Development Workflows**
   - Testing strategy?
   - Deployment process?
   - Code review practices?

5. **AI Integration Depth**
   - Basic code completion?
   - Active agentic development?
   - Full autonomous capabilities?

### Phase 2: Core Configuration

#### Step 1: Create Root Instructions
Create `.github/copilot-instructions.md` with:
- Project overview
- Architecture principles
- Core conventions

#### Step 2: Add Conditional Instructions
For each major file type/context:
1. Create `[context].instructions.md`
2. Set `applyTo` glob pattern
3. Define specific guidelines

#### Step 3: Identify Skill Candidates
Common skills to consider:
- `testing` - Test generation & execution
- `deployment` - Deployment procedures
- `code-review` - Review checklists
- `debugging` - Debugging workflows
- `refactoring` - Safe refactoring patterns
- `documentation` - Doc generation standards

### Phase 3: Advanced Configuration

#### Step 4: Design Custom Agents
For complex domains, create specialized agents:
- Backend architecture specialist
- Frontend/UI designer
- DevOps/infrastructure expert
- Security reviewer
- Performance optimizer

#### Step 5: Configure MCP Servers
Identify external integrations:
- Filesystem access
- Git/GitHub operations
- Database connections
- API testing tools
- Cloud provider CLIs

#### Step 6: Create Command Shortcuts
Define quick-access workflows in `.clauderc` or similar.

---

## Skill Template

### Basic Skill Template

```markdown
---
name: example-skill
description: This skill helps with [specific task]. Use when you need to [use case 1] or [use case 2]. Especially useful for [scenario].
---

# Example Skill

## Purpose
[Clear statement of what this skill accomplishes]

## When to Use This Skill
- Scenario 1: [Description]
- Scenario 2: [Description]
- Scenario 3: [Description]

## When NOT to Use This Skill
- Anti-pattern 1
- Anti-pattern 2

## Prerequisites
- Requirement 1
- Requirement 2

## Step-by-Step Instructions

### Phase 1: [Phase Name]
1. **Action**: [Clear, specific action]
   - Detail 1
   - Detail 2
   - **Expected outcome**: [What should happen]

2. **Action**: [Next action]
   - Detail 1
   - **Expected outcome**: [What should happen]

### Phase 2: [Phase Name]
[Continue with numbered steps]

## Examples

### Example 1: [Scenario]
```
[Code or command example]
```

**Result**:
```
[Expected output]
```

### Example 2: [Scenario]
[Another concrete example]

## Common Pitfalls
- Pitfall 1: [Description] → Solution: [Fix]
- Pitfall 2: [Description] → Solution: [Fix]

## Validation Checklist
- [ ] Checkpoint 1
- [ ] Checkpoint 2
- [ ] Checkpoint 3

## Supporting Files
- `template.[ext]` - [Description]
- `checklist.md` - [Description]

## Related Skills
- `related-skill-1` - [When to use instead]
- `related-skill-2` - [How they combine]
```

### Advanced Skill Template (with Sub-agents)

```markdown
---
name: advanced-workflow
description: Multi-phase workflow that coordinates multiple specialized tasks. Use for [complex scenario] requiring [sub-task 1], [sub-task 2], and [sub-task 3].
---

# Advanced Workflow Skill

## Architecture
This skill uses a coordinator pattern with specialized sub-agents.

## Sub-Agent Roles
1. **Analyzer**: Examines codebase and identifies issues
2. **Implementer**: Makes code changes following analysis
3. **Validator**: Tests and validates changes

## Workflow

### Phase 1: Analysis (Sub-agent: Analyzer)
[Instructions for analysis phase]
- Returns: Summary of findings (1000-2000 tokens)

### Phase 2: Implementation (Sub-agent: Implementer)
[Instructions for implementation]
- Context: Receives analysis summary
- Returns: Change summary

### Phase 3: Validation (Sub-agent: Validator)
[Instructions for validation]
- Context: Receives change summary
- Returns: Test results

## Coordination Strategy
- Main agent maintains state in `NOTES.md`
- Sub-agents receive focused context
- Summaries flow between phases
- Progress tracked in persistent notes
```

---

## Best Practices

### DO:
✅ Start minimal, iterate based on observed failures
✅ Use progressive disclosure (metadata → instructions → resources)
✅ Create focused, single-purpose skills
✅ Write clear descriptions that explain WHEN to use skills
✅ Include concrete examples in skills
✅ Reference supporting files by name
✅ Think from Claude's perspective when naming/describing
✅ Keep instructions short and self-contained
✅ Use XML tags or Markdown headers for organization
✅ Test skills on representative tasks before deployment
✅ Maintain skills in version control
✅ Review community skills before adoption
✅ Use sub-agents for complex, multi-phase tasks

### DON'T:
❌ Pre-load all documentation upfront
❌ Create overlapping or ambiguous tools/skills
❌ Write vague descriptions ("helps with coding")
❌ Stuff edge cases into prompts
❌ Anticipate all needs before testing
❌ Create monolithic instruction files
❌ Assume shared understanding with AI
❌ Ignore security when installing skills
❌ Hard-code brittle logic in instructions
❌ Duplicate context across multiple files
❌ Write instructions for inline suggestions
❌ Mix mutually exclusive contexts in single skills

### Context Management:
- **Compaction**: Summarize conversations when approaching limits
- **Structured Notes**: Use persistent NOTES.md for long-running tasks
- **Sub-Agent Delegation**: Focused contexts for specialized work
- **Tool Result Clearing**: Low-risk compaction opportunity
- **Just-in-Time Retrieval**: Load data dynamically vs. upfront

### Security Considerations:
- Only install skills from trusted sources
- Audit bundled files before deployment
- Review code dependencies carefully
- Check for external network connections
- Use terminal tool controls for script execution

---

## The "Project Scaffold Generator" Skill

Here's the actual meta-skill you can use to kickstart new projects:

### File: `.github/skills/project-scaffold/SKILL.md`

```markdown
---
name: project-scaffold-generator
description: Interactive wizard that guides you through creating a comprehensive agentic development scaffold. Use when starting a new project or adding AI capabilities to an existing codebase. Asks about project goals, tech stack, team size, and workflows, then generates custom instructions, skills, agents, and MCP configurations.
---

# Project Scaffold Generator

## Purpose
Generate a complete, customized agentic development environment tailored to your specific project needs through guided questions.

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

Based on workflows selected, generate skills in `.github/skills/`:

**Testing Workflow** → Create `testing/SKILL.md`:
```markdown
---
name: testing
description: Comprehensive testing workflow including unit, integration, and e2e tests. Use when adding tests or debugging test failures.
---

# Testing Skill

## Purpose
Streamline test creation and execution for [PROJECT_STACK]

## When to Use
- Writing new tests for features
- Debugging failing tests
- Running test suites
- Updating test coverage

## Instructions

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

## Examples
[Stack-specific examples]
```

**Deployment Workflow** → Create `deployment/SKILL.md`:
```markdown
---
name: deployment
description: Deployment checklist and procedures for [INFRASTRUCTURE]. Use before deploying to staging or production.
---

# Deployment Skill

[Infrastructure-specific deployment procedures]
```

**Code Review Workflow** → Create `code-review/SKILL.md`:
```markdown
---
name: code-review
description: Systematic code review checklist covering [PROJECT STANDARDS]. Use when reviewing PRs or preparing code for review.
---

# Code Review Skill

[Team-size-appropriate review guidelines]
```

Additional skills based on selections:
- `debugging` - If testing selected
- `documentation` - If open source or large team
- `performance` - If monitoring selected
- `security-review` - If security scanning selected
- `api-design` - If backend development
- `component-design` - If frontend framework

### Phase 4: Generate Custom Agents (if Advanced AI selected)

Create specialized agents in `.github/agents/`:

1. **Backend Specialist** (`backend-specialist.md`)
   - Database design patterns
   - API architecture
   - Performance optimization
   - Security best practices

2. **Frontend Specialist** (`frontend-specialist.md`)
   - Component architecture
   - State management
   - Performance optimization
   - Accessibility

3. **DevOps Specialist** (`devops-specialist.md`)
   - Infrastructure as code
   - CI/CD optimization
   - Monitoring setup
   - Deployment strategies

4. **[Domain] Specialist** (based on project type)
   - Custom agent for specific domain needs

### Phase 5: Generate MCP Server Configuration

Based on tool integrations selected, create `.vscode/settings.json`:

```json
{
  "mcpServers": {
    // Add servers for each selected integration
  }
}
```

Common servers:
- `filesystem` - Always include
- `github` - If Git/GitHub selected
- `[database]` - If database access needed
- `[cloud-provider]` - If cloud CLI selected

### Phase 6: Generate Project Documentation

Create `docs/agentic-setup.md`:
- Overview of installed capabilities
- How to use each skill
- Agent specializations
- MCP server usage
- Customization guide
- Team onboarding instructions

### Phase 7: Summary & Next Steps

Present to user:

```
✅ Created core configuration files:
   - .github/copilot-instructions.md
   - [N] conditional instruction files

✅ Generated [N] skills:
   - [List skills with brief descriptions]

✅ Created [N] specialized agents:
   - [List agents with roles]

✅ Configured [N] MCP servers:
   - [List servers with purposes]

✅ Documentation:
   - docs/agentic-setup.md

🎯 Next Steps:
1. Review generated files and customize for your specific needs
2. Test each skill with representative tasks
3. Add team-specific conventions to instructions
4. Configure environment variables for MCP servers
5. Commit configuration to version control
6. Share onboarding doc with team

💡 Pro Tips:
- Start with minimal instructions, iterate based on usage
- Monitor which skills get used most, refine others
- Add examples to skills based on real project code
- Review and update quarterly as project evolves
```

## Supporting Files

### `templates/copilot-instructions.md`
[Base template with placeholders]

### `templates/skill-template.md`
[Generic skill structure]

### `templates/agent-template.md`
[Generic agent structure]

### `templates/mcp-config.json`
[Common MCP server configurations]

## Validation Checklist
- [ ] All required files created
- [ ] File paths follow standards
- [ ] YAML frontmatter is valid
- [ ] Descriptions are clear and actionable
- [ ] No duplicate or overlapping skills
- [ ] MCP servers have required env vars documented
- [ ] Documentation includes team onboarding
- [ ] All templates use actual project context, not placeholders

## Related Skills
- `skill-editor` - Modify existing skills
- `instruction-optimizer` - Refine instructions based on usage
- `mcp-configurator` - Add/modify MCP servers
```

---

## Resources

### Official Documentation

**Anthropic**:
- [Agent Skills Engineering](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- [Effective Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Claude Code Documentation](https://docs.claude.com/)

**VS Code / GitHub Copilot**:
- [Agent Skills](https://code.visualstudio.com/docs/copilot/customization/agent-skills)
- [Custom Instructions](https://code.visualstudio.com/docs/copilot/customization/custom-instructions)
- [Copilot Extensibility](https://code.visualstudio.com/api/extension-guides/copilot)

**Model Context Protocol**:
- [MCP Documentation](https://modelcontextprotocol.io/)
- [Official MCP Servers](https://github.com/modelcontextprotocol)

### Community Resources

- [agentskills.io](https://agentskills.io/) - Open standard for agent skills
- [github/awesome-copilot](https://github.com/github/awesome-copilot) - Community skills catalog
- [Anthropic Cookbook](https://github.com/anthropics/anthropic-cookbook) - Agent patterns

---

## Quick Start Checklist

When starting a new project:

- [ ] Run the project-scaffold-generator skill
- [ ] Answer all discovery questions
- [ ] Review generated configuration files
- [ ] Customize with project-specific details
- [ ] Test each skill with representative tasks
- [ ] Configure MCP server environment variables
- [ ] Commit to version control
- [ ] Document for team onboarding
- [ ] Iterate based on actual usage
- [ ] Review quarterly and refine

---

## Appendix: Example Complete Scaffold

### Small TypeScript/React Project

```
my-app/
├── .github/
│   ├── copilot-instructions.md
│   ├── skills/
│   │   ├── testing/
│   │   │   ├── SKILL.md
│   │   │   └── vitest.config.template.ts
│   │   ├── component-design/
│   │   │   ├── SKILL.md
│   │   │   └── component-template.tsx
│   │   └── code-review/
│   │       └── SKILL.md
│   └── instructions/
│       ├── typescript.instructions.md
│       └── react.instructions.md
├── .vscode/
│   └── settings.json  # MCP servers
└── docs/
    └── agentic-setup.md
```

**copilot-instructions.md**:
```markdown
# My App - AI Assistant Guidelines

## Project Overview
React 18 + TypeScript + Vite frontend application.

## Architecture
- Component-based architecture
- Custom hooks for logic reuse
- Context API for global state
- Vitest + React Testing Library

## Code Standards
- Functional components only
- TypeScript strict mode
- Props interfaces defined above components
- One component per file

## Naming Conventions
- Components: PascalCase
- Hooks: camelCase with 'use' prefix
- Utils: camelCase
- Constants: UPPER_SNAKE_CASE
```

---

## Version History

- v1.0 (2026-01-24): Initial research document
  - Synthesized Anthropic, VS Code, Copilot guidance
  - Created project-scaffold-generator skill
  - Defined standard file structures
  - Documented best practices

---

## Contributing

This is a living document. Update based on:
- New official guidance from tool vendors
- Team learnings from real usage
- Emerging patterns in agent development
- Community best practices

---

## License

This research document is provided as-is for project planning purposes. External resources are property of their respective owners (Anthropic, Microsoft, GitHub).
