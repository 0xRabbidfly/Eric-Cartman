/**
 * Remote Skills API Server
 * 
 * Chat with and invoke Eric Cartman skills from your phone via Tailscale.
 * Generalised from rbc-banking/simple-api.js.
 *
 * Architecture:
 *   - Auto-discovers all SKILL.md files from .github/skills/ and .claude/skills/
 *   - Mobile-first chat UI with skill picker
 *   - Claude CLI backend (one-shot or conversational)
 *   - Request queue prevents concurrent Claude processes
 *   - Token auth via API_SECRET in .env
 *   - SSE streaming for real-time responses
 *   - Binds 0.0.0.0 — reachable over Tailscale
 */

require('dotenv').config({ path: require('path').join(__dirname, '../../../.env') });

const express = require('express');
const cors    = require('cors');
const path    = require('path');
const fs      = require('fs');
const { spawn } = require('child_process');

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const PORT        = process.env.SKILLS_PORT || 3838;
const PROJECT_DIR = path.resolve(__dirname, '../../..');
const CLAUDE_PATH = process.env.CLAUDE_PATH || 'claude';
const API_SECRET  = process.env.API_SECRET;
const CLAUDE_MODEL = process.env.CLAUDE_MODEL || 'sonnet';
const ALLOW_QUERY_TOKEN = (process.env.ALLOW_QUERY_TOKEN || '').toLowerCase() === 'true';

if (!API_SECRET) {
  console.error('❌  API_SECRET not set in .env — aborting');
  process.exit(1);
}

// ---------------------------------------------------------------------------
// Skill Discovery
// ---------------------------------------------------------------------------

/**
 * Parse YAML-ish frontmatter from a SKILL.md string.
 * Doesn't need a full YAML parser — just key: value pairs.
 */
function parseFrontmatter(text) {
  const match = text.match(/^```+skill\s*\n([\s\S]*?)\n```+/m)
              || text.match(/^---\s*\n([\s\S]*?)\n---/m);
  if (!match) return {};
  const meta = {};
  for (const line of match[1].split('\n')) {
    const kv = line.match(/^(\w[\w-]*):\s*"?(.+?)"?\s*$/);
    if (kv) meta[kv[1]] = kv[2];
  }
  return meta;
}

/**
 * Scan skill directories and return a registry Map<name, { dir, meta, snippet }>.
 */
function discoverSkills() {
  const skills = new Map();
  const dirs = [
    path.join(PROJECT_DIR, '.github', 'skills'),
    path.join(PROJECT_DIR, '.claude', 'skills'),
  ];

  for (const base of dirs) {
    if (!fs.existsSync(base)) continue;
    for (const name of fs.readdirSync(base)) {
      const skillFile = path.join(base, name, 'SKILL.md');
      if (!fs.existsSync(skillFile)) continue;
      try {
        const raw = fs.readFileSync(skillFile, 'utf-8');
        const meta = parseFrontmatter(raw);
        // Grab first meaningful paragraph after the frontmatter as a snippet
        const body = raw.replace(/^```+skill[\s\S]*?```+/m, '')
                        .replace(/^---[\s\S]*?---/m, '')
                        .trim();
        const snippet = body.split('\n').filter(l => l.trim() && !l.startsWith('#'))
                            .slice(0, 2).join(' ').substring(0, 200);
        const source = base.includes('.claude') ? 'personal' : 'oss';
        skills.set(meta.name || name, {
          dir: path.join(base, name),
          file: skillFile,
          meta,
          snippet,
          source,
          rawLength: raw.length,
        });
      } catch (e) {
        console.warn(`[Skills] Error reading ${skillFile}:`, e.message);
      }
    }
  }
  return skills;
}

let skillRegistry = discoverSkills();
console.log(`[Skills] Discovered ${skillRegistry.size} skills`);
for (const [name, s] of skillRegistry) {
  const tag = s.source === 'personal' ? '🔒' : '🌐';
  console.log(`  ${tag} ${name}: ${(s.meta.description || s.snippet || '').substring(0, 80)}`);
}

// ---------------------------------------------------------------------------
// Express Setup
// ---------------------------------------------------------------------------

const app = express();
app.use(cors());
app.use(express.json());

// Auth middleware
function auth(req, res, next) {
  const headerToken = (req.headers.authorization || '').replace('Bearer ', '');
  const queryToken = ALLOW_QUERY_TOKEN
    ? req.query.token?.replace('Bearer ', '')
    : '';
  const token = headerToken || queryToken;
  if (token !== API_SECRET) return res.status(401).json({ error: 'Unauthorized' });
  next();
}

