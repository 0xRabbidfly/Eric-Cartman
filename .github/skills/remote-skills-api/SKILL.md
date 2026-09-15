---
name: remote-skills-api
description: Mobile-friendly web server to chat with and invoke Eric Cartman skills remotely via Tailscale. Generalised from rbc-banking/simple-api.js. Start once on your PC, access from your phone anywhere.
argument-hint: start, stop
user-invocable: true
disable-model-invocation: false
metadata:
  author: 0xrabbidfly
  version: "1.2.0"
---

# Remote Skills API

## Purpose

Lightweight Express.js server that auto-discovers all skills from `.github/skills/`
and `.claude/skills/`, exposes them via a chat-style API, and serves a mobile-first
web UI. Access your entire skill library from your phone over Tailscale while on
vacation.

## When to Use

- "I want to run skills from my phone"
- "Start the remote skills server"
- "How do I access skills over Tailscale?"
- Going AFK but leaving PC running

## Prerequisites

1. **Node.js 18+** installed
2. **Claude CLI** installed and on PATH (`claude --version`)
3. **Tailscale** installed and running on both PC and phone
4. **API_SECRET** — set via keyring (`automation/api`), env var, or project root `.env`

## Quick Start

```powershell
# 1. Install dependencies (first time only)
cd .github/skills/remote-skills-api
npm install

# 2. Start the server
npm start

# 3. Get your Tailscale IP
tailscale ip -4

# 4. Open on phone: http://<tailscale-ip>:3838
#    Or with token: http://<tailscale-ip>:3838?token=YOUR_API_SECRET
```

## Survive Reboots

A startup shortcut is installed in `shell:startup` so the server launches
minimized when you log in. To set it up manually:

```powershell
# Creates a shortcut in your Windows Startup folder
$s = [Environment]::GetFolderPath('Startup')
$ws = (New-Object -ComObject WScript.Shell).CreateShortcut("$s\RemoteSkillsAPI.lnk")
$ws.TargetPath = "$PWD\.github\skills\remote-skills-api\start-service.bat"
$ws.WorkingDirectory = "$PWD"
$ws.WindowStyle = 7  # minimized
$ws.Save()
```

The included `start-service.bat` sets the correct working directory and
supervises the Node process. A minimized cmd window stays in your taskbar.
If the API exits with the configured restart code, the batch file relaunches it
automatically.

## Architecture

