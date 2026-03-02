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

### 6. 🗒️ Session Log

**Capture session insights and metrics for later analysis.**

Logs checkpoint snapshots and end-of-session summaries into `.github/sessions/` so other skills can analyze what happened over time.

**3 Modes of Usage:**
- **Checkpoint** — `/session-log checkpoint` auto-extracts recent insights/challenges/metrics
- **End** — `/session-log end` generates a comprehensive session report
- **Message** — `/session-log "..."` logs a specific note (auto-categorized)

**Use When:**
- You want lightweight logging during a long session
- You want a structured end-of-session summary for later reference
- You want to build a dataset for process improvement over time
- You want to capture friction points and successful workflows as you go

**Invocation:**
```
/session-log checkpoint
/session-log "Hit 39 TypeScript errors in auth module"
/session-log end
```

```
📍 Location: .github/skills/session-log/
```

---

### 7. 📈 Insights Report

**Generate a comprehensive cross-session insights report from your session logs.**

Analyzes everything in `.github/sessions/` to surface patterns (what’s working, what’s causing friction, and what to change next). Useful for retrospectives, onboarding, and tightening project conventions.

**Use When:**
- Weekly/monthly retrospectives
- Preparing to improve team workflows and developer guidance
- Identifying recurring issues across multiple sessions
- Summarizing progress across multiple workstreams

**Invocation:**
```
/insights-report
/insights-report --from 2026-02-01 --to 2026-02-09
```

```
📍 Location: .github/skills/insights-report/
```

---

### 8. 🎭 Eric Cartman Agent

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

### 9. ✅ Verification Loop

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

### 10. 🔍 Last 30 Days Research

**Research any topic across Reddit, X, and the web from the last 30 days.**

Surfaces what people are actually discussing, recommending, and debating right now. Returns AI-synthesized insights with engagement metrics, key patterns, and source citations.

**Available for both Claude Code and GitHub Copilot:**
- **Claude Code:** `.claude/skills/last30days/`
- **GitHub Copilot:** `.github/skills/last30days/`

**Use When:**
- Learning new prompting techniques for AI tools (Midjourney, ChatGPT, etc.)
- Finding recommendations ("best Claude Code skills", "top AI tools")
- Catching up on news ("what's happening with OpenAI")
- Understanding current community sentiment on any topic
- Market research ("Seattle housing market", "NYC rent trends")

**Output Includes:**
| Section | Description |
|---------|-------------|
| What I Learned | AI-synthesized narrative paragraph |
| Key Patterns | 3-5 actionable insights with bold labels |
| Stats Tree | Source counts with engagement totals |
| Full Report | Detailed posts/threads with URLs and quotes |

**API Keys (Optional):**
- Works without any API keys using web search fallback
- Add `OPENAI_API_KEY` → Reddit threads with real upvotes & comments
- Add `XAI_API_KEY` → X posts with real likes & reposts
- Keys go in `~/.config/last30days/.env`

**Copilot Version Notes:**
The GitHub Copilot version saves a full `report.md` to your local share folder:
- **Windows:** `%USERPROFILE%\.local\share\last30days\out\report.md`
- **macOS/Linux:** `~/.local/share/last30days/out/report.md`

```
📍 Locations: 
   Claude Code: .claude/skills/last30days/
   GitHub Copilot: .github/skills/last30days/
```

---

### 11. ✍️ Content Research Writer

**Your AI writing partner for research-backed content creation.**

Acts as a collaborative writing partner — helps with outlining, research, citations, hook improvement, and section-by-section feedback while preserving your unique voice.

**Use When:**
- Writing blog posts, articles, or newsletters
- Creating educational content or tutorials
- Drafting thought leadership pieces with citations
- Researching and writing case studies
- Getting real-time feedback as you write

**What It Does:**
| Capability | Description |
|------------|-------------|
| Collaborative Outlining | Structures ideas into coherent outlines |
| Research Assistance | Finds information and adds citations |
| Hook Improvement | Strengthens openings to capture attention |
| Section Feedback | Reviews each section as you write |
| Voice Preservation | Maintains your writing style and tone |

