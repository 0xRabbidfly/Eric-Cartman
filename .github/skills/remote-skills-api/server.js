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
const RESTART_EXIT_CODE = process.env.RESTART_EXIT_CODE
  ? parseInt(process.env.RESTART_EXIT_CODE, 10)
  : 75;

// LLM caps: token budget and tool-call limit
// MAX_BUDGET_USD  — max dollars per request (passed as --max-budget-usd to Claude CLI)
// MAX_TOOL_CALLS  — max tool invocations before the request is killed (0 = unlimited)
const MAX_BUDGET_USD  = process.env.MAX_BUDGET_USD  ? parseFloat(process.env.MAX_BUDGET_USD)  : null;
const MAX_TOOL_CALLS  = process.env.MAX_TOOL_CALLS  ? parseInt(process.env.MAX_TOOL_CALLS, 10) : 0;

// Request timeout — kill Claude if it hangs (default 5 min, 0 = no timeout)
const CLAUDE_TIMEOUT_MS = process.env.CLAUDE_TIMEOUT_MS
  ? parseInt(process.env.CLAUDE_TIMEOUT_MS, 10)
  : 5 * 60 * 1000;

if (!API_SECRET) {
  console.error('❌  API_SECRET not set in .env — aborting');
  process.exit(1);
}

// ---------------------------------------------------------------------------
// Usage Stats (persisted to disk)
// ---------------------------------------------------------------------------
const USAGE_FILE = path.join(__dirname, 'usage-stats.json');
let usageStats = { skills: {} };
try {
  if (fs.existsSync(USAGE_FILE)) {
    const raw = JSON.parse(fs.readFileSync(USAGE_FILE, 'utf-8'));
    usageStats = { skills: {}, ...raw };
  }
} catch {}

function trackSkillUsage(skillName) {
  if (!skillName) return;
  usageStats.skills[skillName] = (usageStats.skills[skillName] || 0) + 1;
  try { fs.writeFileSync(USAGE_FILE, JSON.stringify(usageStats, null, 2)); } catch {}
}

// ---------------------------------------------------------------------------
// Session Management (in-memory + persisted JSON, configurable TTL)
// ---------------------------------------------------------------------------
// Set SESSION_TTL_HOURS=0 to disable expiry. Default: 24 hours.
const SESSION_TTL_HOURS = parseFloat(process.env.SESSION_TTL_HOURS ?? '24');
const SESSION_TTL_MS = SESSION_TTL_HOURS > 0 ? SESSION_TTL_HOURS * 60 * 60 * 1000 : Infinity;
// Context reuse window is intentionally much shorter than session persistence.
// Only same-scope conversations within this freshness window can reuse history.
const SESSION_CONTEXT_TTL_HOURS = parseFloat(process.env.SESSION_CONTEXT_TTL_HOURS ?? '2');
const SESSION_CONTEXT_TTL_MS = SESSION_CONTEXT_TTL_HOURS > 0
  ? SESSION_CONTEXT_TTL_HOURS * 60 * 60 * 1000
  : Infinity;
const SESSIONS_FILE  = path.join(__dirname, 'sessions.json');
const activeSessions = new Map();
const GENERAL_SCOPE = '__general__';

function makeSessionId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

function loadSessions() {
  try {
    if (!fs.existsSync(SESSIONS_FILE)) return;
    const data = JSON.parse(fs.readFileSync(SESSIONS_FILE, 'utf-8'));
    const now  = Date.now();
    for (const [id, sess] of Object.entries(data || {})) {
      if (now - sess.lastActivity <= SESSION_TTL_MS) activeSessions.set(id, sess);
    }
    console.log(`[Sessions] Loaded ${activeSessions.size} active session(s) from disk`);
  } catch {}
}

function saveSessions() {
  try {
    const obj = {};
    for (const [id, sess] of activeSessions) obj[id] = sess;
    fs.writeFileSync(SESSIONS_FILE, JSON.stringify(obj, null, 2));
  } catch {}
}

function getOrCreateSession(id) {
  const now = Date.now();
  if (id && activeSessions.has(id)) {
    const sess = activeSessions.get(id);
    if (now - sess.lastActivity <= SESSION_TTL_MS) return sess;
    activeSessions.delete(id);
  }
  const sess = {
    id: makeSessionId(),
    createdAt: now,
    lastActivity: now,
    messageCount: 0,
    skills: [],
    history: [],
    contextScope: GENERAL_SCOPE,
    contextStartedAt: now,
    contextLastActivity: now,
  };
  activeSessions.set(sess.id, sess);
  saveSessions();
  return sess;
}

