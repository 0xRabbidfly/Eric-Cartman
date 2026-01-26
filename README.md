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

### 2. 🧭 Project Guide

**A teaching-first exploration companion for any codebase.**

Simulates plan mode with an educational focus. Provides high-level overviews, architecture diagrams, and guided deep-dives into any area of the project. Emphasizes building mental models and offers follow-up questions to continue the learning journey.

**Use When:**
- Onboarding to a new or unfamiliar codebase
- Understanding architectural decisions and trade-offs
- Exploring a specific subsystem in depth
- Preparing for a code review or contribution
- Explaining a codebase to stakeholders or new team members

**Teaching Approach:**
- Starts with bird's-eye overview, zooms in on request
- Uses Mermaid and ASCII diagrams for visual learning
- Acknowledges complexity; layers understanding gradually
- Ends interactions with 2-3 thoughtful follow-up questions
- Adapts to beginner, experienced, or returning developer

```
📍 Location: .github/skills/project-guide/
```

---

### 3. 🏗️ Project Scaffold

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

### 4. 🩺 Health Audit

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

### 5. 📚 Session Learning

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

### 6. 🎭 Eric Cartman Agent

**A Cartman-flavored project guide for codebase exploration.**

Combines the teaching methodology of the Project Guide skill with Eric Cartman's iconic personality. Get thorough, helpful codebase walkthroughs delivered with attitude, authority, and demands for Cheesy Poofs.

**Use When:**
- You want guided codebase exploration with entertainment value
- Onboarding feels dry and you need some personality
- You want the Project Guide skill's approach but as a persistent persona
- Teaching junior developers who appreciate humor with their learning

**Personality Highlights:**
- Acts like explaining things is a huge favor (but actually helps thoroughly)
- Blames messy code on "hippies" or previous developers being "totally weak"
- Grudgingly admits when you ask a good question
- Demands respect for his authoritah on all architectural matters
- References Cheesy Poofs as appropriate compensation for guidance

**Invocation:**
```
@eric-cartman Give me a tour of this codebase
@eric-cartman Explain the authentication flow
@eric-cartman What's going on in the API layer?
```

```
📍 Location: .github/agents/eric-cartman.md
```

---

### 7. ✅ Verification Loop

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

### 8. 🔍 Last 30 Days Research

**Research any topic across Reddit, X, and the web from the last 30 days.**

Surfaces what people are actually discussing, recommending, and debating right now. Returns engagement-weighted results with copy-paste-ready prompts for your target tool.

**Use When:**
- Learning new prompting techniques for AI tools (Midjourney, ChatGPT, etc.)
- Finding recommendations ("best Claude Code skills", "top AI tools")
- Catching up on news ("what's happening with OpenAI")
- Understanding current community sentiment on any topic

**Query Types:**
| Type | Example | Output |
|------|---------|--------|
| Prompting | "photorealistic people for Midjourney" | Techniques + copy-paste prompts |
| Recommendations | "best RAG frameworks 2026" | Ranked list with engagement metrics |
| News | "latest AI announcements" | Recent developments with sources |
| General | "skills vs RAG for document analysis" | Community insights + discussion summary |

**Modes:**
- **Full Mode** (OpenAI + xAI keys): Reddit + X + Web search with engagement metrics
- **Partial Mode** (one key): Single platform + web fallback
- **Web-Only Mode** (no keys): WebSearch only — still useful

```
📍 Location: .claude/skills/last30days/
```

---

## 💻 Windows Setup for Claude Code Skills

Claude Code skills with Python scripts require specific setup on Windows. Follow these steps:

### Prerequisites

1. **Python 3.10+** installed and in PATH
2. **Claude Code** CLI installed (`npm install -g @anthropic-ai/claude-code`)

### Installing the `last30days` Skill

#### Step 1: Locate the Skills Directory

Skills live in `~/.claude/skills/` (your user profile). On Windows:
```powershell
# Check if directory exists
Test-Path "$env:USERPROFILE\.claude\skills"

# Create if needed
New-Item -ItemType Directory -Path "$env:USERPROFILE\.claude\skills" -Force
```

#### Step 2: Copy the Skill

From this repo, copy the skill folder:
```powershell
# From the Eric-Cartman repo root
Copy-Item -Recurse ".\.claude\skills\last30days" "$env:USERPROFILE\.claude\skills\"
```

#### Step 3: Install Python Dependencies

```powershell
# Navigate to the skill's scripts folder
cd "$env:USERPROFILE\.claude\skills\last30days\scripts"

# Install dependencies (if requirements.txt exists)
pip install requests python-dotenv
```

#### Step 4: Configure API Keys (Optional but Recommended)

Create a config file for enhanced Reddit/X search:
```powershell
# Create config directory
New-Item -ItemType Directory -Path "$env:USERPROFILE\.config\last30days" -Force

# Create .env file
@"
# last30days API Configuration
# Both keys are optional - skill works with WebSearch fallback

# For Reddit research (uses OpenAI's web_search tool)
OPENAI_API_KEY=your-openai-key-here

# For X/Twitter research (uses xAI's x_search tool)  
XAI_API_KEY=your-xai-key-here
"@ | Out-File -FilePath "$env:USERPROFILE\.config\last30days\.env" -Encoding UTF8
```

#### Step 5: Verify Installation

Open Claude Code and test:
```
/last30days best Claude Code skills
```

### Troubleshooting Windows Issues

| Issue | Solution |
|-------|----------|
| `python3` not found | Windows uses `python` not `python3`. The skill handles this. |
| Permission denied on scripts | Run PowerShell as Administrator or check execution policy |
| Path too long errors | Enable long paths: `git config --system core.longpaths true` |
| `.env` not loading | Ensure no BOM in file: save as UTF-8 without BOM |

### Windows vs. Unix Path Notes

The skill uses `~/.config/last30days/.env` which translates on Windows to:
```
%USERPROFILE%\.config\last30days\.env
```

If you prefer a Windows-native location, set the environment variable:
```powershell
$env:LAST30DAYS_CONFIG = "C:\Users\YourName\.last30days\.env"
```

---

## 📁 Repository Structure

```
.github/
├── copilot-instructions.md     # Root AI instructions
├── mcp.json                    # MCP server configuration
├── skills/                     # Reusable AI skills (GitHub Copilot)
│   ├── agentic-evaluator/      # ⭐ Featured
│   ├── project-guide/          # ⭐ Featured
│   ├── project-scaffold/       # ⭐ Featured
│   ├── health-audit/           # ⭐ Featured
│   ├── session-learning/       # ⭐ Featured
│   └── verification-loop/      # ⭐ Featured
├── agents/                     # Specialized agent configs
│   └── eric-cartman.md         # 🎭 Cartman-flavored project guide
├── instructions/               # File-pattern-specific rules
└── prompts/                    # Reusable prompt templates

.claude/
├── settings.local.json         # Local Claude Code permissions (gitignored)
└── skills/                     # Claude Code skills
    └── last30days/             # 🔍 Research skill
        ├── SKILL.md            # Skill definition
        ├── SPEC.md             # Technical specification
        ├── TASKS.md            # Implementation checklist
        ├── scripts/            # Python implementation
        │   ├── last30days.py   # Main CLI script
        │   └── lib/            # Modules (cache, search, render)
        ├── fixtures/           # Test data samples
        └── tests/              # Unit tests
```

> **Note:** `.github/skills/` is for GitHub Copilot, `.claude/skills/` is for Claude Code.
> The same skill can be adapted for both by adjusting frontmatter and paths.

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
