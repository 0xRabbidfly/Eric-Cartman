---
name: podcast-to-obsidian
description: Podcast → transcript → Obsidian pipeline. Detects new episodes via Spotify MCP, downloads audio via RSS, transcribes locally with faster-whisper, generates structured Obsidian notes with summaries, key ideas, quotes, and backlinks. Manifest tracks processed episodes to avoid duplicates. Use when user says "podcast", "transcribe episode", "podcast-to-obsidian", or any podcast/transcript workflow.
argument-hint: process podcasts, transcribe episode, check new episodes
user-invocable: true
disable-model-invocation: true
metadata:
  author: 0xrabbidfly
  version: "1.3.0"
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
| `--url <web video URL>` | One-off mode: transcribe a single X/YouTube/Vimeo/etc. video via yt-dlp (no manifest, no RSS) |

## Prerequisites

- **Spotify MCP** configured in VS Code (see Setup section below) — only for podcast detection mode
- **Obsidian** running with CLI enabled (Settings → General → CLI)
- **faster-whisper** installed (`pip install faster-whisper`)
- **feedparser** installed (`pip install feedparser`)
- **yt-dlp + ffmpeg** for `--url` mode (`pip install yt-dlp`, plus ffmpeg on PATH)
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

# Keep audio files after run (default: purge after success)
python .github/skills/podcast-to-obsidian/scripts/pipeline.py --keep-audio

# List all tracked shows
python .github/skills/podcast-to-obsidian/scripts/pipeline.py --list-shows

# Transcription model selection (default: large-v3)
# Use --model base only when speed matters more than accuracy; it garbles
# proper nouns badly and those errors propagate into the generated note.
python .github/skills/podcast-to-obsidian/scripts/pipeline.py --model base

# Retry failed episodes
python .github/skills/podcast-to-obsidian/scripts/pipeline.py --retry-failed

# URL mode — one-off clip from X / YouTube / Vimeo / etc. (uses yt-dlp, bypasses manifest)
python .github/skills/podcast-to-obsidian/scripts/pipeline.py --url "https://x.com/handle/status/123/video/1"

# URL mode + custom folder + title override
python .github/skills/podcast-to-obsidian/scripts/pipeline.py --url "https://youtu.be/abc" --clips-folder "Clips" --title "My Clean Title"
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
9. CLEANUP   → Purge .mp3 audio files + intermediate build artifacts
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

**This step is automatic.** `step_generate_notes()` resolves a summary in this
order and writes the note itself:

1. A pre-generated summary at `.work/summaries/<transcript-stem>.json`, if the
   orchestrator wrote one
2. Otherwise `generate_ai_summary()` — Claude CLI first, then the OpenAI API
   (`OPENAI_API_KEY`)
3. If neither is available the episode is **failed, not skeleton-written** —
   pass `--no-ai` explicitly if you actually want a template-only note

The pipeline then writes the note to the vault and updates the manifest. A
normal run needs no agent intervention.

#### When an agent IS in the loop

An orchestrating agent adds value by **auditing the generated note against the
transcript**, not by regenerating it. Do not write a second note — the manifest
is already marked `completed` and the vault file already exists. Instead:

1. Read the generated note and the full transcript
2. Check the back third of the episode specifically — summaries reliably
   under-cover the final segments
3. Verify speaker attribution on quotes (small models produce bare or wrong
   first names)
4. Verify `[[People/...]]` links resolve to real people, not homophones
5. Patch gaps in place with targeted edits

Alternatively, pre-generate the summary yourself into
`.work/summaries/<transcript-stem>.json` **before** running the pipeline, and
it will be used verbatim.

#### Writing a note by hand (fallback only)

1. Read the full transcript from `.work/transcripts/<YYYY-MM-DD> - <Title>.txt`
2. Identify speakers, key themes, and structure
3. Write the note following the **Obsidian Note Structure** template above:
  - Frontmatter with tags, show, episode, dates, `source: podcast-to-obsidian`, and `spotify_url` when available
  - Keep the episode title unsanitized inside the note; sanitize only the filename/path
  - TL;DR as an Obsidian abstract callout
  - Key Ideas as a numbered list with bolded labels and explanations
   - Deep Dives (3-5 mini-essays on the most important/surprising concepts — analysis, implications, connections, what wasn't said. NOT a summary rehash.)
   - Actionable Takeaways (checkbox items)
  - Memorable Quotes as quote callouts with speaker attribution
   - People & Topics (wiki-links: `[[People/Name]]`, `[[Topics/Topic]]`, `[[Companies/Org]]`)
  - Use the same section separators and layout as the generated final notes in `.work/notes/`
4. Pipe the note to the obsidian skill:
   ```powershell
   $noteContent = @'
   <generated note content>
   '@ | python .github/skills/obsidian/scripts/obsidian.py create --path "Podcasts/<Show>/<YYYY-MM-DD> - <Title>.md"
   ```
5. Verify the write through the Obsidian wrapper instead of writing directly to the vault filesystem:
  ```powershell
  python .github/skills/obsidian/scripts/obsidian.py read --path "Podcasts/<Show>/<YYYY-MM-DD> - <Title>.md"
  ```

## URL Mode (one-off clips)

For single web videos that aren't tracked podcast episodes (X tweets,
YouTube videos, Vimeo clips, etc.), use `--url` to bypass RSS detection
and the manifest:

```powershell
python .github/skills/podcast-to-obsidian/scripts/pipeline.py --url "<web video URL>"
```

**How it differs from podcast mode:**

| Aspect | Podcast mode | URL mode (`--url`) |
|--------|-------------|--------------------|
| Source | RSS feed enclosure | yt-dlp (X, YouTube, Vimeo, …) |
| Detection | Spotify MCP / RSS poll | Direct URL |
| Manifest | Tracks episodes by show | Skipped — no manifest write |
| Show grouping | `Podcasts/<Show>/` | `<clips_folder>/<platform> — @<handle>/` |
| Default folder | `Podcasts` | `Clips` |
| Filename | `YYYY-MM-DD - <Episode Title>.md` | `YYYY-MM-DD - <Derived Title>.md` |
| Note frontmatter | `source: podcast-to-obsidian` | adds `source_url: "<original URL>"` |

**Title derivation:** yt-dlp doesn't expose a clean title for X tweets — it
uses the tweet description. The pipeline auto-derives a note title by
stripping the `<uploader> -` prefix, dropping trailing `t.co/...` links,
and keeping the first sentence (~100 chars). Use `--title` to override.

**Source label / folder:** auto-derived from extractor + uploader, e.g.
`X — @servasyy_ai`, `YouTube — @somechannel`. Override with `--show-name`.

**Playlists (X tweets with multiple videos):** the pipeline always picks
the first video. There's no equivalent of `/video/N` selection — re-run
with a more specific URL if needed.

**URL-mode flags:**

| Flag | Purpose |
|------|---------|
| `--url <URL>` | The web video URL (required to trigger URL mode) |
| `--clips-folder <name>` | Vault subfolder (default: `Clips`) |
| `--show-name <label>` | Override the auto-derived `Platform — @handle` folder |
| `--title <text>` | Override the auto-derived note title |
| `--check-only` | Download + report metadata, skip transcription |
| `--transcribe-only` | Download + transcribe, skip note + write |
| `--dry-run` | Run everything except the Obsidian write |
| `--model <size>` | Whisper model (base / large-v3 / …) |
| `--no-ai` | Skip AI summary and intentionally write a template-only skeleton note |
| `--keep-audio` | Don't purge the .mp3 after success |

## New Releases Only

**The pipeline never walks backwards into a show's archive.** Backfill is a
deliberate manual act, never something a scheduled run starts doing on its own.

Two gates apply together during detection:

| Gate | Source | Purpose |
|------|--------|---------|
| **Release watermark** | `shows.<id>.latest_published` in the manifest | Newest publish date successfully processed. Anything at or below it is historical, even if it never reached the manifest |
| **Age cutoff** | `max_age_days` (default 30) | An episode from three months ago is still historical even if it is technically "newer than" a stale watermark |

The watermark advances **only on `status: completed`** — a failed episode must
not raise the bar, or its retry would be filtered out as historical next run.

Episodes with **no publish date** in the feed are skipped while gating is
active: recency can't be established, so they can't be confirmed as new
releases. (Undated entries previously bypassed every gate silently.)

### Drawing a line in the sand

```powershell
# Everything currently in every feed becomes historical.
# Only genuinely future releases are auto-fetched from here on.
python .../pipeline.py --set-watermark today

# Or per show, or to a specific date
python .../pipeline.py --set-watermark 2026-07-18 --show "Bankless"
```

`--set-watermark` never *lowers* an existing watermark unless `--force` is
given, so it can't silently re-open a backlog you already closed.

### Manual backfill

```powershell
# Consider episodes published on or after a date, ignoring the watermark
python .../pipeline.py --backfill-since 2026-06-01 --show "Bankless"

# Target one specific episode
python .../pipeline.py --backfill-since 2026-06-01 --episode "Nasdaq"

# Everything in the detection window, no date gate at all
python .../pipeline.py --ignore-watermark --show "Naval" --max-episodes 1
```

Backfill still respects `max_episodes`, so a large archive drains in
controlled batches rather than all at once.

### Adopting this on an existing manifest

```powershell
# Set each show's watermark from its newest COMPLETED episode
python .../pipeline.py --seed-watermarks
```

