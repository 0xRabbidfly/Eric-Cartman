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

### 5. 🎭 Eric Cartman Agent

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

### 6. 🛠️ Skill Creator

**Create new skills, improve existing ones, and measure whether they actually work.**

Provides an end-to-end workflow for skill authoring: capture intent, draft the `SKILL.md`, generate realistic test prompts, compare with-skill vs baseline runs, add assertions, and iterate until the skill is solid.

**Use When:**
- You want to create a skill from scratch
- You want to improve or refactor an existing skill
- You need evals to verify a skill is actually helping
- You want to benchmark a revised skill against the previous version
- You want to tighten the skill description so it triggers more reliably

**Core Workflow:**
| Step | What it does |
|------|--------------|
| Capture Intent | Clarifies triggers, outputs, edge cases, and success criteria |
| Draft the Skill | Writes the `SKILL.md` and any bundled resources |
| Create Test Prompts | Builds realistic prompts for evaluation |
| Run Comparisons | Compares with-skill behavior against a baseline |
| Add Assertions | Defines objective checks where the output is measurable |
| Iterate | Rewrites the skill based on results and feedback |

**Why It Matters:**
- Prevents vibes-only skill authoring
- Encourages measured improvement instead of prompt folklore
- Makes skill quality reviewable by other contributors

```
📍 Location: .github/skills/skill-creator/
```

---

### 7. 🔍 Last 30 Days Research

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
- Keys stored via Python `keyring` (Windows Credential Manager), env vars, or `~/.config/last30days/.env`

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

### 8. ✍️ Content Research Writer

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

### 9. 🔄 Doc-Sync-All

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

### 10. 🎨 Project Infographic

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

### 11. 🔃 Repo State Sync

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

### 12. 🪞 Skill Reflection

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

### 13. 📡 Daily Research Pipeline

**Automated daily AI research pipeline that writes to your Obsidian vault.**

Scans topic tracks on X, pulls Google News RSS, and batches a search over frontier-lab accounts, deduplicating everything against vault history. Writes a mobile-friendly daily note: a synthesized briefing, lab pulse, prominent voices, news, and a ranked research feed. Supports a feedback loop with `#good` and `#bad` tags.

**Use When:**
- Daily research habit for staying current on AI developments
- Scanning specific topics across Reddit and X
- Building a curated research library over time
- Catching up after missing a few days of research
- User says "daily research", "what's new in AI", "run pipeline"

**Pipeline Highlights:**
| Capability | Description |
|------------|-------------|
| Lab Account Scan | Batched X search over frontier-lab accounts (Anthropic, OpenAI, Google, SpaceXAI, Mistral, Meta, Moonshot), chunked at 10, no engagement floor |
| Prominent Voices | One broad search for high-engagement posts across the AI space, no hardcoded handles |
| News | Google News RSS per topic, deduplicated against vault history by URL and title, then LLM-ranked |
| Vault Dedup | Avoids resurfacing links and titles already captured in the vault |
| Feedback Loop | Collects `#good` / `#bad` tags into `feedback.json` |

**Cost:** ~$0.30/day (~$9/month). Search is pinned to `grok-4.3`; analysis runs on
Claude CLI (free on Max) with `grok-4.5` as fallback.

**Invocation:**
```bash
# Full daily run (all topics)
python .github/skills/obsidian-daily-research/scripts/run.py

# Single topic
python .github/skills/obsidian-daily-research/scripts/run.py --topic agents

# Preview without writing to vault
python .github/skills/obsidian-daily-research/scripts/run.py --dry-run

# Intentionally regenerate today's note
python .github/skills/obsidian-daily-research/scripts/run.py --force-rerun
```

```
📍 Location: .github/skills/obsidian-daily-research/
```

---

### 14. 📓 Obsidian Vault Operations

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

**Composable Patterns:**
| Pattern | Purpose |
|---------|---------|
| Agent Memory | Agents autonomously save insights to `Agent Memories/` for cross-session recall |
| Research Reports | Skills producing deep-thought output save structured reports to `Research/Reports/` with `[[wikilinks]]` to all source notes |
| Friction Self-Healing | When a skill breaks mid-run, triggers `skill-reflection` immediately and applies fixes |

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

### 15. 🔗 Obsidian Linked Research

**Turn any URL into a structured research note in your vault.**

Fetches a URL, summarizes it, checks for thesis drift against existing notes, and files the result into the numbered `Research/Library/` taxonomy — using the master Research Library MOC as the source of truth for tags, folder routing, and freshness updates. X/Twitter URLs get rich extraction via xAI's `x_search` (engagement stats, thread context); everything else uses plain-text HTTP fetch. The agent does the summarizing, so no external LLM call is needed for the intelligence step.

**Use When:**
- You share a URL and want it captured — "research this: https://..."
- User says "save this article", "obsidian research", "save this tweet"
- You're bookmarking something to actually read later, with a summary attached

**Key Behaviors:**
| Behavior | Description |
|----------|-------------|
| MOC-Driven Routing | Reads the master Library MOC to pick the right subfolder and tag vocabulary |
| Always-Capture Sources | A whitelist (e.g. AINews / Latent Space) bypasses the digest quality filter |
| Thesis Drift Check | Compares new material against existing notes before writing |
| Composable Writes | All vault writes route through the `obsidian` skill |

