---
name: podcast-to-obsidian
description: Podcast → transcript → Obsidian pipeline. Detects new episodes via Spotify MCP, downloads audio via RSS, transcribes locally with faster-whisper, generates structured Obsidian notes with summaries, key ideas, quotes, and backlinks. Manifest tracks processed episodes to avoid duplicates. Use when user says "podcast", "transcribe episode", "podcast-to-obsidian", or any podcast/transcript workflow.
argument-hint: process podcasts, transcribe episode, check new episodes
user-invokable: true
disable-model-invocation: true
metadata:
  author: 0xrabbidfly
  version: "1.1.0"
---

# Podcast → Transcript → Obsidian

## Purpose

Manual-trigger pipeline that detects new podcast episodes via Spotify MCP,
downloads audio via RSS enclosures, transcribes locally using faster-whisper,
and generates structured Obsidian notes with summaries, key ideas, quotes,
and backlinks.

## When to Use

| Trigger | Action |
|---------|--------|
| "podcast to obsidian" | Full pipeline — detect, download, transcribe, write |
| "check new episodes" | Detection only — show what's new |
| "transcribe podcast" | Process a specific episode or show |
| "add podcast show" | Register a new show in the manifest |
| "list podcast shows" | Show all tracked shows and episode counts |

## Prerequisites

- **Spotify MCP** configured in VS Code (see Setup section below)
- **Obsidian** running with CLI enabled (Settings → General → CLI)
- **faster-whisper** installed (`pip install faster-whisper`)
- **feedparser** installed (`pip install feedparser`)
- Python 3.10+

## Quick Start

```powershell
# Full pipeline — detect, download, transcribe, write to vault
python .github/skills/podcast-to-obsidian/scripts/pipeline.py

# Check for new episodes only (no download/transcribe)
python .github/skills/podcast-to-obsidian/scripts/pipeline.py --check-only

# Process a specific show
python .github/skills/podcast-to-obsidian/scripts/pipeline.py --show "Show Name"

# Dry run — downloads & transcribes but SKIPS vault write only
python .github/skills/podcast-to-obsidian/scripts/pipeline.py --dry-run

# Process a single episode by title substring
python .github/skills/podcast-to-obsidian/scripts/pipeline.py --episode "Nasdaq"

# Add a new show manually (without Spotify)
python .github/skills/podcast-to-obsidian/scripts/pipeline.py --add-show --name "My Show" --rss "https://example.com/feed.xml"

# List all tracked shows
python .github/skills/podcast-to-obsidian/scripts/pipeline.py --list-shows

# Transcription model selection (default: base)
python .github/skills/podcast-to-obsidian/scripts/pipeline.py --model large-v3

# Retry failed episodes
python .github/skills/podcast-to-obsidian/scripts/pipeline.py --retry-failed
```

## Pipeline Flow

```
1. DETECT    → Spotify MCP or fetch_webpage scrapes episode metadata
2. DIFF      → Compare episode IDs against manifest (skip processed)
3. CONFIRM   → Show user what's new, ask which to process
4. DOWNLOAD  → Fetch audio via RSS <enclosure> URL → .work/audio/
5. TRANSCRIBE → faster-whisper (local GPU/CPU) → .work/transcripts/
6. GENERATE  → Agent reads transcript + writes structured note (see below)
7. WRITE     → Obsidian skill pipes note to vault
8. MANIFEST  → Update manifest only after successful write
```

### Step 1 — DETECT: Fallback Detection

Spotify MCP (`SpotifyGetInfo`) **does not support episode URIs** — it returns
"Unknown qtype episode". When given a Spotify episode URL:

1. Try Spotify MCP first (may work for show-level queries)
2. If it fails, use `fetch_webpage` on the Spotify episode URL to scrape:
   - Episode title, show name, publish date, duration, description
3. Match the episode to a tracked show in `config.json` via show name
4. Use the show's RSS feed to find the audio enclosure URL

### Step 6 — GENERATE: Structured Note from Transcript

This step is **manual** — the agent reads the transcript and writes the note.