Use this when a manifest predates watermarks. It reprocesses nothing — it just
records where each show had already got to. Shows with no completed episodes
fall back to `max_age_days` on their first run.

| Config key | Default | Effect |
|-----------|---------|--------|
| `only_new_releases` | `true` | Master switch. Set `false` to disable both gates |
| `max_age_days` | 30 | Hard ceiling on episode age. `0` disables the age gate (watermark still applies) |

## Manifest

Persistent JSON file tracking all processed episodes.

**Location:** `config/podcast-manifest.json`

**Rules:**
- Spotify episode ID is the primary key (RSS-only entries are keyed by RSS GUID)
- Dedup matches by key, `rss_guid`/`spotify_id` field, **or** normalized title + published date — the same episode may be keyed by Spotify ID (Spotify detection) or RSS GUID (RSS detection), and a match on ANY of these means already processed. When diffing via Spotify MCP, compare title + published date against manifest entries, not just IDs.
- If a match exists → skip
- If not → process and append
- Manifest updated ONLY after successful Obsidian write
- Supports manual RSS-only entries (no Spotify ID required)
- Each show carries `latest_published`, the release watermark (see **New Releases Only**). It advances only on `completed`, never on `failed`, and never moves backwards

## Obsidian Note Structure

Each episode produces a note at:
`Podcasts/<Show Name>/<YYYY-MM-DD> - <Episode Title>.md`

Filename rule:
- Use the episode's published date plus title
- Strip invalid filename characters `< > : " / \ | ? *` AND Obsidian
  wikilink-breaking characters `# ^ [ ]` (a `#` in the filename breaks
  the `[[path|label]]` links in the show index)
- Trim trailing `.` and space after stripping
- Truncate the title portion to about 120 chars if needed
- Do not slugify the filename

The transcript is also written to the vault at
`Podcasts/<Show Name>/transcripts/<same filename>.md` (the Obsidian CLI
only creates `.md` notes) and that path is recorded in the manifest. If
the vault copy fails, the manifest records the real `.work` path instead
— never a path that does not exist.

```markdown
---
tags: [podcast, <show-slug>, <topic-tag-1>, <topic-tag-2>]
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

**Show:** [[Podcasts/<Show Name>]] · 📅 YYYY-MM-DD · ⏱ HH:MM:SS

---

> [!abstract]+ TL;DR
> <2-3 sentence summary>

---

## 💡 Key Ideas

1. **Idea 1** — explanation
2. **Idea 2** — explanation
3. ...

---

## 🧠 Deep Dives

### Concept Title

2-4 paragraph mini-essay analyzing this concept in depth —
implications, connections between ideas, what wasn't said,
why it matters beyond the podcast. Pick 3-5 of the most
important/surprising concepts. Do NOT repeat Key Ideas;
add new depth and perspective.

---

## ✅ Actionable Takeaways

- [ ] Action item 1
- [ ] Action item 2

---

## 💬 Key Quotes

> [!quote] "Quote text"
> — **Speaker Name**

---

## 🔗 People & Topics

**People:** [[People/<Name>]] · [[People/<Name 2>]]

**Topics:** [[Topics/<Topic>]] · [[Topics/<Topic 2>]]

**Companies:** [[Companies/<Org>]] · [[Companies/<Org 2>]]

---

## Transcript

<collapsible full transcript>
```

## Working Directory

**`work_dir` resolves against `SKILL_DIR`, not the current working directory
or the repo root.** With the default `.work`, everything lives under:

```
.github/skills/podcast-to-obsidian/.work/
├── audio/         # .mp3 (+ .part during download), purged after success
├── transcripts/   # raw .txt from whisper
├── summaries/     # optional pre-generated summary JSON (see Step 6)
├── notes/         # intermediate .final.md build artifacts
└── logs/          # timestamped run logs, newest 30 retained
```

Running `python .../pipeline.py` from the repo root does **not** create
`<repo>/.work` — look under the skill directory. This has cost debugging time
more than once.

## Configuration

Edit `scripts/config.json`:

| Key | Default | Description |
|-----|---------|-------------|
| `vault_path` | (auto-detect) | Path to Obsidian vault |
| `podcasts_folder` | `Podcasts` | Vault subfolder for notes |
| `transcripts_folder` | `transcripts` | Subfolder for raw transcripts |
| `whisper_model` | `large-v3` | faster-whisper model size. `base` is materially worse on proper nouns — see Known Issues |
| `whisper_device` | `auto` | `cpu`, `cuda`, or `auto` |
| `max_episodes` | 5 | Max new episodes **processed** per show per run |
| `detection_window` | 50 | Feed entries **scanned** for new episodes. Independent of `max_episodes` — keep it comfortably larger than a show's per-run publish rate |
| `audio_format` | `mp3` | Expected audio format |
| `note_template` | `default` | Note template name |