// ---------------------------------------------------------------------------
// Claude CLI Runner (queue-based, one at a time)
// ---------------------------------------------------------------------------

let requestQueue = [];
let isProcessing = false;
let currentGoal   = '';
let activeProcess  = null;

async function enqueue(handler) {
  return new Promise((resolve, reject) => {
    requestQueue.push({ handler, resolve, reject });
    processQueue();
  });
}

async function processQueue() {
  if (isProcessing || requestQueue.length === 0) return;
  isProcessing = true;
  const { handler, resolve, reject } = requestQueue.shift();
  try {
    const result = await handler();
    resolve(result);
  } catch (err) {
    reject(err);
  } finally {
    isProcessing = false;
    currentGoal = '';
    activeProcess = null;
    processQueue();
  }
}

/**
 * Run Claude CLI once and return the full result text.
 */
function runClaude(prompt, opts = {}) {
  return new Promise((resolve, reject) => {
    const model = opts.model || CLAUDE_MODEL;
    const args = [
      '--output-format', 'json',
      '--model', model,
      '--permission-mode', 'bypassPermissions',
      '-p', prompt,
    ];

    // If there's an MCP config, reference it
    const mcpConfig = path.join(PROJECT_DIR, '.mcp.json');
    if (fs.existsSync(mcpConfig)) {
      args.push('--mcp-config', mcpConfig.replace(/\\/g, '/'));
    }

    console.log(`[Claude] ${model} | ${prompt.substring(0, 100)}…`);
    const start = Date.now();

    const proc = spawn(CLAUDE_PATH, args, {
      cwd: PROJECT_DIR,
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env },
      shell: false,
    });
    activeProcess = proc;
    proc.stdin.end();

    let stdout = '', stderr = '';
    proc.stdout.on('data', d => stdout += d);
    proc.stderr.on('data', d => stderr += d);

    proc.on('close', code => {
      const elapsed = ((Date.now() - start) / 1000).toFixed(1);
      console.log(`[Claude] Done in ${elapsed}s (exit ${code})`);
      if (code === 0) {
        try {
          const json = JSON.parse(stdout);
          resolve(json.result || stdout.trim());
        } catch {
          resolve(stdout.trim() || 'Done (no output)');
        }
      } else {
        reject(new Error(stderr || `Claude exited ${code}`));
      }
    });

    proc.on('error', err => reject(new Error(`Claude spawn error: ${err.message}`)));
  });
}

/**
 * Run Claude CLI with streaming output.
 * Uses --output-format stream-json to get real-time JSONL events.
 * Calls onEvent(event) for each parsed event.
 * Returns a promise that resolves with the final result text.
 */
function runClaudeStreaming(prompt, onEvent, opts = {}) {
  return new Promise((resolve, reject) => {
    const model = opts.model || CLAUDE_MODEL;
    const args = [
      '--output-format', 'stream-json',
      '--verbose',
      '--model', model,
      '--permission-mode', 'bypassPermissions',
      '-p', prompt,
    ];

    const mcpConfig = path.join(PROJECT_DIR, '.mcp.json');
    if (fs.existsSync(mcpConfig)) {
      args.push('--mcp-config', mcpConfig.replace(/\\/g, '/'));
    }

    console.log(`[Claude:stream] ${model} | ${prompt.substring(0, 100)}…`);
    const start = Date.now();

    const proc = spawn(CLAUDE_PATH, args, {
      cwd: PROJECT_DIR,
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env },
      shell: false,
    });
    activeProcess = proc;
    proc.stdin.end();

    let stderr = '';
    let buffer = '';
    let resultText = '';

    proc.stdout.on('data', chunk => {
      buffer += chunk.toString();
      // Process complete lines
      const lines = buffer.split('\n');
      buffer = lines.pop(); // Keep incomplete line in buffer
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        try {
          const evt = JSON.parse(trimmed);
          // Extract useful events and forward them
          if (evt.type === 'content_block_delta' && evt.delta?.type === 'text_delta') {
            onEvent({ type: 'text', text: evt.delta.text });
          } else if (evt.type === 'content_block_start' && evt.content_block?.type === 'tool_use') {
            onEvent({ type: 'tool_start', tool: evt.content_block.name, id: evt.content_block.id });
          } else if (evt.type === 'content_block_start' && evt.content_block?.type === 'tool_result') {
            onEvent({ type: 'tool_result', id: evt.content_block.tool_use_id });
          } else if (evt.type === 'content_block_start' && evt.content_block?.type === 'thinking') {
            onEvent({ type: 'thinking_start' });
          } else if (evt.type === 'content_block_delta' && evt.delta?.type === 'thinking_delta') {
            onEvent({ type: 'thinking', text: evt.delta.thinking });
          } else if (evt.type === 'content_block_stop') {
            onEvent({ type: 'block_stop', index: evt.index });
          } else if (evt.type === 'system' && evt.subtype === 'init') {
            onEvent({ type: 'init', session_id: evt.session_id });
          } else if (evt.type === 'result') {
            resultText = evt.result || '';
            const elapsed = ((Date.now() - start) / 1000).toFixed(1);
            onEvent({
              type: 'done',
              result: resultText,
              duration: elapsed,
              cost: evt.cost_usd,
              totalCost: evt.total_cost_usd,
              numTurns: evt.num_turns,
            });
          }
        } catch {
          // Skip non-JSON lines (e.g. stderr leaking into stdout)
        }
      }
    });

    proc.stderr.on('data', d => stderr += d);

    proc.on('close', code => {
      const elapsed = ((Date.now() - start) / 1000).toFixed(1);
      console.log(`[Claude:stream] Done in ${elapsed}s (exit ${code})`);
      if (code === 0) {
        resolve(resultText || 'Done (no output)');
      } else {
        reject(new Error(stderr || `Claude exited ${code}`));
      }
    });

    proc.on('error', err => reject(new Error(`Claude spawn error: ${err.message}`)));
  });
}