**Workflow Example:**
1. Start with an outline together
2. Research key points with citations
3. Write introduction → get feedback
4. Write body sections → feedback each
5. Final review and polish

```
📍 Location: .github/skills/content-research-writer/
```

---

### 12. 🔄 Doc-Sync-All

**Comprehensive documentation synchronization across all project artifacts.**

Scans local git changes and propagates updates to ALL design docs, task lists, specs, diagrams, and planning artifacts. Ensures documentation reflects reality, not aspirations.

**Use When:**
- After completing a development phase or feature
- When new architectural decisions are made
- After adding new skills, tools, or modules
- Before creating a PR to ensure docs match implementation
- User says "sync all docs", "update design docs"

**What It Syncs:**
| Document Type | Updates |
|---------------|---------|
| `tasks.md` | Marks completed tasks, updates phase summaries |
| `spec.md` | Syncs FRs, entities, success criteria |
| `research.md` | Adds new decision entries |
| `data-model.md` | Keeps in sync with TypeScript types |
| Diagrams | Updates Mermaid and ASCII architecture flows |

**Core Principle:** If code exists, docs should describe it. If code changed, docs should be updated. If a task is done, it should be checked off everywhere.

```
📍 Location: .github/skills/doc-sync-all/
```

---

### 13. 🎨 Project Infographic

**Generate polished HTML infographics for sprint demos and stakeholder presentations.**

Scans the codebase and design docs, then produces a beautiful single-page HTML infographic suitable for sprint demos. Targets non-technical stakeholders with visual-first communication.

**Use When:**
- Before sprint demos or stakeholder presentations
- When onboarding new team members visually
- To complement technical documentation with executive-friendly visuals
- User says "generate infographic", "create demo doc", "visual overview"

**Output Sections:**
- Hero with project name and key stats
- The Challenge (pain points solved)
- How It Works (visual pipeline/flow diagram)
- Current Status (phase completion, metrics)
- Tech Stack (pill badges with emoji icons)

**Design Features:**
- Self-contained HTML with embedded CSS
- Dark gradient hero sections
- Interactive hover effects
- Premium architectural diagrams with system boundaries
- Responsive for meeting room displays

```
📍 Location: .github/skills/project-infographic/
```

---

### 14. 🔃 Repo State Sync

**Keep your Session Onboarding section current with actual codebase state.**

Scans the entire codebase and design documentation to produce an up-to-date "Session Onboarding" section for `copilot-instructions.md`. Detects staleness and refreshes project context.

**Use When:**
- At the start of a new development phase
- After significant architecture changes
- When copilot-instructions.md seems stale
- User says "sync repo state", "update onboarding", "refresh copilot instructions"

**What It Updates:**
- Key Files table with current paths
- Runtime dependencies and verification
- Current working features (✅/🚧/⬜ status)
- Common development tasks
- Phase status from tasks.md
- Sync timestamp for freshness tracking

**Staleness Detection:**
Suggests running when it notices discrepancies between docs and reality (chunk counts, phase status, missing skills).

```
📍 Location: .github/skills/repo-state-sync/
```

---

### 15. 🪞 Skill Reflection

**Composable after-action review that any skill can invoke at the end of its workflow.**

Analyzes friction encountered during a skill run and produces prioritized, advisory recommendations for improving the calling skill's SKILL.md. Tracks friction history across runs — if the same issue appears twice, it auto-escalates to P0.

**Use When:**
- At the end of any multi-step skill workflow
- After a skill encounters friction (errors, workarounds, retries)
- After a successful run that still had rough edges
- When a user says "reflect on that run" or "what could be improved"

**Design Principles:**
| Principle | Meaning |
|-----------|--------|
| Generic | Knows nothing about specific skills; receives context as input |
| Composable | Called inline by other skills, not standalone |
| Advisory | Produces recommendations, never edits SKILL.md directly |
| Cumulative | Tracks friction history to detect repeat issues |

**How Other Skills Compose With This:**

