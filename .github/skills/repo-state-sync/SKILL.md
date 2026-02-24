---
name: repo-state-sync
description: Scan codebase and design docs to update the Session Onboarding section in copilot-instructions.md. Use at the start of a new development phase or when onboarding context is stale.
---

You are a repository state analyst. Your task is to scan the entire codebase and all design documentation to produce an up-to-date "Session Onboarding" section for `.github/copilot-instructions.md`.

## When to Use This Skill

- At the start of a new development phase
- After significant architecture changes
- When the user says "sync repo state" or "update onboarding"
- If you notice copilot-instructions.md seems stale (check the `Last synced` timestamp)

## Scan Process

### 1. Codebase Structure Analysis

Scan these locations to understand current state:

```
src/                    # All TypeScript source modules
tests/                  # Test coverage and patterns
web/                    # Frontend assets
scripts/                # Build and maintenance scripts
indexes/                # Vector indexes (check *.meta.json for stats)
catalog/                # Corpus data (count .jsonl lines, .htm files)
runs/                   # Recent pipeline runs (check latest outputs)
.github/skills/         # Available Copilot skills
```

For each key area, note:

- File count and primary exports
- Entry points (main files, CLI commands)
- Integration points between modules

### 2. Design Documentation Scan

Check ALL documentation sources for current project state:

```
docs/                     # Or your project's design folder
  ├── spec.md           # User stories, acceptance criteria
  ├── plan.md           # Architecture decisions
  ├── tasks.md          # Phased task breakdown with completion status
  ├── data-model.md     # Type definitions
  ├── research.md       # Technical research notes
  └── quickstart.md     # Getting started guide

specs/                    # (Optional) OpenSpec-style specifications
  ├── project.md        # Project-wide specifications
  ├── changes/          # Change proposals (numbered)
  └── features/         # Feature specifications

policies/               # Validation templates
README.md               # Project overview
TESTING.md              # Test strategy
AGENTS.md               # AI assistant instructions
```

### 3. CI/CD and Tooling

Check for workflow definitions and build configuration:

```
.github/workflows/      # GitHub Actions (if present)
package.json            # Scripts section for npm commands
tsconfig*.json          # TypeScript configuration
vitest.config.ts        # Test configuration
eslint.config.js        # Linting rules
```

### 4. Runtime State

Gather current runtime details:

- Vector index statistics from `indexes/*.meta.json`
- Corpus record count from `catalog/*.jsonl`
- Recent runs from `runs/` directory
- Available skills from `.github/skills/`

## Output Format

Generate a complete replacement for the "Session Onboarding (Read First)" section. The section:

1. **MUST** start with `## Session Onboarding (Read First)`
2. **MUST** end with `---` (horizontal rule) before the next section
3. **MUST** include a `Last synced: YYYY-MM-DD` timestamp

### Required Subsections

```markdown
## Session Onboarding (Read First)

> Last synced: YYYY-MM-DD

**Quick Context**: [One-line summary of what this project does and how to run it]

### Key Files to Understand First

| Purpose    | File(s)      |
| ---------- | ------------ |
| [Category] | [file paths] |

...

### Runtime Dependencies

[Code block with required services and how to verify they're running]

### Current Working Features

- ✅ [Working feature]
- ✅ [Working feature]
- 🚧 [In-progress feature]
- ⬜ [Planned feature]

### Common Development Tasks

[Code block with essential npm/node commands]

### Architecture Pattern

[Brief description of data flow through the system]

### CI/CD Status

[If workflows exist: describe them. If not: state "No CI/CD workflows configured yet."]

### Phase Status

[Current phase from tasks.md, what's complete, what's next]

---
```

## Important Rules

1. **ONLY modify the Session Onboarding section** - never touch anything after the `---` separator
2. **Be specific with numbers** - actual file counts, chunk counts, record counts
3. **Check task completion status** - look for `[x]` vs `[ ]` in tasks.md
4. **Verify working features** - check if files/modules actually exist before marking ✅
5. **Include the sync timestamp** - so users know freshness
6. **Keep it scannable** - tables and bullet points, not paragraphs

## Example Staleness Detection

If the current copilot-instructions.md says:

- "319 chunks" but `indexes/*.meta.json` shows different
- "Phase 3 Complete" but tasks.md shows Phase 4 items checked
- Missing skills that now exist in `.github/skills/`

Then suggest running this sync skill.

## Execution Steps

When invoked:

1. Read current `copilot-instructions.md` to find section boundaries
2. Scan codebase structure with `list_dir` and `file_search`
3. Read key docs: `tasks.md`, `spec.md`, `plan.md`
4. Check index metadata: `indexes/*.meta.json`
5. Count corpus records: `wc -l catalog/*.jsonl` or read and count
6. List recent runs: `runs/` directory
7. Check for CI/CD: `.github/workflows/`
8. Generate new Session Onboarding section
9. Use `replace_string_in_file` to swap old section with new
10. Confirm the update with file read

## Sample Invocation Phrases

- "Sync repo state"
- "Update session onboarding"
- "Refresh copilot instructions"
- "Is the onboarding section current?"
