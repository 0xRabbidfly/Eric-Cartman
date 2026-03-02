````skill
---
name: remote-skills-api
description: Mobile-friendly web server to chat with and invoke Eric Cartman skills remotely via Tailscale. Generalised from rbc-banking/simple-api.js. Start once on your PC, access from your phone anywhere.
argument-hint: start, stop
user-invokable: true
disable-model-invocation: false
metadata:
  author: 0xrabbidfly
  version: "1.0.0"
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
4. **API_SECRET** set in project root `.env`

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
$ws.TargetPath = "Z:\Projects\Eric-Cartman\.github\skills\remote-skills-api\start-service.bat"
$ws.WorkingDirectory = "Z:\Projects\Eric-Cartman"
$ws.WindowStyle = 7  # minimized
$ws.Save()
```

The included `start-service.bat` sets the correct working directory and
launches node. A minimized cmd window stays in your taskbar.

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
| POST | `/api/chat` | Send a chat message (JSON: `{message, skill?}`) |
| GET | `/api/chat/stream` | SSE streaming chat (`?q=...&skill=...`) |
| POST | `/api/invoke/:skill` | Direct skill invocation (`{args}`) |
| POST | `/api/cancel` | Kill running Claude process |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_SECRET` | (required) | Bearer token for auth |
| `SKILLS_PORT` | `3838` | Server port |
| `CLAUDE_PATH` | `claude` | Path to Claude CLI binary |
| `CLAUDE_MODEL` | `sonnet` | Model for Claude CLI |

## Security

- **Token auth**: Every request requires `Authorization: Bearer <API_SECRET>`
- **Tailscale**: Network-level encryption + identity. Not exposed to public internet.
- **No secrets in URL**: Token passed via header; URL token only for initial setup (stripped after save)

## Phone Setup (One-Time)

1. Install Tailscale on your phone
2. Open `http://<pc-tailscale-ip>:3838?token=YOUR_API_SECRET`
3. Token is saved to localStorage — bookmark the page
4. Add to Home Screen for app-like experience (iOS: Share → Add to Home Screen)

## UI Features

- **Chat interface**: Natural language, rendered with Markdown
- **Skill picker**: Bottom drawer with all discovered skills
- **Skill chip**: Pin a skill to scope your messages
- **Status indicator**: Green = ready, yellow = processing
- **Cancel button**: Kill a long-running request
- **Dark theme**: Easy on eyes, OLED-friendly

## Tips

- Chat without selecting a skill — Claude sees the full skill list and picks the right one
- Pin a skill via the ⚡ button for repeated use (e.g., pin `obsidian` for vault ops)
- Use `/api/invoke/last30days` with `{args: "AI agents"}` for direct invocation
- The server auto-discovers new skills — add a SKILL.md and hit "reload"

## Related Skills

- `obsidian` — Vault operations (commonly invoked remotely)
- `last30days` — Research (good for phone-triggered research)
- `visual-explainer` — Generates HTML visualizations
- `rbc-banking` — The original template this was generalised from
````
