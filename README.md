<div align="center">

<img src="https://upload.wikimedia.org/wikipedia/en/7/77/EricCartman.png" alt="Eric Cartman - The King of Meta Prompting" width="200"/>

# 🎯 Eric Cartman

### *The Meta Prompt Library*

**A development scaffold for leveraging the power of agents, commands, skills, and prompts in your projects.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)

*"Respect my authority!"* — Eric Cartman knows what he wants, and so should your AI agents.

</div>

---

## 🤔 What is This?

**Eric Cartman** is a meta prompt library — a springboard of Gen AI IDE artifacts to bootstrap any project with agentic development capabilities. Whether you're using GitHub Copilot, Claude, Cursor, or other AI coding assistants, this library provides battle-tested prompts, skills, and scaffolding to get you off on the right path.

### Why "Eric Cartman"?

Because Cartman is the ultimate meta-prompter. He knows exactly how to manipulate situations to get what he wants. Your AI agents should be just as effective (but, you know, for good).

---

## 🚀 Featured Prompts

### 1. 🔍 Agentic Evaluator

**Score any repository's agentic development maturity.**

Audits a codebase for best practices in agents, skills, instructions, MCP config, and prompts. Produces a scored report (A-F grade, 0-100 points) with specific remediation steps.

**Use When:**
- Auditing a new repository before contributing
- Evaluating your project's agentic maturity
- Onboarding to a codebase with agentic features
- CI gate to enforce minimum agentic standards
- Comparing multiple repos' implementations

**Scoring Categories:**
| Category | Points | Focus |
|----------|--------|-------|
| Foundation | 25 | Root instructions, structure, MCP config |
| Skills | 25 | Frontmatter, examples, right-sizing |
| Agents | 20 | Tools, mission, handoffs |
| Instructions | 20 | applyTo patterns, coverage |
| Consistency | 10 | Naming, no duplicates, cross-refs |

```
📍 Location: .github/skills/agentic-evaluator/
```

---

### 2. 🏗️ Project Scaffold

**Interactive wizard for creating a comprehensive agentic development scaffold.**

Guides you through creating custom instructions, skills, agents, and MCP configurations tailored to your specific project needs.

**Use When:**
- Starting a new development project
- Adding AI coding assistant capabilities to existing codebase
- Standardizing team's AI tooling approach
- Migrating from basic to advanced agentic features

**What It Generates:**
- `copilot-instructions.md` — Root instructions for AI context
- Custom skills for your workflows (testing, deployment, etc.)
- Agent configurations for specialized tasks
- MCP (Model Context Protocol) server configs
- Progressive disclosure structure (metadata → body → bundled files)

```
📍 Location: .github/skills/project-scaffold/
```

---

### 3. 🩺 Health Audit

**Regular audit checklist for maintaining quality across all agentic artifacts.**

Validates YAML frontmatter, checks cross-references, counts tokens, and ensures your skills stay accurate and useful.

**Use When:**
- Quarterly skill reviews
- After major project changes
- Before onboarding new team members
- Post-incident documentation review

**Automated Checks:**
```bash
# Validate YAML frontmatter
node .github/skills/health-audit/validate-frontmatter.js

# Check cross-references
node .github/skills/health-audit/check-cross-refs.js

# Count tokens in skills
node .github/skills/health-audit/count-tokens.js
```

```
📍 Location: .github/skills/health-audit/
```

---

### 4. 📚 Session Learning

**Extract reusable patterns from coding sessions to build institutional knowledge.**

Analyzes completed coding sessions to identify patterns worth capturing as persistent instructions or skills. Turns one-time solutions into reusable knowledge.

**Use When:**
- At the end of long coding sessions (30+ minutes)
- After solving tricky debugging problems
- When you corrected the AI multiple times on the same issue
- After discovering framework quirks or workarounds
- When establishing new project conventions

**What It Extracts:**
- **Error Resolutions** — How specific errors were diagnosed and fixed
- **User Corrections** — Patterns where you corrected the AI's approach
- **Workarounds** — Solutions to framework/library quirks
- **Debugging Techniques** — Effective debugging patterns
- **Project Conventions** — New conventions established during the session

**Output Locations:**
| Pattern Type | Saved To |
|--------------|----------|
| Quick rules | `copilot-instructions.md` |
| File-specific rules | `instructions/*.instructions.md` |
| Complex workflows | `skills/*/SKILL.md` |

```
📍 Location: .github/skills/session-learning/
```

---

### 5. ✅ Verification Loop

**Pre-PR quality gate running comprehensive validation in 7 phases.**

Runs build, type-check, lint, tests, security scans, and hygiene checks before creating a pull request. Catches issues locally before they reach CI/CD.

**Use When:**
- Before creating a pull request
- After completing a feature or significant refactoring
- After merging main into your branch
- As a final check before deployment
- Every 30 minutes during long coding sessions

**Verification Phases:**
| Phase | Type | Checks |
|-------|------|--------|
| Build | ✅ Blocking | Syntax, imports, compilation |
| Type Check | ⚠️ Soft | Type safety, `any` leaks |
| Lint | ⚠️ Soft | Code style, unused vars |
| Tests | ✅ Blocking | Unit tests, 80% coverage target |
| Security | ✅ Blocking | Constitutional violations, secrets |
| Hygiene | ⚠️ Soft | Import style, ARIA labels |
| Git Diff | 📋 Info | Changed files review |

**Constitutional Checks:**
- No `localStorage`/`sessionStorage` usage
- No hardcoded secrets or API keys
- No `console.log` in production code
- No hardcoded English text (i18n compliance)

```
📍 Location: .github/skills/verification-loop/
```

---

## 📁 Repository Structure

```
.github/
├── copilot-instructions.md     # Root AI instructions
├── mcp.json                    # MCP server configuration
├── skills/                     # Reusable AI skills
│   ├── agentic-evaluator/      # ⭐ Featured
│   ├── project-scaffold/       # ⭐ Featured
│   ├── health-audit/           # ⭐ Featured
│   ├── session-learning/       # ⭐ Featured
│   └── verification-loop/      # ⭐ Featured
├── agents/                     # Specialized agent configs
├── instructions/               # File-pattern-specific rules
└── prompts/                    # Reusable prompt templates
```

---

## 🎬 Getting Started

### 1. Clone or Copy

Copy the `.github/` folder structure into your project, or fork this repo as a starting point.

### 2. Run the Evaluator

Ask your AI assistant:
```
Evaluate this repository's agentic development patterns using the agentic-evaluator skill.
```

### 3. Generate Your Scaffold

If starting fresh:
```
Help me create a project scaffold using the project-scaffold skill.
```

### 4. Maintain with Health Audits

Run periodic checks:
```
Run a health audit on our agentic artifacts.
```

---

## 🧠 Philosophy

This library follows key principles for effective agentic development:

1. **Progressive Disclosure** — Metadata first, details on-demand
2. **Right-Sizing** — Skills should be 100-500 lines, not monolithic
3. **Clear Triggers** — Every skill has explicit "When to Use" scenarios
4. **Actionable Output** — Graded scores and specific remediation steps
5. **Cross-Platform** — Works with Copilot, Claude, Cursor, and more

---

## 🤝 Contributing

PRs welcome! If you have prompts, skills, or patterns that have worked well for your team, we'd love to include them.

---

## 📜 License

MIT — Use freely, fork wildly, prompt responsibly.

---

<div align="center">

*"Screw you guys, I'm going home... to write better prompts."*

**Made with 🍟 by developers who respect Cartman's authority**

</div>