```
Phone (Safari/Chrome)
    │
    │  HTTPS over Tailscale VPN
    ▼
┌──────────────────────────────┐
│  Express.js  (port 3838)     │
│  ┌────────────────────────┐  │
│  │  Skill Discovery       │  │  Reads all SKILL.md files
│  │  .github/skills/*      │  │  Builds registry at startup
│  │  .claude/skills/*      │  │
│  ├────────────────────────┤  │
│  │  Chat Router           │  │  Natural language → skill match
│  │  Request Queue         │  │  Serial Claude CLI execution
│  ├────────────────────────┤  │
│  │  Claude CLI Backend    │  │  claude -p <prompt>
│  │  MCP servers attached  │  │  (.mcp.json — Playwright, etc.)
│  └────────────────────────┘  │
│  Mobile-first UI (ui.html)   │
└──────────────────────────────┘
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Mobile chat UI |
| GET | `/api/status` | Server status + queue info |
| GET | `/api/skills` | List all discovered skills |
| POST | `/api/skills/reload` | Re-scan skill directories |
| GET | `/api/skills/:name` | Read a skill's full SKILL.md |
| POST | `/api/chat` | Send chat message. JSON response by default; SSE stream when `Accept: text/event-stream` |
| GET | `/api/chat/stream` | SSE streaming chat (`?q=...&skill=...`) |
| POST | `/api/invoke/:skill` | Direct skill invocation (`{args}`) |
| POST | `/api/admin/restart` | Restart the Node service so `start-service.bat` relaunches it |
| POST | `/api/cancel` | Kill running Claude process |
| GET | `/api/recent-notes` | Vault notes touched in the last 7 days (`?days=N`, `?days=all`) |
| GET | `/api/notes-by-topic` | Notes grouped by Library subfolder / podcast show |
| GET | `/api/notes-by-week` | Notes grouped by ISO week, newest first |
| GET | `/api/gym/profiles` | The app-wide weight `units` (`kg` or `lb`) and gym profiles with each one's `program`, next session, program week and pace against the plan (`{enabled:false}` when no gym data) |
| GET | `/api/gym/week/:n` | Week prescription plus per-day log status and any podcast picked for the day from `<profile>/podcasts.json` (`?profile=`) |
| GET | `/api/gym/session/:week/:day` | One day's prescription merged with its log (`?profile=`) |
| PUT | `/api/gym/session/:week/:day` | Save a partial log (`?profile=`) |
| POST | `/api/gym/session/:week/:day/finish` | Complete the session, fill blank reps, barbell loads and weighted pull-up loads (each marked `assumed`), and start the assessment; body `{performedOn: "YYYY-MM-DD"}` is the phone's local date, used when the log has none and within a day of the server's; returns `{jobId}` (`?profile=`) |
| POST | `/api/gym/session/:week/:day/reopen` | Make a finished session editable again (`?profile=`) |
| GET | `/api/gym/exercises` | Exercise library with how-tos and videos, from the tracked `gym-library/exercises.json`. Barbell lifts carry `barLb`, the empty bar in pounds; single-weight lifts may carry a `loadHint` saying what to type (`?profile=`) |
| GET | `/api/gym/stats` | The athlete's `program`, week-by-week tonnage, RPE and adherence, 1RM trend, working-load trend and baseline re-checks (`?profile=`) |
| GET | `/api/gym/assessments` | Past session assessments, newest first (`?profile=`) |

All three note endpoints scan `Research/Library` and `Podcasts` in the vault
(skipping `00 MOC`, `attachments`, `transcripts`, show index files, and stubs
under 1 KB) and return Obsidian deep links (`obsidian://open?vault=Rabbidfly Vault…`).

The gym routes read a private data store outside version control. When it is
absent, `/api/gym/profiles` reports `enabled: false`, every other gym route
returns 404 `gym_not_configured`, and the UI hides the Gym tab, so a fresh clone
behaves exactly as it did before this feature existed.

Gym sessions are done in program order: W1 D1, D2, D3, then W2 D1. The PUT and
finish routes accept any session already done and the next one, and answer
`409` with code `gym_session_out_of_sequence` for anything later. A locked
session can still be read with GET, and reopen is unaffected, since it only
applies to a session already finished.

Each profile in `profiles.json` names its `program`, and a profile without one
is `cycling`. Both programs share the 12 weeks × 3 sessions structure, so
sequence, locking and pace work the same way for every athlete:

- `cycling` opens with 3RM ramps and derives loads from the estimated 1RM.
- `strength-tone` never tests a max. Its working sets stop at RPE 8 and
  progress by reps and load. Its only tested numbers are `isBaseline` checks
  in weeks 1, 5, 9 and 12, including rep-count baselines where 0 is a valid
  result. Stats reports those as `baselineTrend` and the heaviest working set
  per exercise per week as `loadTrend`.
- A week item may carry an optional `repsMax`, which makes its prescription a
  range: 3 × 10–12.

Weights are always stored in kilograms. `profiles.json` may set `units: "lb"`
for the whole app. The UI then takes pounds, stores them as kilograms to three
decimals so they read back exactly as typed, and shows prescribed loads in
5 lb steps, per hand for a dumbbell pair. `gymlib.py --lb-target` in the
gym-cyclist skill rounds the same way, so assessment notes match the app.

Finishing a session fills blanks the athlete skipped because they matched the
plan, and lists each in the entry's `assumed` array:

- Blank reps become the prescribed reps, or the prescribed hold for seconds.
  Never on a max-test ramp, a baseline, centimetres or metres.
- A barbell set (`barLb` in the library) left blank or at 0 becomes the empty
  bar. On a max-test ramp only a typed 0 does.
- A weighted pull-up with no added load becomes 0, bodyweight.

Typing into a field the server filled removes that field from `assumed`.

A profile may also have `<profile>/podcasts.json`, keyed `W<week>D<day>`, with
an episode picked for that session. It is kept out of the week files, so
regenerating a week never drops it.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_SECRET` | (required) | Bearer token for auth |
| `SKILLS_PORT` | `3838` | Server port |
| `CLAUDE_PATH` | `claude` | Path to Claude CLI binary |
| `CLAUDE_MODEL` | `sonnet` | Model for Claude CLI |
| `SESSION_CONTEXT_TTL_HOURS` | `2` | Max age for reusable chat history within the same skill scope |
| `ALLOW_QUERY_TOKEN` | `false` | Allow `?token=` authentication on API routes (not recommended) |
| `RESTART_EXIT_CODE` | `75` | Exit code that tells `start-service.bat` to relaunch the service |
| `CLAUDE_TIMEOUT_MS` | `300000` | Kill Claude process after this many ms (0 = no timeout) |
| `GYM_ASSESSMENT_DISABLED` | `false` | Set to `1`, `true` or `yes` to save finished gym sessions without running an assessment. The route tests set it so a test run can never spend a real model call. |

## Conversation Context Guards

- Chat history is now **scope-isolated**: only messages from the same skill can be reused in follow-up prompts.
- Switching from one skill to another immediately clears persisted history instead of carrying context across scopes.
- Old history is also discarded after `SESSION_CONTEXT_TTL_HOURS`, even if you return to the same skill later.
- General chat (no pinned skill / no slash-skill) is treated as its own separate scope and does not inherit skill-specific history.
- Prompt transport should use Claude stdin mode for large prompts so long SKILL.md content does not trigger Windows `spawn ENAMETOOLONG` errors.

## Security

- **Token auth (default)**: Header-only `Authorization: Bearer <API_SECRET>`
- **Tailscale**: Network-level encryption + identity. Not exposed to public internet.
- **URL token bootstrap**: `?token=` in the UI is only for saving token to localStorage on that device; API query-token auth is disabled by default.
- **Optional compatibility mode**: Set `ALLOW_QUERY_TOKEN=true` only if you intentionally need API query-token auth.

## Phone Setup (One-Time)

1. Install Tailscale on your phone
2. Open `http://<pc-tailscale-ip>:3838?token=YOUR_API_SECRET` once on a new device (optional)
3. Token is saved to localStorage — bookmark the page
4. Use **Settings → API token** anytime to update the token on that device
5. Add to Home Screen for app-like experience (iOS: Share → Add to Home Screen)

## UI Features

Bottom tabs — **Chat**, **Reader**, **Skills**, **Gym**, **Settings** — replace the
old crowded header icon bar. The Gym tab appears only when gym data is present.

- **Chat interface**: Natural language, rendered with Markdown
- **Research Reader**: Three tab-selectable views over the vault
  - *By Topic* — Library subfolders and podcast shows as colour-coded cards with
    note counts; tap to drill into that folder's notes
  - *By Date* — collapsible ISO-week groups (W32 · Aug 3 – Aug 9), newest open
  - *Recent* — flat feed of the last 7 days
  - Search box filters across every note regardless of the active view;
    pull-to-refresh re-scans the vault; every note deep-links into Obsidian mobile