**Invocation:**
```
/obsidian-linked-research https://example.com/article
research this: https://x.com/...
```

```
📍 Location: .github/skills/obsidian-linked-research/
```

---

### 16. 🎙️ Podcast to Obsidian

**Podcast → transcript → structured Obsidian note, fully local.**

Detects new episodes via Spotify MCP, downloads audio from RSS enclosures, transcribes locally with faster-whisper, and writes structured notes with summaries, key ideas, quotes, and backlinks. A manifest tracks processed episodes so nothing gets transcribed twice, and the pipeline git-commits that manifest itself so runs don't leave the working tree dirty (`--no-commit-manifest` opts out). A `--url` mode transcribes any single X/YouTube/Vimeo video via yt-dlp, no manifest or RSS involved.

**Use When:**
- User says "podcast to obsidian", "check new episodes", "transcribe podcast"
- Registering a new show to track, or listing tracked shows
- One-off transcription of a web video

**Prerequisites:**
- Spotify MCP (detection mode only), Obsidian with CLI enabled, Python 3.10+
- `pip install faster-whisper feedparser`, plus `yt-dlp` + `ffmpeg` on PATH for `--url` mode

**Invocation:**
```powershell
# Full pipeline — detect, download, transcribe, write to vault
python .github/skills/podcast-to-obsidian/scripts/pipeline.py

# Detection only
python .github/skills/podcast-to-obsidian/scripts/pipeline.py --check-only

# Single show, or a one-off web video
python .github/skills/podcast-to-obsidian/scripts/pipeline.py --show "Show Name"
python .github/skills/podcast-to-obsidian/scripts/pipeline.py --url https://...
```

```
📍 Location: .github/skills/podcast-to-obsidian/
```

---

### 17. 🔍 Obsidian Vault Digest

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

### 18. 🔗 Obsidian Vault Linker

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

### 19. 📱 Remote Skills API

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
| Auth | Bearer token via `API_SECRET` (keyring, env var, or `.env`) |
| Reboot Survival | Startup shortcut launches server at login |
| Remote Restart | Authenticated endpoint can restart the Node service via the launcher |

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

### 20. 🧪 Skill Autoresearch

**Apply Karpathy-style autoresearch to skill creation and improvement.**

This skill wraps skill authoring in a bounded keep-or-revert loop: one target
`SKILL.md`, one stable eval batch, one results ledger, and one promotion rule.
It is for measured skill iteration, not one-shot drafting.

**Use When:**
- You want to improve a skill empirically instead of by vibes
- You want fixed prompts and a ledger before changing instructions
- You want to compare candidate revisions against a baseline and only keep winners
- You want a safe way to create a new skill without letting scope sprawl

**Core Pattern:**
| Autoresearch | Skill Workflow |
|---|---|
| `program.md` | experiment brief + control rules |
| `train.py` | one mutable `SKILL.md` |
| fixed 5-minute harness | fixed eval batch |
| `results.tsv` | skill results ledger |
| keep / discard | promote / revert |

**How It Fits:**
- `skill-creator` helps with prompts, assertions, and benchmark runs
- `skill-autoresearch` controls the bounded hill-climbing loop around one target skill

```
📍 Location: .github/skills/skill-autoresearch/
```

---

## 📚 Complete Skill Index

Every skill in `.github/skills/` (28 total). ⭐ marks the ones with a deep-dive section above.

**Repo & Project Tooling**
| Skill | Purpose |
|-------|---------|
| ⭐ `agentic-evaluator` | Score any repo's agentic development maturity (A–F grade) |
| `branch-wrapup` | Pre-PR quality gate — build, types, lint, tests, security, conventional commit |
| ⭐ `doc-sync-all` | Propagate code changes to every design doc, task list, and spec |
| ⭐ `health-audit` | Validate frontmatter, cross-references, and token counts |
| `owasp-security-review` | Quick-scan review against the OWASP Top 10:2025 |
| ⭐ `project-guide` | Teaching-first codebase exploration companion |
| ⭐ `project-infographic` | Generate HTML infographics for sprint demos |
| ⭐ `project-scaffold` | Interactive wizard to scaffold agentic dev artifacts |
| ⭐ `remote-skills-api` | Invoke any skill from your phone over Tailscale |
| ⭐ `repo-state-sync` | Keep the onboarding section of `copilot-instructions.md` fresh |
| `visual-explainer` | Self-contained HTML diagrams, diff reviews, plan audits, slide decks |

**Research & Writing**
| Skill | Purpose |
|-------|---------|
| ⭐ `content-research-writer` | Token-efficient writing partner with numbered citations |
| ⭐ `last30days` | Research any topic from the last 30 days (Reddit + X + web) |

