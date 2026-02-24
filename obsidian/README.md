# Obsidian Skill

Composable Obsidian vault operations via the [Obsidian CLI](https://help.obsidian.md/cli).

## What This Is

A thin Python wrapper (`scripts/obsidian.py`) that other skills import to interact with
your Obsidian vault. Instead of each skill reimplementing filesystem reads, regex-based
tag parsing, or YAML frontmatter manipulation, they call typed methods that map 1:1 to
the CLI.

## Setup

### Prerequisites

1. **Obsidian 1.12+** with a [Catalyst license](https://help.obsidian.md/catalyst)
2. **CLI enabled**: Settings → General → "Command line interface"
3. **Windows**: `Obsidian.com` in your install folder (check `%LOCALAPPDATA%\Programs\obsidian\`)

### Verify

```powershell
# Add to PATH (or set permanently in System Environment Variables)
$env:PATH += ";$env:LOCALAPPDATA\Programs\obsidian"

# Test
obsidian version
obsidian vault
```

Or set `OBSIDIAN_CLI` env var to the full path of `Obsidian.com`:
```powershell
$env:OBSIDIAN_CLI = "$env:LOCALAPPDATA\Programs\obsidian\Obsidian.com"
```

## Usage

```python
from obsidian import Obsidian

ob = Obsidian()                    # auto-discovers binary + active vault
ob = Obsidian(vault="My Vault")   # target a specific vault
```

### Core Operations

| Category | Methods |
|----------|---------|
| **Files** | `read`, `create`, `append`, `prepend`, `move`, `rename`, `delete`, `open` |
| **Search** | `search`, `search_context`, `search_json`, `search_context_json` |
| **Daily** | `daily`, `daily_read`, `daily_append`, `daily_prepend`, `daily_path` |
| **Properties** | `properties`, `property_read`, `property_set`, `property_remove` |
| **Tags** | `tags`, `tag_info`, `tags_for_file`, `tags_json` |
| **Links** | `backlinks`, `links`, `orphans`, `unresolved`, `deadends` |
| **Tasks** | `tasks`, `task_toggle`, `task_done`, `task_todo`, `daily_tasks` |
| **Vault** | `vault_info`, `vaults`, `files`, `folders`, `outline` |
| **Templates** | `templates`, `template_read`, `template_insert` |
| **Bookmarks** | `bookmarks`, `bookmark` |
| **Dev** | `eval` (run JS in Obsidian context) |
| **Raw** | `run(command, **params)` for any CLI command |

### Composing from Another Skill

```python
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "obsidian" / "scripts"))
from obsidian import Obsidian

ob = Obsidian()
ob.daily_append("- [ ] Review PR #42")
```

Or add the skills path to `PYTHONPATH`:
```powershell
$env:PYTHONPATH = ".github/skills/obsidian/scripts;$env:PYTHONPATH"
```

## Architecture

```
.github/skills/obsidian/
├── SKILL.md              # Skill declaration (composable)
├── README.md             # This file
└── scripts/
    └── obsidian.py       # CLI wrapper (stdlib only, zero deps)
```

**Design choices:**
- No filesystem fallback — Obsidian is assumed running
- No pip dependencies — stdlib `subprocess` + `json` only
- `CLIResult` dataclass wraps every response with `.text`, `.json()`, `.lines()`, `.ok`
- Auto-discovers binary: `OBSIDIAN_CLI` env → PATH → default Windows install
- Vault targeting via constructor, not per-call (but `run()` allows anything)

## Dependencies

- Python 3.10+ (stdlib only)
- Obsidian 1.12+ running with CLI enabled
