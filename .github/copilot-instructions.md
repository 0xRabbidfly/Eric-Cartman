# Copilot Instructions — Eric Cartman (Meta Prompt Library)

## Purpose
Eric Cartman is a **meta-prompt library** — a portable scaffold of agentic development artifacts (skills, agents, instructions, prompts) that can be dropped into any project to bootstrap AI coding assistant workflows. It works with GitHub Copilot, Claude Code, Cursor, and other AI IDEs.

## Repository Layout

```
.github/
├── copilot-instructions.md   ← YOU ARE HERE (root AI context)
├── agents/                   # Persistent agent personas (e.g., eric-cartman.md)
├── instructions/             # File-pattern-scoped rules (applyTo globs)
├── prompts/                  # Reusable prompt templates
├── references/               # Reference docs (brand guidelines, etc.)
├── skills/                   # Portable skills for GitHub Copilot
│   └── <skill-name>/SKILL.md
└── sessions/                 # Session logs (generated)

.claude/
├── CLAUDE.md                 # Claude Code root context
├── mcp.json                  # MCP server config (gitignored)
├── settings.local.json       # Claude Code permissions (gitignored)
├── mcp-servers/              # Vendored MCP servers (gitignored)
└── skills/                   # Claude Code–specific skills (gitignored)
```

> `.github/` is the open-source, portable scaffold. `.claude/` is personal/local config (not git-tracked except CLAUDE.md).

## Audience & Tooling
- **Primary audience**: Open-source community — skills must be self-documenting, contributor-friendly, and broadly compatible.
- **Supported AI tools**: GitHub Copilot (VS Code) and Claude Code (CLI). Skills should work in both where possible.
- **Known gaps**: Obsidian-related workflows need more skill coverage.

## Non-Negotiables
- Never commit secrets, API keys, or tokens. Use `.env` (gitignored).
- Keep skills portable — no hardcoded absolute paths or machine-specific assumptions.
- Every skill must have a `SKILL.md` with clear purpose, triggers, and workflow.
- Prefer cross-platform commands (PowerShell + CI-friendly). Avoid bash-only scripts.
- **Obsidian vault operations** must go through the `obsidian` skill (`.github/skills/obsidian/scripts/obsidian.py`). Never write to the vault via raw filesystem, temp scripts, or other skills' scripts. Read the skill's SKILL.md for usage patterns.

## Skill Authoring Conventions
- **Location**: `.github/skills/<kebab-case-name>/SKILL.md`
- **Size**: Target 100–500 lines. Split oversized skills into composable parts.
- **Structure**: Purpose → When to Use → Workflow (numbered steps) → Output Format → Rules
- **Naming**: Folder names are `kebab-case`. Skill titles are human-readable.
- **Composability**: Skills can invoke other skills (e.g., `skill-reflection` as a final step).
- **Scripts**: Place helper scripts in `<skill>/scripts/`. Python preferred for cross-platform.
- **No duplication**: If a rule exists in `copilot-instructions.md`, skills reference it — don't repeat it.

## Writing Style for AI Artifacts
- Concise, imperative tone. Rules over explanations.
- Use tables for structured data (triggers, outputs, checks).
- Code examples only when the pattern isn't obvious.
- Include `## When to Use` with concrete trigger phrases the user might say.
- Include `## Related Skills` to help discoverability.

## Change Hygiene
- Keep changes focused on the requested task.
- Do not reformat unrelated files.
- Update README.md when adding/removing/renaming skills.
- Test skills by invoking them before marking complete.

## Friction Rule
If you experienced friction completing a task — retries, workarounds, encoding issues,
missing params, unclear docs, unexpected errors — run **`/skill-reflection`** **immediately**
(not at end of session). Apply P0/P1 fixes to the SKILL.md right away, save an Agent Memory
via the obsidian skill, then continue with the current task. This is the self-healing loop.

## Autonomous Agent Behaviors

These behaviors fire **automatically** during any session. No user prompt needed.

### Agent Memory (via obsidian skill)
After completing any significant action, evaluate: *"Would I want to know this next time?"*
If yes, save to `Agent Memories/` in the Obsidian vault using the obsidian skill's
Agent Memory pattern. Deduplicate before writing. See `obsidian/SKILL.md § Agent Memory`.

**Triggers**: non-obvious workaround, project convention learned, user preference observed,
decision with rationale, recurring error pattern + fix, research insight, complex task lessons.

### Friction Self-Healing (via skill-reflection)
When any skill step fails or needs a workaround **mid-run**:
1. Complete the step with the workaround
2. Immediately invoke `skill-reflection` with friction details
3. Apply P0/P1 recommendations to the SKILL.md now
4. Save an Agent Memory about the friction + resolution
5. Continue the remaining steps

Do NOT defer to end of session. Fix skills while they're breaking.

## Meta-Skills (Self-Improvement)
The library includes skills that improve its own context:
- `session_context_optimizer` — Audit and compress instruction files
- `session-context-audit` — Lighter health check for context drift
- `session-learning` — Extract patterns from sessions into persistent rules
- `skill-reflection` — After-action review any skill can invoke **mid-run or post-run**; triggers Agent Memory capture
- `repo-state-sync` — Keep onboarding context fresh
- `obsidian` (Agent Memory) — Long-term memory store; agents save insights autonomously to `Agent Memories/` in the vault
