# Skills — Eric Cartman Meta Prompt Library

Portable, reusable skills for AI coding assistants. Each skill lives in its own folder with a `SKILL.md` manifest.

## Skill Index

| Skill | Purpose |
|-------|---------|
| `agentic-evaluator` | Score any repo's agentic development maturity (A–F grade) |
| `api-testing` | Next.js API route testing patterns |
| `branch-wrapup` | Pre-PR quality gate (build, types, lint, tests, security) |
| `ci-cd` | GitHub Actions workflow creation and debugging |
| `session_context_optimizer` | Audit and compress the AI's own context files |
| `session-skill-forge` | Turn a productive workflow into a reusable SKILL.md |
| `obsidian-vault-digest` | Synthesize Obsidian vault content into a briefing |
| `obsidian-vault-linker` | Discover missing links and clusters in Obsidian vault |
| `code-review` | Constitutional code review against project standards |
| `content-research-writer` | Token-efficient writing partner with citations |
| `session-context-audit` | Lighter health check for context drift |
| `css-audit` | Audit components for CSS best-practice violations |
| `obsidian-daily-research` | Daily AI research pipeline → Obsidian vault |
| `doc-sync-all` | Propagate code changes to all design docs |
| `health-audit` | Validate YAML frontmatter, cross-refs, token counts |
| `i18n` | Bilingual EN/FR content validation (next-intl) |
| `insights-report` | Cross-session insights report from session logs |
| `last30days` | Research any topic from the last 30 days (Reddit + X + web) |
| `obsidian` | Composable Obsidian vault operations via CLI |
| `project-guide` | Teaching-first codebase exploration companion |
| `project-infographic` | Generate HTML infographics for sprint demos |
| `project-scaffold` | Interactive wizard to scaffold agentic dev artifacts |
| `repo-state-sync` | Keep onboarding context in copilot-instructions.md fresh |
| `session-learning` | Extract reusable patterns from coding sessions |
| `session-log` | Capture session insights into `.github/sessions/` |
| `skill-reflection` | Composable after-action review (any skill can invoke) |
| `testing` | Comprehensive testing workflow (Vitest + Playwright) |

## Authoring a New Skill

1. Create `.github/skills/<kebab-case-name>/SKILL.md`
2. Follow the structure: **Purpose → When to Use → Workflow → Output Format → Rules**
3. Target 100–500 lines. Split if larger.
4. Place helper scripts in `<skill>/scripts/`. Python preferred.
5. Add an entry to this table and to `README.md` at the repo root.
6. Test the skill by invoking it before marking complete.

See `copilot-instructions.md` for full authoring conventions.