### Transcription vocabulary

`config/vocabulary.json` holds domain terms and is applied two ways:

- **`initial_prompt`** primes the Whisper decoder toward correct spellings
  (prevention). Add recurring hosts, guests, companies, and jargon here.
- **`corrections`** are word-boundary, case-insensitive replacements applied to
  the finished transcript (cure). Keep entries **phrase-scoped** — a bare
  single word like `opioid` or `England` must never be replaced, because both
  have legitimate uses in the same episodes.

Terms too ambiguous to auto-correct are parked under `_risky_not_applied` as
documentation rather than silently guessed at.

## Run Logs

Every invocation tees stdout **and** stderr to
`.work/logs/<YYYYMMDD-HHMMSS>.log`, including tracebacks, and prints the path
on exit. This is independent of shell redirection, so scheduled and detached
runs always leave a debuggable artifact. The newest 30 logs are kept.

Download progress renders as a live bar only when stdout is a TTY; redirected
output gets one line per 10% instead, which keeps logs small and readable.

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
| `obsidian.com create` with stdin-piped content silently produces 0-byte files (RC 0, says "Overwrote") | **P0** | Write directly to vault filesystem via `Path.write_text()`, then verify with `obsidian.com file`. The Python wrapper `obsidian.py` also fails because its `run()` uses `stdin=subprocess.DEVNULL`. |
| `--dry-run` still downloads audio and runs transcription | **P1** | Use `--check-only` for true no-side-effects preview. `--dry-run` only skips vault write (Step 7). |
| AI summarization unavailable during a normal run | **P1** | The pipeline fails that episode instead of silently writing a template-only note; install Claude CLI or set `OPENAI_API_KEY`. Pass `--no-ai` only if you truly want a skeleton note |
| Pipeline downloads all new episodes per show, not just the target | **P1** | Use `--episode "title substring"` to filter, or `--max-episodes 1` |
| Small Whisper models mangle domain jargon and proper nouns | **P1** | Default model is now `large-v3`. `base` produced "opioid models" for "open-weight models" throughout an entire episode, which then propagated into the generated note. Extend `config/vocabulary.json` for show-specific names |
| Pipeline may exit with code 1 during large batch downloads | **P2** | Re-run with `--retry-failed` or `--transcribe-only` if audio already downloaded |

## CLI Flag Reference

| Flag | What it does | What it skips |
|------|-------------|---------------|
| `--check-only` | Lists new episodes (or downloads + reports metadata in URL mode) | Download/transcribe/generate/write (podcast mode); transcription (URL mode) |
| `--dry-run` | Downloads + transcribes | **Vault write only** (Step 7) |
| `--transcribe-only` | Downloads + transcribes | Generate, write, manifest |
| `--episode "text"` | Filters to episodes matching title substring | Other episodes |
| `--show "Name"` | Filters to a single show | Other shows |
| `--max-episodes N` | Limits episodes per show | Episodes beyond N |
| `--model <size>` | Sets whisper model (base/large-v3) | — |
| `--retry-failed` | Re-processes failed episodes | Already-completed episodes |
| `--keep-audio` | Keeps .mp3 files after successful run | Cleanup step |
| `--set-watermark <date\|today>` | Forces the release watermark, then exits | Everything else — it's a maintenance command |
| `--seed-watermarks` | Seeds watermarks from newest completed episode, then exits | Everything else |
| `--backfill-since <date>` | Manual backfill from a date floor | The watermark gate |
| `--ignore-watermark` | Manual backfill, no date gate at all | Both recency gates |
| `--force` | Lets `--set-watermark` lower a watermark | The safety check |
| `--url <URL>` | One-off mode via yt-dlp (X/YouTube/Vimeo/…) | RSS detection, manifest |
| `--clips-folder <name>` | Vault subfolder for URL-mode notes (default `Clips`) | — |
| `--show-name <label>` | Override URL-mode source folder | Auto-derived `Platform — @handle` |
| `--title <text>` | Override URL-mode note title | Auto-derived title |

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| "Unknown qtype episode" from Spotify MCP | MCP doesn't support episode URIs | Use `fetch_webpage` fallback (see Step 1 above) |
| Exit code 1 during download | Network timeout or RSS enclosure URL expired | Re-run with `--retry-failed` |
| Transcript empty or garbled | Audio codec issue or whisper model too small | Try `--model large-v3` |
| Obsidian write fails | Obsidian not running or CLI not enabled | Start Obsidian, enable CLI in Settings → General |
| Obsidian write returns RC 0 but file is 0 bytes | stdin content-loss bug in `obsidian.com create` | Use direct filesystem write fallback (see Step 7 WRITE) |

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
