# Skills — Eric Cartman Meta Prompt Library

Portable, reusable skills for AI coding assistants. Each skill lives in its own folder with a `SKILL.md` manifest.

## Skill Index

### Repo & Project Tooling

| Skill | Purpose |
|-------|---------|
| `agentic-evaluator` | Score any repo's agentic development maturity (A–F grade) |
| `branch-wrapup` | Pre-PR quality gate (build, types, lint, tests, security) |
| `doc-sync-all` | Propagate code changes to all design docs |
| `health-audit` | Validate YAML frontmatter, cross-refs, token counts |
| `owasp-security-review` | Quick-scan review against the OWASP Top 10:2025 |
| `project-guide` | Teaching-first codebase exploration companion |
| `project-infographic` | Generate HTML infographics for sprint demos |
| `project-scaffold` | Interactive wizard to scaffold agentic dev artifacts |
| `remote-skills-api` | Invoke any skill from your phone over Tailscale |
| `repo-state-sync` | Keep onboarding context in `copilot-instructions.md` fresh |
| `visual-explainer` | Self-contained HTML diagrams, diff reviews, plan audits, slide decks — no ASCII art |

### Research & Writing

| Skill | Purpose |
|-------|---------|
| `content-research-writer` | Token-efficient writing partner with citations |
| `last30days` | Research any topic from the last 30 days (Reddit + X + web) |

### Obsidian & Knowledge Base

| Skill | Purpose |
|-------|---------|
| `obsidian` | Composable Obsidian vault operations via CLI — the sole interface for vault writes |
| `obsidian-connection-detector` | Detect and classify relationships between vault notes |
| `obsidian-daily-research` | Daily AI research pipeline → Obsidian vault |
| `obsidian-linked-research` | Fetch a URL → summarize → save into the research taxonomy using the master Library MOC |
| `obsidian-thesis-tracker` | Track emerging theses and draft reports as evidence accumulates |
| `obsidian-vault-digest` | Synthesize Obsidian vault content into a briefing |
| `obsidian-vault-linker` | Discover missing links, MOC gaps, and cluster opportunities |
| `obsidian-vault-lint` | Weekly vault maintenance — broken links, MOC coverage, section sorting |
| `obsidian-vault-lint-cowork` | Cowork-native fork of `obsidian-vault-lint` |
| `obsidian-vault-report` | Generate synthesis reports and strategy docs from the vault corpus |
| `obsidian-weekly-brain` | Weekly digest — trends, thesis health, blindspots, cross-domain bridges |
| `podcast-to-obsidian` | Podcast → local transcription → structured Obsidian note |

### Skill Authoring (Meta)

| Skill | Purpose |
|-------|---------|
| `skill-autoresearch` | Bounded keep-or-revert experiment loop for creating or improving one skill |
| `skill-creator` | Create, test, benchmark, and refine skills |
| `skill-reflection` | Composable after-action review (any skill can invoke) |

## Authoring a New Skill

1. Create `.github/skills/<kebab-case-name>/SKILL.md`
2. Follow the structure: **Purpose → When to Use → Workflow → Output Format → Rules**
3. Target 100–500 lines. Split if larger.
4. Place helper scripts in `<skill>/scripts/`. Python preferred.
5. Add an entry to the table above and to `README.md` at the repo root.
6. Test the skill by invoking it before marking complete.

See `copilot-instructions.md` for full authoring conventions.