function appendHistory(sess, role, content, maxTurns = 10) {
  if (!sess.history) sess.history = [];
  sess.history.push({ role, content: content.substring(0, 4000) });
  if (sess.history.length > maxTurns * 2) {
    sess.history = sess.history.slice(-(maxTurns * 2));
  }
  saveSessions();
}

function formatInvokeHistoryEntry(skillName, args) {
  const trimmedArgs = typeof args === 'string' ? args.trim() : '';
  return trimmedArgs ? `/${skillName} ${trimmedArgs}` : `/${skillName}`;
}

function getConversationScope(skillName) {
  return skillName || GENERAL_SCOPE;
}

function isContextExpired(sess, now = Date.now()) {
  if (!isFinite(SESSION_CONTEXT_TTL_MS)) return false;
  const lastContextActivity = sess.contextLastActivity || sess.lastActivity || 0;
  return (now - lastContextActivity) > SESSION_CONTEXT_TTL_MS;
}

function rewriteSessionsFile(reason, keepSession = null) {
  try {
    if (fs.existsSync(SESSIONS_FILE)) fs.unlinkSync(SESSIONS_FILE);
  } catch (err) {
    console.warn(`[Sessions] Failed to delete sessions file during reset (${reason}): ${err.message}`);
  }

  activeSessions.clear();
  if (keepSession) activeSessions.set(keepSession.id, keepSession);
  saveSessions();
  console.log(`[Sessions] Reset persisted history (${reason})`);
}

function resetSessionContext(sess, scope, reason) {
  const now = Date.now();
  sess.history = [];
  sess.skills = scope === GENERAL_SCOPE ? [] : [scope];
  sess.contextScope = scope;
  sess.contextStartedAt = now;
  sess.contextLastActivity = now;
  sess.lastActivity = now;
  rewriteSessionsFile(reason, sess);
  return sess;
}

function getScopedHistory(sess, scope) {
  if (!sess.history || sess.history.length === 0) return [];
  if ((sess.contextScope || GENERAL_SCOPE) !== scope) return [];
  if (isContextExpired(sess)) return [];
  return sess.history;
}

function prepareSessionContext(sess, scope) {
  const previousScope = sess.contextScope || GENERAL_SCOPE;
  if (previousScope !== scope) {
    return resetSessionContext(sess, scope, `scope changed: ${previousScope} -> ${scope}`);
  }
  if (isContextExpired(sess)) {
    return resetSessionContext(sess, scope, `context expired for scope ${scope}`);
  }

  const now = Date.now();
  sess.contextScope = scope;
  sess.contextLastActivity = now;
  sess.lastActivity = now;
  if (scope !== GENERAL_SCOPE && !sess.skills.includes(scope)) sess.skills = [scope];
  saveSessions();
  return sess;
}

function touchSession(sessionId, skillName) {
  const sess = getOrCreateSession(sessionId);
  sess.lastActivity = Date.now();
  sess.messageCount++;
  if (skillName && !sess.skills.includes(skillName)) sess.skills.push(skillName);
  saveSessions();
  return sess;
}

// Purge expired sessions every 10 minutes (skipped if TTL is infinite)
if (isFinite(SESSION_TTL_MS)) {
  setInterval(() => {
    const now = Date.now();
    let purged = 0;
    for (const [id, sess] of activeSessions) {
      if (now - sess.lastActivity > SESSION_TTL_MS) { activeSessions.delete(id); purged++; }
    }
    if (purged) { console.log(`[Sessions] Purged ${purged} expired session(s)`); saveSessions(); }
  }, 10 * 60_000);
}

loadSessions();

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
let serverHandle   = null;
let restartScheduled = false;

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

function scheduleRestart(reason) {
  if (restartScheduled) return;
  restartScheduled = true;
  console.log(`[Admin] Restart requested: ${reason}`);

  const exitWithRestartCode = () => {
    console.log(`[Admin] Exiting with restart code ${RESTART_EXIT_CODE}`);
    process.exit(RESTART_EXIT_CODE);
  };

  setTimeout(exitWithRestartCode, 1500);

  if (serverHandle) {
    try {
      serverHandle.close(() => exitWithRestartCode());
    } catch {
      // Fallback timer above will still terminate the process.
    }
  }
}

