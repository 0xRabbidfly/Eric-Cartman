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
| GET | `/api/gym/profiles` | Gym profiles with each one's next session, program week and pace against the plan (`{enabled:false}` when no gym data) |
| GET | `/api/gym/week/:n` | Week prescription plus per-day log status (`?profile=`) |
| GET | `/api/gym/session/:week/:day` | One day's prescription merged with its log (`?profile=`) |
| PUT | `/api/gym/session/:week/:day` | Save a partial log (`?profile=`) |
| POST | `/api/gym/session/:week/:day/finish` | Complete the session and start the assessment; body `{performedOn: "YYYY-MM-DD"}` is the phone's local date, used when the log has none and within a day of the server's; returns `{jobId}` (`?profile=`) |
| POST | `/api/gym/session/:week/:day/reopen` | Make a finished session editable again (`?profile=`) |
| GET | `/api/gym/exercises` | Exercise library with how-tos and videos (`?profile=`) |
| GET | `/api/gym/stats` | Week-by-week tonnage, RPE, adherence and 1RM trend (`?profile=`) |
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
- **Gym tab**: The 12-week cycling strength program for two profiles
  - Profile switcher, then Week, Stats and Notes views
  - Program position follows the sessions done, not the calendar. Sessions go in
    order, W1 D1 to W12 D3, so a week that takes ten days stays the current week
    until its third session is done rather than rolling over on Monday
  - Week view opens on the week holding the next session. Each day card reads done,
    in progress, up next or locked, and a locked session opens read-only with the
    session that unlocks it. The week shows when its sessions actually happened
    ("Started 9 Sep · 2 of 3 done") instead of a calendar date range
  - A tracker above the week shows sessions done against where the plan expects them
    by now, this week's count, the projected finish at the current pace against the
    planned one, and the other athlete's position in one line
  - Session view logs load, reps and RPE per set with a numeric keypad, autosaves
    every change, and links each exercise to its how-to and video
  - Finish workout runs the `gym-cyclist` skill and shows the assessment inline
  - Stats shows pace (sessions per week so far, projected against planned finish),
    estimated 1RM trend, weekly tonnage, adherence and average RPE
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