Add this as the final step in any skill's SKILL.md:

```markdown
### Step N: Reflection (composable)

Invoke the `skill-reflection` skill with:
- **Calling skill**: `<skill-name>`
- **SKILL.md path**: `.github/skills/<skill-name>/SKILL.md`
- **Steps completed**: list each step with pass/fail/skipped
- **Friction notes**: any workarounds, retries, unexpected errors
```

**Priority Levels:**
| Priority | Meaning |
|----------|--------|
| P0 - breaking | Will cause failure next time — must fix before next run |
| P1 - quality | Causes retries or confusion — should fix soon |
| P2 - nice | Minor clarity improvement — fix when convenient |

**Escalation Rule:** Same friction point in two consecutive runs → auto-escalate to P0.

```
📍 Location: .github/skills/skill-reflection/
```

---

### 16. 📡 Daily Research Pipeline

**Automated daily AI research pipeline that writes to your Obsidian vault.**

Scans 5 topic tracks (agents, skills, models, MCP, RAG) across Reddit and X, deduplicates against vault history, and writes a structured daily note with reading list and per-topic breakdowns. Tag `#keep` to promote posts to your long-term Library.

**Use When:**
- Daily research habit for staying current on AI developments
- Scanning specific topics across Reddit and X
- Building a curated research library over time
- User says "daily research", "what's new in AI", "run pipeline"

**Cost:** ~$0.05-0.15/day (~$3/month) using scan mode with gpt-4o-mini.

**Invocation:**
```bash
# Full daily run (all 5 topics)
python .github/skills/obsidian-daily-research/scripts/run.py

# Single topic
python .github/skills/obsidian-daily-research/scripts/run.py --topic agents

# Preview without writing to vault
python .github/skills/obsidian-daily-research/scripts/run.py --dry-run
```

```
📍 Location: .github/skills/obsidian-daily-research/
```

---

### 17. 📓 Obsidian Vault Operations

**Composable wrapper for Obsidian CLI — the sole interface for all vault operations.**

Thin, composable wrapper around the Obsidian CLI (v1.12+) that other skills import to interact with the vault. Supports read, write, search, tags, properties, tasks, daily notes, backlinks, and more.

**Use When:**
- Any task needs to read, write, search, tag, or query the Obsidian vault
- Other skills need to persist output to the vault
- User says "save to vault", "obsidian", "research note", "daily note"

**Key Operations:**
| Category | Examples |
|----------|--------|
| Files | `read`, `create`, `append`, `prepend`, `move`, `rename`, `delete` |
| Search | `search`, `search_context` |
| Daily Notes | `daily_read`, `daily_append`, `daily_prepend` |
| Properties | `property_read`, `property_set`, `properties` |
| Tags | `tags`, `tag_info`, `tags_for_file` |
| Graph | `backlinks`, `links`, `orphans`, `unresolved` |
| Tasks | `tasks`, `task_toggle`, `task_done` |

**Invocation (PowerShell):**
```powershell
@'
# My Note
Body content here.
'@ | python .github/skills/obsidian/scripts/obsidian.py create --path "Research/Library/my-note.md"
```

```
📍 Location: .github/skills/obsidian/
```

---

### 18. 🔍 Obsidian Vault Digest

**Ask your vault what you already know about any topic.**

Searches your entire Obsidian vault for everything related to a topic, reads the matching notes, and produces a **synthesized briefing** with citations back to source notes. This is the "what do I already know about X?" skill.

**Use When:**
- Before starting a writing project — find all prior thinking on the topic
- Before a meeting or decision — get a briefing from your own notes
- When you can't remember where you wrote about something
- To find contradictions in your own thinking across notes
- User says "what do I know about X?", "digest my notes on X", "vault briefing"

**Output format:**
| Section | Description |
|---------|-------------|
| Executive Summary | Key themes synthesized across all matches |
| Source Notes | Each note with relevance score and key excerpts |
| Connections | Links between notes the user may not have noticed |
| Gaps | Topics partially covered — may need more research |
| Citations | `[[Note Name]]` backlinks for every claim |