/**
 * Build a system prompt that tells Claude about available skills.
 */
function buildSystemPrompt() {
  const lines = [
    'You are a helpful assistant running on the user\'s home PC, accessed remotely via phone.',
    'You have access to the following skills from the Eric Cartman meta-prompt library.',
    'When the user\'s request matches a skill, use it. Otherwise answer normally.',
    'Keep responses concise and mobile-friendly (the user is on a phone).',
    '',
    '## Available Skills',
  ];
  for (const [name, s] of skillRegistry) {
    const desc = s.meta.description || s.snippet || 'No description';
    lines.push(`- **${name}**: ${desc.substring(0, 150)}`);
  }
  lines.push('', 'When invoking a skill, read its SKILL.md from disk first for full instructions.');
  return lines.join('\n');
}

// ---------------------------------------------------------------------------
// API Routes
// ---------------------------------------------------------------------------

// Health / status
app.get('/api/status', auth, (req, res) => {
  res.json({
    active: isProcessing,
    goal: currentGoal,
    queueLength: requestQueue.length,
    skillCount: skillRegistry.size,
    auth: {
      queryTokenEnabled: ALLOW_QUERY_TOKEN,
    },
  });
});

// List discovered skills
app.get('/api/skills', auth, (req, res) => {
  const list = [];
  for (const [name, s] of skillRegistry) {
    list.push({
      name,
      description: s.meta.description || s.snippet || '',
      source: s.source,
      invocable: s.meta['user-invokable'] !== 'false',
    });
  }
  res.json({ skills: list });
});

// Reload skill registry
app.post('/api/skills/reload', auth, (req, res) => {
  skillRegistry = discoverSkills();
  console.log(`[Skills] Reloaded — ${skillRegistry.size} skills`);
  res.json({ count: skillRegistry.size });
});

// Read a specific skill's SKILL.md
app.get('/api/skills/:name', auth, (req, res) => {
  const skill = skillRegistry.get(req.params.name);
  if (!skill) return res.status(404).json({ error: 'Skill not found' });
  const content = fs.readFileSync(skill.file, 'utf-8');
  res.json({ name: req.params.name, ...skill.meta, content });
});

// Chat — main endpoint. Supports SSE streaming via Accept header.
app.post('/api/chat', auth, async (req, res) => {
  const { message, skill } = req.body;
  if (!message) return res.status(400).json({ error: 'message required' });

  const wantsStream = (req.headers.accept || '').includes('text/event-stream');

  // Build the prompt
  let prompt;
  if (skill && skillRegistry.has(skill)) {
    const s = skillRegistry.get(skill);
    const skillContent = fs.readFileSync(s.file, 'utf-8');
    prompt = [
      buildSystemPrompt(),
      '',
      `## Active Skill: ${skill}`,
      '```',
      skillContent.substring(0, 6000),
      '```',
      '',
      `User request: ${message}`,
    ].join('\n');
  } else {
    prompt = [
      buildSystemPrompt(),
      '',
      `User request: ${message}`,
    ].join('\n');
  }

  if (wantsStream) {
    // SSE streaming response
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no',
    });

    // Send initial event
    res.write(`data: ${JSON.stringify({ type: 'start', skill: skill || null })}\n\n`);

    try {
      currentGoal = message.substring(0, 60);
      const result = await enqueue(() => {
        return runClaudeStreaming(prompt, (evt) => {
          // Forward each streaming event to the client
          try { res.write(`data: ${JSON.stringify(evt)}\n\n`); } catch {}
        });
      });
      // Final done event (runClaudeStreaming already sends done, but ensure connection closes)
      res.end();
    } catch (err) {
      console.error('[Chat:stream] Error:', err.message);
      res.write(`data: ${JSON.stringify({ type: 'error', error: err.message })}\n\n`);
      res.end();
    }
  } else {
    // Non-streaming JSON response (backwards compatible)
    try {
      currentGoal = message.substring(0, 60);
      const result = await enqueue(() => runClaude(prompt));
      res.json({ result, skill: skill || null });
    } catch (err) {
      console.error('[Chat] Error:', err.message);
      res.status(500).json({ error: err.message });
    }
  }
});