**Obsidian & Knowledge Base**
| Skill | Purpose |
|-------|---------|
| ⭐ `obsidian` | Composable vault wrapper — the sole interface every other vault skill uses |
| `obsidian-connection-detector` | Detect and classify relationships between vault notes |
| ⭐ `obsidian-daily-research` | Daily AI research pipeline → Obsidian vault |
| ⭐ `obsidian-linked-research` | URL → summarized research note, routed by the master Library MOC |
| `obsidian-thesis-tracker` | Track emerging theses and draft reports as evidence accumulates |
| ⭐ `obsidian-vault-digest` | Synthesize everything the vault knows about a topic |
| ⭐ `obsidian-vault-linker` | Find missing links, orphans, MOC gaps, and thematic clusters |
| `obsidian-vault-lint` | Weekly vault structural maintenance — broken links, MOC coverage, section sorting, tag/folder taxonomy |
| `obsidian-vault-lint-cowork` | Cowork-native fork of `obsidian-vault-lint` |
| `obsidian-vault-report` | Generate synthesis reports and strategy docs from the vault corpus |
| `obsidian-weekly-brain` | Weekly digest — trends, thesis health, blindspots, cross-domain bridges |
| ⭐ `podcast-to-obsidian` | Podcast → local transcription → structured Obsidian note |

**Skill Authoring (Meta)**
| Skill | Purpose |
|-------|---------|
| ⭐ `skill-autoresearch` | Bounded keep-or-revert experiment loop for improving one skill |
| ⭐ `skill-creator` | Create, test, benchmark, and refine skills |
| ⭐ `skill-reflection` | Composable after-action review any skill can invoke |

---

## 📁 Repository Structure

```
.github/
├── copilot-instructions.md     # Root AI instructions
├── agents/                     # Specialized agent personas
│   ├── eric-cartman.md         # 🎭 Cartman-flavored project guide
│   ├── portuguese-lawyer.md    # ⚖️ Portuguese legal advisor
│   ├── ui-designer.md          # 🎨 UI design and Fluent UI patterns
│   └── ux-designer.md          # 🧑‍💻 UX flows and information architecture
├── references/                 # Shared reference docs
│   └── brand-guidelines.md
├── sessions/                   # Session notes and audit output
└── skills/                     # Reusable AI skills (portable across IDEs)
    ├── README.md               # Skill index + authoring conventions
    ├── agentic-evaluator/      # ⭐ Score repo agentic maturity
    ├── branch-wrapup/          # ✅ Pre-PR quality gate
    ├── content-research-writer/ # ✍️ Writing partner
    ├── doc-sync-all/           # 🔄 Documentation sync
    ├── health-audit/           # 🩺 Artifact health checks
    ├── last30days/             # 🔍 Research (Copilot version)
    ├── obsidian/               # 📓 Vault operations (composable)
    ├── obsidian-connection-detector/ # 🕸️ Note relationship detection
    ├── obsidian-daily-research/ # 📡 Daily AI research pipeline
    ├── obsidian-linked-research/ # 🔗 URL → research note via the master Library MOC
    ├── obsidian-thesis-tracker/ # 🎯 Thesis tracking and draft reports
    ├── obsidian-vault-digest/  # 🔍 Vault topic synthesis
    ├── obsidian-vault-linker/  # 🔗 Missing links, MOC gaps, and graph health
    ├── obsidian-vault-lint/    # 🧹 Weekly vault structural maintenance
    ├── obsidian-vault-lint-cowork/ # 🧹 Cowork-native lint fork
    ├── obsidian-vault-report/  # 📄 Corpus synthesis reports
    ├── obsidian-weekly-brain/  # 🧠 Weekly intelligence digest
    ├── owasp-security-review/  # 🔒 OWASP Top 10 security scan
    ├── podcast-to-obsidian/    # 🎙️ Podcast → transcript → Obsidian
    ├── project-guide/          # 🧭 Codebase exploration
    ├── project-infographic/    # 🎨 Sprint demo visuals
    ├── project-scaffold/       # 🏗️ Agentic scaffold wizard
    ├── remote-skills-api/      # 📱 Phone access over Tailscale
    ├── repo-state-sync/        # 🔃 Onboarding sync
    ├── skill-autoresearch/     # 🧪 Keep-or-revert skill improvement loops
    ├── skill-creator/          # 🛠️ Create, test, and refine skills
    ├── skill-reflection/       # 🪞 Composable after-action review
    └── visual-explainer/       # 🎨 HTML diagrams, diff reviews, slide decks

.claude/
├── readme-mcp.md               # MCP setup notes for Claude Code
├── playwright-*.json           # Browser automation configs
└── skills/                     # Claude Code skills (shared subset)
    ├── council/                # 🏛️ Multi-persona deliberation
    ├── humanizer/              # 🧑 Strip AI tells from writing
    ├── last30days/             # 🔍 Research (Claude Code version)
    └── skill-creator/          # 🛠️ Create, test, and refine skills
```

> **Note:** `.github/skills/` is the open-source portable scaffold — it works with any AI IDE.
> `.claude/` holds Claude Code configuration and a second skill set, only part of which is
> shared here. Local-only files — `CLAUDE.md`, `mcp.json`, and personal skills that touch
> private accounts (banking, groceries, car search) — are gitignored and stay on the machine.

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