1. Read the full transcript from `.work/transcripts/<YYYY-MM-DD> - <Title>.txt`
2. Identify speakers, key themes, and structure
3. Write the note following the **Obsidian Note Structure** template above:
   - Frontmatter with tags, show, episode, dates, spotify_url
   - TL;DR (2-3 sentences)
   - Key Ideas (bulleted, bolded labels with explanations)
   - Detailed Summary (paragraph-level, use ### subheadings for major topics)
   - Actionable Takeaways (checkbox items)
   - Memorable Quotes (blockquotes with speaker attribution)
   - People & Topics (wiki-links: `[[People/Name]]`, `[[Topics/Topic]]`, `[[Companies/Org]]`)
   - Transcript (condensed inside `<details><summary>` collapsible)
4. Pipe the note to the obsidian skill:
   ```powershell
   $noteContent = @'
   <generated note content>
   '@ | python .github/skills/obsidian/scripts/obsidian.py create --path "Podcasts/<Show>/<YYYY-MM-DD> - <Title>.md"
   ```

## Manifest

Persistent JSON file tracking all processed episodes.

**Location:** `config/podcast-manifest.json`

**Rules:**
- Spotify episode ID is the primary key
- If episode ID exists in manifest → skip
- If not → process and append
- Manifest updated ONLY after successful Obsidian write
- Supports manual RSS-only entries (no Spotify ID required)

## Obsidian Note Structure

Each episode produces a note at:
`Podcasts/<Show Name>/<YYYY-MM-DD> - <Episode Title>.md`

```markdown
---
tags: [podcast, <show-slug>, transcript]
type: podcast-note
show: "<Show Name>"
episode: "<Episode Title>"
published: YYYY-MM-DD
duration: "HH:MM:SS"
spotify_url: "<url>"
source: podcast-to-obsidian
created: YYYY-MM-DDTHH:MM:SSZ
---

# <Episode Title>

**Show:** [[Podcasts/<Show Name>]]
**Published:** YYYY-MM-DD
**Duration:** HH:MM:SS

## TL;DR

<2-3 sentence summary>

## Key Ideas

- **Idea 1** — explanation
- **Idea 2** — explanation
- ...

## Detailed Summary

<paragraph-level summary of the episode>

## Actionable Takeaways

- [ ] Action item 1
- [ ] Action item 2

## Memorable Quotes

> "Quote text" — Speaker Name

## People & Topics

[[People/<Name>]] · [[Topics/<Topic>]] · [[Companies/<Org>]]

## Transcript

<collapsible full transcript>
```

## Configuration

Edit `scripts/config.json`:

| Key | Default | Description |
|-----|---------|-------------|
| `vault_path` | (auto-detect) | Path to Obsidian vault |
| `podcasts_folder` | `Podcasts` | Vault subfolder for notes |
| `transcripts_folder` | `transcripts` | Subfolder for raw transcripts |
| `whisper_model` | `base` | faster-whisper model size |
| `whisper_device` | `auto` | `cpu`, `cuda`, or `auto` |
| `max_episodes` | 5 | Max new episodes per show per run |
| `audio_format` | `mp3` | Expected audio format |
| `note_template` | `default` | Note template name |

## Spotify MCP Setup

### Step 1 — Create Spotify Developer App

1. Go to https://developer.spotify.com/dashboard
2. Create a new app
3. Note your **Client ID** and **Client Secret**
4. Set Redirect URI to `http://localhost:8888/callback`

### Step 2 — Install Spotify MCP Server

```powershell
# Clone and install
git clone <spotify-mcp-repo>
cd spotify-mcp
npm install
```

### Step 3 — Environment Variables

Add to your `.env` or system environment:
```
SPOTIFY_CLIENT_ID=<your-client-id>
SPOTIFY_CLIENT_SECRET=<your-client-secret>
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
```

### Step 4 — Register in VS Code

Add to `.vscode/settings.json` or user settings:
```json
{
  "mcp.servers": {
    "spotify": {
      "command": "node",
      "args": ["path/to/spotify-mcp/index.js"]
    }
  }
}
```

Restart VS Code after configuration.

## Known Issues

| Issue | Severity | Workaround |
|-------|----------|------------|
| Spotify MCP `SpotifyGetInfo` does not support episode URIs | **P0** | Use `fetch_webpage` on the Spotify episode URL to scrape metadata |
| `--dry-run` still downloads audio and runs transcription | **P1** | Use `--check-only` for true no-side-effects preview. `--dry-run` only skips vault write (Step 7). |
| Pipeline downloads all new episodes per show, not just the target | **P1** | Use `--episode "title substring"` to filter, or `--max-episodes 1` |
| Pipeline may exit with code 1 during large batch downloads | **P2** | Re-run with `--retry-failed` or `--transcribe-only` if audio already downloaded |

## CLI Flag Reference

| Flag | What it does | What it skips |
|------|-------------|---------------|
| `--check-only` | Lists new episodes | Download, transcribe, generate, write |
| `--dry-run` | Downloads + transcribes | **Vault write only** (Step 7) |
| `--transcribe-only` | Downloads + transcribes | Generate, write, manifest |
| `--episode "text"` | Filters to episodes matching title substring | Other episodes |
| `--show "Name"` | Filters to a single show | Other shows |
| `--max-episodes N` | Limits episodes per show | Episodes beyond N |
| `--model <size>` | Sets whisper model (base/large-v3) | — |
| `--retry-failed` | Re-processes failed episodes | Already-completed episodes |

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| "Unknown qtype episode" from Spotify MCP | MCP doesn't support episode URIs | Use `fetch_webpage` fallback (see Step 1 above) |
| Exit code 1 during download | Network timeout or RSS enclosure URL expired | Re-run with `--retry-failed` |
| Transcript empty or garbled | Audio codec issue or whisper model too small | Try `--model large-v3` |
| Obsidian write fails | Obsidian not running or CLI not enabled | Start Obsidian, enable CLI in Settings → General |

## Dependencies

- Composes with **obsidian** skill for all vault I/O
- **faster-whisper** for local transcription (GPU recommended)
- **feedparser** for RSS parsing
- Python 3.10+ (stdlib + 2 pip packages)
- Obsidian must be running with CLI enabled
- Spotify MCP server (optional — can use RSS-only mode)

## Related Skills

- **obsidian** — Vault operations (composed — required)
- **obsidian-vault-digest** — Query vault for prior podcast knowledge
- **obsidian-vault-linker** — Link podcast notes to related content
- **session-log** — Capture pipeline run outcomes

### Step N: Reflection (composable)

Invoke the `skill-reflection` skill with the following context:

- **Calling skill**: `podcast-to-obsidian`
- **SKILL.md path**: `.github/skills/podcast-to-obsidian/SKILL.md`
- **Steps completed**: list each step with pass/fail/skipped
- **Friction notes**: any workarounds, retries, unexpected errors, or manual interventions