/**
 * Run Claude CLI once and return the full result text.
 */
function runClaude(prompt, opts = {}) {
  return new Promise((resolve, reject) => {
    const model = opts.model || CLAUDE_MODEL;
    const args = [
      '--print',
      '--output-format', 'json',
      '--input-format', 'text',
      '--model', model,
      '--permission-mode', 'bypassPermissions',
    ];

    if (MAX_BUDGET_USD != null) args.push('--max-budget-usd', String(MAX_BUDGET_USD));

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
    proc.stdin.end(prompt);

    let killTimeout;
    if (CLAUDE_TIMEOUT_MS > 0) {
      killTimeout = setTimeout(() => {
        console.warn(`[Claude] Timeout (${CLAUDE_TIMEOUT_MS / 1000}s) — killing hung process`);
        try { proc.kill('SIGTERM'); } catch {}
      }, CLAUDE_TIMEOUT_MS);
    }

    let stdout = '', stderr = '';
    proc.stdout.on('data', d => stdout += d);
    proc.stderr.on('data', d => stderr += d);

    proc.on('close', code => {
      if (killTimeout) clearTimeout(killTimeout);
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
      '--print',
      '--output-format', 'stream-json',
      '--input-format', 'text',
      '--verbose',
      '--model', model,
      '--permission-mode', 'bypassPermissions',
    ];

    if (MAX_BUDGET_USD != null) args.push('--max-budget-usd', String(MAX_BUDGET_USD));

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
    proc.stdin.end(prompt);

    let killTimeout;
    if (CLAUDE_TIMEOUT_MS > 0) {
      killTimeout = setTimeout(() => {
        console.warn(`[Claude:stream] Timeout (${CLAUDE_TIMEOUT_MS / 1000}s) — killing hung process`);
        try { proc.kill('SIGTERM'); } catch {}
        onEvent({ type: 'error', code: 'timeout', error: `Request timed out after ${CLAUDE_TIMEOUT_MS / 1000}s` });
      }, CLAUDE_TIMEOUT_MS);
    }

    let stderr = '';
    let buffer = '';
    let resultText = '';
    let toolCallCount = 0;

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
            toolCallCount++;
            if (MAX_TOOL_CALLS > 0 && toolCallCount > MAX_TOOL_CALLS) {
              console.warn(`[Claude:stream] Tool call limit (${MAX_TOOL_CALLS}) reached — killing process`);
              try { proc.kill('SIGTERM'); } catch {}
              onEvent({ type: 'error', code: 'tool_limit_exceeded', error: `Tool call limit of ${MAX_TOOL_CALLS} reached` });
              return;
            }
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
      if (killTimeout) clearTimeout(killTimeout);
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
    'Do not shorten, summarize, or simplify skill execution because the user is on mobile.',
    'When a skill is selected, follow the skill exactly and preserve complete output.',
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

function buildHistoryBlock(history) {
  if (!history || history.length === 0) return '';
  const lines = ['', '## Conversation History'];
  for (const msg of history) {
    const label = msg.role === 'user' ? 'User' : 'Assistant';
    lines.push(`**${label}**: ${msg.content}`);
  }
  return lines.join('\n');
}

function buildChatPrompt(message, skill, history = []) {
  const historyBlock = buildHistoryBlock(history);

  if (skill && skillRegistry.has(skill)) {
    const s = skillRegistry.get(skill);
    const skillContent = fs.readFileSync(s.file, 'utf-8');
    return [
      buildSystemPrompt(),
      '',
      `## Active Skill: ${skill}`,
      'IMPORTANT: When this skill has workflow steps with shell commands, you MUST execute them',
      'using the Bash tool. Do not just describe or explain the commands — actually run them.',
      'Run each step, check output, and proceed to the next. The working directory is the project root.',
      '```',
      skillContent,
      '```',
      historyBlock,
      '',
      `User request: ${message}`,
    ].join('\n');
  }

  return [
    buildSystemPrompt(),
    historyBlock,
    '',
    `User request: ${message}`,
  ].join('\n');
}

function buildInvokePrompt(name, args) {
  const skill = skillRegistry.get(name);
  const skillContent = fs.readFileSync(skill.file, 'utf-8');
  return [
    `Execute the following skill by RUNNING the actual commands listed in the workflow steps.`,
    `You MUST use the Bash tool to execute each shell command — do not just describe or explain them.`,
    `Run each step in sequence, check the output, and proceed to the next step.`,
    `The working directory is the project root. Python and node are available on PATH.`,
    '',
    '## SKILL.md',
    '```',
    skillContent,
    '```',
    '',
    `User arguments: ${args || '(none — use defaults)'}`,
  ].join('\n');
}

function parseSlashInvocation(message) {
  const m = (message || '').trim().match(/^\/([a-zA-Z0-9][\w-]*)\s*(.*)$/);
  if (!m) return null;
  return {
    skill: m[1],
    args: (m[2] || '').trim(),
  };
}

function classifyError(err, fallbackCode = 'request_failed') {
  const msg = (err?.message || 'Unknown error').trim();
  const low = msg.toLowerCase();

  if (low.includes('spawn error')) {
    return {
      code: 'claude_spawn_failed',
      error: msg,
      hint: 'Check CLAUDE_PATH and that Claude CLI is installed and runnable.',
    };
  }

  if (low.includes('exited')) {
    return {
      code: 'claude_exit_nonzero',
      error: msg,
      hint: 'Claude process failed. Check server logs for stderr details.',
    };
  }

  if (low.includes('invalid choice') || low.includes('unrecognized arguments')) {
    return {
      code: 'invalid_skill_args',
      error: msg,
      hint: 'The invoked skill command arguments are unsupported by its script.',
    };
  }

  return {
    code: fallbackCode,
    error: msg,
  };
}

function resolveChatRequest(message, selectedSkill, history = []) {
  const slash = parseSlashInvocation(message);
  if (!slash) {
    const skill = selectedSkill && skillRegistry.has(selectedSkill) ? selectedSkill : null;
    return {
      mode: 'chat',
      skill,
      message,
      prompt: buildChatPrompt(message, skill, history),
      currentGoal: message.substring(0, 60),
    };
  }

  if (!skillRegistry.has(slash.skill)) {
    return {
      error: {
        status: 404,
        code: 'skill_not_found',
        error: `Skill "${slash.skill}" not found`,
        hint: 'Use an existing skill name from /api/skills or the skill picker.',
      },
    };
  }

  return {
    mode: 'invoke',
    skill: slash.skill,
    args: slash.args,
    prompt: buildInvokePrompt(slash.skill, slash.args),
    currentGoal: `/${slash.skill} ${slash.args.substring(0, 40)}`.trim(),
  };
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
      usageCount: usageStats.skills[name] || 0,
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

  // Session + usage tracking with strict scope guards
  const sess = touchSession(req.headers['x-session-id'], null);
  const seedResolved = resolveChatRequest(message, skill, []);
  if (seedResolved.error) {
    if (wantsStream) {
      res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
      });
      res.write(`data: ${JSON.stringify({ type: 'error', ...seedResolved.error })}\n\n`);
      return res.end();
    }
    return res.status(seedResolved.error.status).json(seedResolved.error);
  }

  const conversationScope = getConversationScope(seedResolved.skill);
  prepareSessionContext(sess, conversationScope);
  const scopedHistory = getScopedHistory(sess, conversationScope);
  const resolved = resolveChatRequest(message, skill, scopedHistory);
  if (resolved.skill) {
    if (!sess.skills.includes(resolved.skill)) sess.skills.push(resolved.skill);
    trackSkillUsage(resolved.skill);
    saveSessions();
  }

  if (resolved.error) {
    if (wantsStream) {
      res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
      });
      res.write(`data: ${JSON.stringify({ type: 'error', ...resolved.error })}\n\n`);
      return res.end();
    }
    return res.status(resolved.error.status).json(resolved.error);
  }

  const prompt = resolved.prompt;

  if (wantsStream) {
    // SSE streaming response
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no',
      'X-Session-ID': sess.id,
      'Access-Control-Expose-Headers': 'X-Session-ID',
    });
    res.flushHeaders();  // Force headers out immediately

    // Send initial event (includes session ID for client)
    res.write(`data: ${JSON.stringify({ type: 'start', skill: resolved.skill || null, mode: resolved.mode, sessionId: sess.id })}\n\n`);

    // Keepalive heartbeat — real data events so they flush through any
    // intermediate buffering and keep mobile Safari from killing the connection
    const heartbeat = setInterval(() => {
      try { res.write(`data: ${JSON.stringify({ type: 'heartbeat', ts: Date.now() })}\n\n`); } catch {}
    }, 10000);

    try {
      currentGoal = resolved.currentGoal;
      appendHistory(sess, 'user', message);
      sess.contextLastActivity = Date.now();
      saveSessions();
      const result = await enqueue(() => {
        return runClaudeStreaming(prompt, (evt) => {
          // Forward each streaming event to the client
          try { res.write(`data: ${JSON.stringify(evt)}\n\n`); } catch {}
        });
      });
      appendHistory(sess, 'assistant', result);
      sess.contextLastActivity = Date.now();
      saveSessions();
      // Final done event (runClaudeStreaming already sends done, but ensure connection closes)
      res.end();
    } catch (err) {
      const e = classifyError(err, 'chat_stream_failed');
      console.error('[Chat:stream] Error:', e.error);
      res.write(`data: ${JSON.stringify({ type: 'error', ...e })}\n\n`);
      res.end();
    } finally {
      clearInterval(heartbeat);
    }
  } else {
    // Non-streaming JSON response (backwards compatible)
    res.setHeader('X-Session-ID', sess.id);
    res.setHeader('Access-Control-Expose-Headers', 'X-Session-ID');
    try {
      currentGoal = resolved.currentGoal;
      appendHistory(sess, 'user', message);
      sess.contextLastActivity = Date.now();
      saveSessions();
      const result = await enqueue(() => runClaude(prompt));
      appendHistory(sess, 'assistant', result);
      sess.contextLastActivity = Date.now();
      saveSessions();
      res.json({ result, skill: resolved.skill || null, mode: resolved.mode, sessionId: sess.id });
    } catch (err) {
      const e = classifyError(err, 'chat_failed');
      console.error('[Chat] Error:', e.error);
      res.status(500).json(e);
    }
  }
});