- **Skills tab**: Full skill list with All / 🌐 Public / 🔒 Private filters
- **Gym tab**: 12-week programs for any number of profiles, each following
  either the cycling strength block or the strength-tone block
  - A compact athlete menu sits beside the Gym title. It is a native select
    filled from `/api/gym/profiles`, so it takes any number of athletes and
    opens the phone's own picker. The choice is remembered on the device, and
    a remembered athlete who no longer exists falls back to the first without
    losing the saved choice. Below it are the Week, Stats and Notes views
  - Program position follows the sessions done, not the calendar. Sessions go in
    order, W1 D1 to W12 D3, so a week that takes ten days stays the current week
    until its third session is done rather than rolling over on Monday
  - Week view opens on the week holding the next session. Each day card reads done,
    in progress, up next or locked, and a locked session opens read-only with the
    session that unlocks it. The week shows when its sessions actually happened
    ("Started 9 Sep · 2 of 3 done") instead of a calendar date range
  - A tracker above the week shows sessions done against where the plan expects them
    by now, this week's count, the projected finish at the current pace against the
    planned one, and every other athlete's position in one line. An athlete whose
    block hasn't started yet shows its start date instead
  - Session view logs load, reps and RPE per set with a numeric keypad, autosaves
    every change, shows rep ranges ("3 × 10–12") where the week has them, and
    links each exercise to its how-to and video
  - Weights read and type in the app-wide unit. Each exercise says what to type:
    both dumbbells together, one dumbbell, or the barbell total with the bar
    included. Target RPE reads in reps left ("RPE 7 · about 3 reps left"), a max
    test reads "build up to RPE 9.5", and a lift with no load yet says "pick a
    weight"
  - A session with a podcast picked for it shows the episode as a Spotify card,
    and the week list shows its title under the day
  - Finish workout runs the `gym-cyclist` skill and shows the assessment inline
  - Stats shows pace (sessions per week so far, projected against planned finish),
    weekly tonnage, adherence and average RPE. A cycling athlete also sees the
    estimated 1RM trend and power baselines. A strength-tone athlete sees the
    pull-up path checks, working loads and core re-checks instead
  - Text uses high-contrast tokens, and every number (loads, reps, RPE, stats,
    tracker counts) is drawn in the primary text colour
  - A finished session is read-only until reopened for safety and audit purposes
- **Skill chip**: Pin a skill to scope your messages
- **Settings tab**: API token, server restart, cancel request, live server status
- **Status indicator**: Green = ready, yellow = processing
- **Cancel button**: Kill a long-running request
- **Live streaming feedback**: Shows phases (starting, thinking, tool use, writing) while Claude runs
- **Tool activity pills**: Displays active/completed tool calls in real time
- **Completion metrics**: Shows duration/cost metadata when available
- **Dark theme**: Easy on eyes, OLED-friendly

## Tips

- Chat without selecting a skill — Claude sees the full skill list and picks the right one
- Pin a skill via the ⚡ button for repeated use (e.g., pin `obsidian` for vault ops)
- Use `/api/invoke/last30days` with `{args: "AI agents"}` for direct invocation
- The server auto-discovers new skills — add a SKILL.md and hit "reload"
- After editing `server.js` or `.env`, call `POST /api/admin/restart` so the launcher restarts the process cleanly

## Remote Restart

Use this when you changed server code or environment settings and need a full
process restart instead of a skill registry reload.

```powershell
$headers = @{ Authorization = "Bearer $env:API_SECRET" }
Invoke-RestMethod -Method Post -Uri "http://<tailscale-ip>:3838/api/admin/restart" -Headers $headers
```

If a Claude request is still running, the endpoint returns `409` unless you force it:

```powershell
$headers = @{ Authorization = "Bearer $env:API_SECRET"; 'Content-Type' = 'application/json' }
Invoke-RestMethod -Method Post -Uri "http://<tailscale-ip>:3838/api/admin/restart" -Headers $headers -Body '{"force":true}'
```

## Related Skills

- `obsidian` — Vault operations (commonly invoked remotely)
- `last30days` — Research (good for phone-triggered research)
- `visual-explainer` — Generates HTML visualizations
- `rbc-banking` — The original template this was generalised from
````