```
📍 Location: .github/skills/obsidian-vault-digest/
```

---

### 19. 🔗 Obsidian Vault Linker

**Surface hidden connections and missing links across your knowledge base.**

Analyzes the vault's link graph to find orphaned notes, missing bidirectional links, thematic clusters, and connection opportunities you haven't noticed. The knowledge gardening skill — it doesn't create content, it strengthens the connective tissue.

**Use When:**
- Vault has grown organically and linking is inconsistent
- After importing a batch of new notes
- You want to discover thematic clusters you've forgotten
- Periodic vault hygiene (monthly)
- User says "find missing links", "what's connected?", "link my vault", "vault audit"

**Report Includes:**
| Section | Description |
|---------|-------------|
| Health Metrics | Orphan count, dead-ends, broken links, avg links/note |
| Missing Link Opportunities | Top 20 pairs of notes that should be linked |
| Orphaned Notes | Isolated notes worth connecting |
| Suggested MOCs | Map of Content notes to create for disconnected clusters |
| Broken Links | Unresolved references with fix suggestions |
| Tag Cleanup | Duplicate/similar tags to merge |

**Modes:**
- **Quick** — Scoped to a single topic or folder
- **Full Audit** — Whole-vault analysis with comprehensive report

```
📍 Location: .github/skills/obsidian-vault-linker/
```

---

### 20. 🔬 Session Context Audit

**Lint your AI's operating instructions for health and coherence.**

A lightweight diagnostic that checks freshness, contradictions, coverage gaps, and redundancy across all context files the AI reads at startup. Think of it as a linter for your AI's instructions.

**Use When:**
- The AI keeps making the same mistake despite instructions
- After merging a large PR that changed project conventions
- Monthly hygiene (takes ~2 minutes)
- After running `session-learning` several times
- User says "audit my context", "why do you keep getting this wrong?"

**Automated Checks:**
| Check | What It Catches |
|-------|----------------|
| Freshness | Files older than 30/90 days |
| Contradictions | Conflicting rules across files |
| Coverage Gaps | Areas used heavily but not documented |
| Redundancy | Same rule duplicated in multiple files |
| Token Budget | Files exceeding recommended size limits |

```
📍 Location: .github/skills/session-context-audit/
```

---

### 21. ⚒️ Session Skill Forge

**Turn any productive workflow into a reusable, callable skill.**

After completing a multi-step workflow, this skill extracts it into a permanent SKILL.md — complete with triggers, steps, decision points, and quality criteria. The skill that creates other skills.

**Use When:**
- You just completed a multi-step workflow that worked well
- You find yourself repeating the same sequence across sessions
- You want to formalize a process before you forget the steps
- User says "make this a skill", "save this workflow", "forge a skill"

**How It Differs from Session Learning:**
| | Session Learning | Skill Forge |
|-|-----------------|-------------|
| Extracts | Rules and corrections (defensive) | Workflows and capabilities (generative) |
| Output | Instructions / rules | Full SKILL.md with steps |
| Purpose | "Don't do X again" | "Here's how to do Y every time" |

**What It Generates:**
- Complete `SKILL.md` with frontmatter, triggers, workflow steps
- Helper scripts (if the workflow used code)
- README registration update
- Wiring into `copilot-instructions.md` skill list

```
📍 Location: .github/skills/session-skill-forge/
```

---

### 22. 🧹 Session Context Optimizer

**Let the AI restructure its own context files for maximum efficiency.**

Analyzes and restructures `.github/copilot-instructions.md`, scoped instructions, and skill manifests to reduce redundancy, resolve contradictions, and improve organization. The meta-optimization skill.

**Use When:**
- Context files feel bloated or contain redundant sections
- You've been adding instructions for weeks without cleanup
- After a major project phase change (old context no longer relevant)
- Periodically (every 2–4 weeks) as context hygiene
- User says "optimize your instructions", "clean up context", "meta-optimize"