// Chat with SSE streaming (GET — kept for direct URL/EventSource usage)
app.get('/api/chat/stream', auth, async (req, res) => {
  const message = String(req.query.q || '');
  const skill   = String(req.query.skill || '');
  if (!message) return res.status(400).json({ error: 'q param required' });

  const sess = touchSession(req.headers['x-session-id'] || req.query.sessionId, null);
  const seedResolved = resolveChatRequest(message, skill || null, []);
  if (!seedResolved.error) {
    const conversationScope = getConversationScope(seedResolved.skill);
    prepareSessionContext(sess, conversationScope);
  }
  const resolved = seedResolved.error
    ? seedResolved
    : resolveChatRequest(message, skill || null, getScopedHistory(sess, getConversationScope(seedResolved.skill)));
  if (resolved.error) {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no',
    });
    res.write(`data: ${JSON.stringify({ type: 'error', ...resolved.error })}\n\n`);
    return res.end();
  }

  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'X-Accel-Buffering': 'no',
  });
  res.flushHeaders();  // Force headers out immediately

  const prompt = resolved.prompt;

  res.write(`data: ${JSON.stringify({ type: 'start', skill: resolved.skill || null, mode: resolved.mode })}\n\n`);

  // Keepalive heartbeat — real data events so they flush through any
  // intermediate buffering and keep mobile Safari from killing the connection
  const heartbeat = setInterval(() => {
    try { res.write(`data: ${JSON.stringify({ type: 'heartbeat', ts: Date.now() })}\n\n`); } catch {}
  }, 10000);

  try {
    currentGoal = resolved.currentGoal;
    appendHistory(sess, 'user', message);
    sess.contextLastActivity = Date.now();
    saveSessions();
    const result = await enqueue(() => {
      return runClaudeStreaming(prompt, (evt) => {
        try { res.write(`data: ${JSON.stringify(evt)}\n\n`); } catch {}
      });
    });
    appendHistory(sess, 'assistant', result);
    sess.contextLastActivity = Date.now();
    saveSessions();
    res.end();
  } catch (err) {
    const e = classifyError(err, 'chat_stream_failed');
    res.write(`data: ${JSON.stringify({ type: 'error', ...e })}\n\n`);
    res.end();
  } finally {
    clearInterval(heartbeat);
  }
});

