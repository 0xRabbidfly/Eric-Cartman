# MCP Configuration Guide

All MCP config lives in `.claude/`. Nothing at project root.

## Files

| File | Used By | Purpose |
|------|---------|---------|
| `mcp.json` | Interactive Claude Code sessions, cowork | Default config. Generic Playwright (npx, no persistent profile), Firecrawl. |
| `mcp-browser.json` | remote-skills-api only | Browser skills (`zehrs-grocery`, `used-car-search`). Playwright connects to the on-demand HTTP server that `ensurePlaywright()` manages on port 3939. Also includes Firecrawl for scraping skills. |
| `rbc-mcp.json` | remote-skills-api, Task Scheduler | RBC banking skill. Spawns its own Playwright via stdio with stealth init + persistent `C:/RBC-Browser` profile. Skips the shared HTTP Playwright server. |
| `telegram-mcp.json` | Telegram channel sessions | Empty `mcpServers` block for phone-based chat with no MCP tools loaded. |
| `google-mcp.json` | Inactive (future use) | Google Workspace MCP config. Parked here for when needed. |

## How remote-skills-api Routes

`getMcpConfig()` in `server.js` selects the config passed to `claude --mcp-config`:

1. **rbc-banking** → `rbc-mcp.json` (stdio Playwright, no `ensurePlaywright()`)
2. **zehrs-grocery, used-car-search** → `mcp-browser.json` (HTTP Playwright on port 3939 via `ensurePlaywright()`)
3. **Everything else** → `mcp.json`

## Gitignore

All files in this folder containing secrets are gitignored:
- `mcp.json`, `mcp-browser.json`, `rbc-mcp.json`, `telegram-mcp.json`, `google-mcp.json`

## Adding a New Browser Skill

1. Add the skill name to `BROWSER_SKILLS` in `server.js`
2. If it needs its own Playwright config (custom profile, stealth), add to `STDIO_BROWSER_SKILLS` and create a dedicated `*-mcp.json`
3. Otherwise it uses the shared HTTP Playwright via `mcp-browser.json`