**What It Fixes:**
| Issue | Action |
|-------|--------|
| Duplication | Consolidate to single authoritative location |
| Contradiction | Resolve — keep intended behavior |
| Staleness | Remove rules referencing removed packages |
| Bloat | Compress verbose explanations into concise rules |
| Poor hierarchy | Re-order by frequency of impact |
| Scope mismatch | Move file-specific rules to `.instructions.md` |

```
📍 Location: .github/skills/session_context_optimizer/
```

---

### 23. 📱 Remote Skills API

**Access all your skills from your phone over Tailscale.**

Lightweight Express.js server that auto-discovers every skill from `.github/skills/` and `.claude/skills/`, exposes them via a chat API, and serves a mobile-first dark-themed web UI. Start it on your PC, access from anywhere over Tailscale.

**Use When:**
- You're away from your desk but want to invoke skills from your phone
- Running research, vault operations, or any skill remotely
- You want a chat interface to your skill library

**Features:**
| Feature | Description |
|---------|-------------|
| Skill Discovery | Auto-scans all SKILL.md files at startup |
| Chat Interface | Natural language, Claude picks the right skill |
| Skill Picker | Pin a specific skill to scope your messages |
| Queue | Requests serialize — safe for concurrent use |
| Auth | Bearer token via `API_SECRET` in `.env` |
| Reboot Survival | Startup shortcut launches server at login |

**Quick Start:**
```powershell
cd .github/skills/remote-skills-api
npm install
npm start
# Open http://<tailscale-ip>:3838 on your phone
```

```
📍 Location: .github/skills/remote-skills-api/
```

---

## 📁 Repository Structure

```
.github/
├── copilot-instructions.md     # Root AI instructions
├── mcp.json                    # MCP server configuration
├── skills/                     # Reusable AI skills (GitHub Copilot)
│   ├── agentic-evaluator/      # ⭐ Score repo agentic maturity
│   ├── branch-wrapup/          # ✅ Pre-PR quality gate
│   ├── content-research-writer/ # ✍️ Writing partner
│   ├── obsidian-daily-research/ # 📡 Daily AI research pipeline
│   ├── doc-sync-all/           # 🔄 Documentation sync
│   ├── health-audit/           # 🩺 Artifact health checks
│   ├── insights-report/        # 📈 Cross-session analysis
│   ├── last30days/             # 🔍 Research (Copilot version)
│   ├── obsidian/               # 📓 Vault operations (composable)
│   ├── obsidian-vault-digest/  # 🔍 Vault topic synthesis
│   ├── obsidian-vault-linker/  # 🔗 Missing links & graph health
│   ├── project-guide/          # 🧭 Codebase exploration
│   ├── project-infographic/    # 🎨 Sprint demo visuals
│   ├── project-scaffold/       # 🏗️ Agentic scaffold wizard
│   ├── repo-state-sync/        # 🔃 Onboarding sync
│   ├── session-learning/       # 📚 Pattern extraction
│   ├── session-log/            # 🗒️ Session capture
│   ├── session-context-audit/  # 🔬 Context file health check
│   ├── session-skill-forge/    # ⚒️ Workflow → reusable skill
│   ├── session_context_optimizer/ # 🧹 Meta-optimize AI context
│   ├── remote-skills-api/      # 📱 Phone access over Tailscale
│   ├── skill-reflection/       # 🪞 Composable after-action review
│   └── visual-explainer/       # 🎨 HTML diagrams, diff reviews, slide decks
├── agents/                     # Specialized agent configs
│   └── eric-cartman.md         # 🎭 Cartman-flavored project guide
├── instructions/               # File-pattern-specific rules
└── prompts/                    # Reusable prompt templates

.claude/
├── settings.local.json         # Local Claude Code permissions (gitignored)
└── skills/                     # Claude Code skills
    └── last30days/             # 🔍 Research skill (Claude version)
        ├── SKILL.md            # Skill definition
        └── scripts/            # Python implementation
```

> **Note:** `.github/skills/` is for GitHub Copilot, `.claude/skills/` is for Claude Code.
> The `last30days` skill is available for both — same Python scripts, different SKILL.md frontmatter.

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