// Quick skill invocation (no chat context, just run it)
app.post('/api/invoke/:skill', auth, async (req, res) => {
  const name = req.params.skill;
  const skill = skillRegistry.get(name);
  if (!skill) {
    return res.status(404).json({
      code: 'skill_not_found',
      error: `Skill "${name}" not found`,
      hint: 'Use /api/skills to list invocable skills.',
    });
  }

  const { args } = req.body;
  const prompt = buildInvokePrompt(name, args);

  const sess = touchSession(req.headers['x-session-id'], name);
  prepareSessionContext(sess, getConversationScope(name));
  trackSkillUsage(name);
  res.setHeader('X-Session-ID', sess.id);
  res.setHeader('Access-Control-Expose-Headers', 'X-Session-ID');

  try {
    currentGoal = `/${name} ${(args || '').substring(0, 40)}`;
    appendHistory(sess, 'user', formatInvokeHistoryEntry(name, args));
    const result = await enqueue(() => runClaude(prompt));
    appendHistory(sess, 'assistant', result);
    res.json({ skill: name, result, sessionId: sess.id });
  } catch (err) {
    const e = classifyError(err, 'invoke_failed');
    appendHistory(sess, 'assistant', `Error: ${e.error}${e.hint ? `\n\n${e.hint}` : ''}`);
    res.status(500).json(e);
  }
});