// Chat with SSE streaming (GET — kept for direct URL/EventSource usage)
app.get('/api/chat/stream', auth, async (req, res) => {
  const message = req.query.q;
  const skill   = req.query.skill;
  if (!message) return res.status(400).json({ error: 'q param required' });

  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'X-Accel-Buffering': 'no',
  });

  // Build prompt (same as /api/chat)
  let prompt;
  if (skill && skillRegistry.has(skill)) {
    const s = skillRegistry.get(skill);
    const skillContent = fs.readFileSync(s.file, 'utf-8');
    prompt = [
      buildSystemPrompt(),
      '',
      `## Active Skill: ${skill}`,
      '```',
      skillContent.substring(0, 6000),
      '```',
      '',
      `User request: ${message}`,
    ].join('\n');
  } else {
    prompt = [buildSystemPrompt(), '', `User request: ${message}`].join('\n');
  }

  res.write(`data: ${JSON.stringify({ type: 'start', skill: skill || null })}\n\n`);

  try {
    currentGoal = message.substring(0, 60);
    const result = await enqueue(() => {
      return runClaudeStreaming(prompt, (evt) => {
        try { res.write(`data: ${JSON.stringify(evt)}\n\n`); } catch {}
      });
    });
    res.end();
  } catch (err) {
    res.write(`data: ${JSON.stringify({ type: 'error', error: err.message })}\n\n`);
    res.end();
  }
});

// Quick skill invocation (no chat context, just run it)
app.post('/api/invoke/:skill', auth, async (req, res) => {
  const name = req.params.skill;
  const skill = skillRegistry.get(name);
  if (!skill) return res.status(404).json({ error: `Skill "${name}" not found` });

  const { args } = req.body;
  const skillContent = fs.readFileSync(skill.file, 'utf-8');

  const prompt = [
    `Execute the following skill. Follow its instructions precisely.`,
    '',
    '## SKILL.md',
    '```',
    skillContent.substring(0, 8000),
    '```',
    '',
    `User arguments: ${args || '(none — use defaults)'}`,
  ].join('\n');

  try {
    currentGoal = `/${name} ${(args || '').substring(0, 40)}`;
    const result = await enqueue(() => runClaude(prompt));
    res.json({ skill: name, result });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Cancel current request (kills the Claude process)
app.post('/api/cancel', auth, (req, res) => {
  if (activeProcess) {
    try { activeProcess.kill('SIGTERM'); } catch {}
    activeProcess = null;
    console.log('[Cancel] Killed active Claude process');
    res.json({ cancelled: true });
  } else {
    res.json({ cancelled: false, message: 'Nothing running' });
  }
});

// ---------------------------------------------------------------------------
// Serve the UI
// ---------------------------------------------------------------------------
app.get('/', (req, res) => {
  const uiPath = path.join(__dirname, 'ui.html');
  if (fs.existsSync(uiPath)) {
    res.sendFile(uiPath);
  } else {
    res.send('<h1>UI not found — create ui.html</h1>');
  }
});

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------
app.listen(PORT, '0.0.0.0', () => {
  console.log('');
  console.log(`🚀  Remote Skills API running on port ${PORT}`);
  console.log(`📍  Local:     http://localhost:${PORT}`);
  console.log(`📱  Tailscale: http://<your-tailscale-ip>:${PORT}`);
  console.log(`🔐  Auth:      API_SECRET ${API_SECRET ? '✅' : '❌ MISSING'}`);
  console.log(`🛡️  Query auth: ${ALLOW_QUERY_TOKEN ? 'ENABLED' : 'DISABLED (header-only)'}`);
  console.log(`🤖  Model:     ${CLAUDE_MODEL}`);
  console.log(`📦  Skills:    ${skillRegistry.size} discovered`);
  console.log(`💡  Claude:    ${CLAUDE_PATH}`);
  console.log('');
});