// Session info
app.get('/api/session', auth, (req, res) => {
  const sess = getOrCreateSession(req.headers['x-session-id']);
  const now  = Date.now();
  res.setHeader('X-Session-ID', sess.id);
  res.setHeader('Access-Control-Expose-Headers', 'X-Session-ID');
  res.json({
    id:             sess.id,
    createdAt:      sess.createdAt,
    lastActivity:   sess.lastActivity,
    messageCount:   sess.messageCount,
    skills:         sess.skills,
    history:        sess.history || [],
    expiresIn:      isFinite(SESSION_TTL_MS) ? Math.max(0, SESSION_TTL_MS - (now - sess.lastActivity)) : null,
    activeSessions: activeSessions.size,
  });
});

// Skill usage stats
app.get('/api/usage', auth, (req, res) => {
  const sorted = Object.entries(usageStats.skills)
    .sort(([, a], [, b]) => b - a)
    .map(([name, count]) => ({ name, count }));
  res.json({ skills: sorted, total: sorted.reduce((s, x) => s + x.count, 0) });
});

// Restart the API process so the launcher can relaunch it.
app.post('/api/admin/restart', auth, (req, res) => {
  const force = req.body?.force === true;
  const busy = isProcessing || requestQueue.length > 0 || activeProcess;

  if (busy && !force) {
    return res.status(409).json({
      restarting: false,
      error: 'Server is busy',
      hint: 'Retry when the queue is empty, or send {"force":true} to cancel the active Claude process and restart anyway.',
      active: isProcessing,
      queueLength: requestQueue.length,
    });
  }

  if (force) {
    requestQueue = [];
    if (activeProcess) {
      try { activeProcess.kill('SIGTERM'); } catch {}
      activeProcess = null;
    }
  }

  res.json({ restarting: true, exitCode: RESTART_EXIT_CODE, forced: force });
  setTimeout(() => scheduleRestart(`remote API request from ${req.ip}${force ? ' (forced)' : ''}`), 100);
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
serverHandle = app.listen(PORT, '0.0.0.0', () => {
  console.log('');
  console.log(`🚀  Remote Skills API running on port ${PORT}`);
  console.log(`📍  Local:     http://localhost:${PORT}`);
  console.log(`📱  Tailscale: http://<your-tailscale-ip>:${PORT}`);
  console.log(`🔐  Auth:      API_SECRET ${API_SECRET ? '✅' : '❌ MISSING'}`);
  console.log(`🛡️  Query auth: ${ALLOW_QUERY_TOKEN ? 'ENABLED' : 'DISABLED (header-only)'}`);
  console.log(`🤖  Model:     ${CLAUDE_MODEL}`);
  console.log(`📦  Skills:    ${skillRegistry.size} discovered`);
  console.log(`💡  Claude:    ${CLAUDE_PATH}`);
  console.log(`🔁  Restart code: ${RESTART_EXIT_CODE}`);
  console.log(`⏱️  Session TTL: ${isFinite(SESSION_TTL_MS) ? `${SESSION_TTL_HOURS}h` : 'unlimited'}`);
  console.log(`💰  Budget cap: ${MAX_BUDGET_USD != null ? `$${MAX_BUDGET_USD}` : 'none'}`);
  console.log(`🔧  Tool cap:   ${MAX_TOOL_CALLS > 0 ? `${MAX_TOOL_CALLS} calls` : 'none'}`);
  console.log(`⏱️  Claude timeout: ${CLAUDE_TIMEOUT_MS > 0 ? `${CLAUDE_TIMEOUT_MS / 1000}s` : 'none'}`);
  console.log('');
});
