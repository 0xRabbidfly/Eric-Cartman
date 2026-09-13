const test = require('node:test');
const assert = require('node:assert/strict');
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const { localDateString } = require('./gym-store');

const SECRET = 'test-secret-for-gym-routes';
const PORT = 3947;
const BASE = `http://127.0.0.1:${PORT}`;

function seedDataRoot() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'gym-routes-'));
  const write = (rel, obj) => {
    const target = path.join(root, rel);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, JSON.stringify(obj), 'utf8');
  };
  write('profiles.json', {
    programWeeks: 12,
    profiles: [{ id: 'athlete-a', name: 'Athlete A', startDate: '2026-09-07' }],
  });
  write('exercises.json', { 'back-squat': { key: 'back-squat', name: 'Back squat', video: 'https://v' } });
  for (let n = 1; n <= 12; n += 1) {
    write(`athlete-a/weeks/W${n}.json`, {
      week: n, block: 'test', blockLabel: 'Test week', goal: 'g', retest: true,
      loadsResolved: n === 1, generatedAt: null,
      days: [1, 2, 3].map((day) => ({
        day, title: `Day ${day}`, estMinutes: 50, warmup: ['bike'],
        items: [{
          id: 'a-back-squat', block: 'A', exerciseKey: 'back-squat', label: 'Back squat',
          sets: 3, reps: 3, resultType: 'reps', loadType: 'kg', targetLoad: null,
          targetPct: null, loadNote: '', targetRpe: 9.5, restSec: 180,
          isRamp: true, setsAreOptional: true, pairedWith: null,
        }],
      })),
    });
  }
  write('athlete-a/maxes.json', { 'back-squat': { threeRm: 70, e1rm: 75.6, loadType: 'kg', testedWeek: 1 } });
  return root;
}

let server;
let dataRoot;

test.before(async () => {
  dataRoot = seedDataRoot();
  server = spawn(process.execPath, [path.join(__dirname, 'server.js')], {
    env: { ...process.env, API_SECRET: SECRET, SKILLS_PORT: String(PORT), GYM_DATA_ROOT: dataRoot, GYM_ASSESSMENT_DISABLED: '1' },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  const deadline = Date.now() + 20000;
  for (;;) {
    try {
      const res = await fetch(`${BASE}/api/status`, { headers: { Authorization: `Bearer ${SECRET}` } });
      if (res.ok) return;
    } catch { /* not up yet */ }
    if (Date.now() > deadline) throw new Error('server did not start');
    await new Promise((r) => setTimeout(r, 250));
  }
});

test.after(() => { if (server) server.kill(); });

const get = (url) => fetch(`${BASE}${url}`, { headers: { Authorization: `Bearer ${SECRET}` } });
const put = (url, body) => fetch(`${BASE}${url}`, {
  method: 'PUT',
  headers: { Authorization: `Bearer ${SECRET}`, 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

test('gym routes require the bearer token', async () => {
  const res = await fetch(`${BASE}/api/gym/profiles`);
  assert.equal(res.status, 401);
});

test('profiles lists the seeded profile as enabled and on week 1', async () => {
  const body = await (await get('/api/gym/profiles')).json();
  assert.equal(body.enabled, true);
  assert.equal(body.profiles.length, 1);
  assert.equal(body.profiles[0].id, 'athlete-a');
  assert.ok(body.profiles[0].currentWeek >= 1);
});

test('week returns three days with log status', async () => {
  const body = await (await get('/api/gym/week/1?profile=athlete-a')).json();
  assert.equal(body.week, 1);
  assert.equal(body.days.length, 3);
  assert.equal(body.days[0].logStatus, 'not_started');
  assert.deepEqual(body.bounds, { start: '2026-09-07', end: '2026-09-13' });
});

test('week rejects a missing or unknown profile', async () => {
  assert.equal((await get('/api/gym/week/1')).status, 400);
  const res = await get('/api/gym/week/1?profile=stan');
  assert.equal(res.status, 400);
  assert.equal((await res.json()).code, 'gym_profile_required');
});

test('week rejects an out-of-range week', async () => {
  const res = await get('/api/gym/week/99?profile=athlete-a');
  assert.equal(res.status, 404);
  assert.equal((await res.json()).code, 'gym_week_not_found');
});

test('session returns prescription plus an empty log', async () => {
  const body = await (await get('/api/gym/session/1/1?profile=athlete-a')).json();
  assert.equal(body.day.title, 'Day 1');
  assert.equal(body.log.status, 'in_progress');
  assert.deepEqual(body.log.entries, []);
});

test('put saves a partial log and reads back identical', async () => {
  const entries = [{ itemId: 'a-back-squat', set: 1, load: 42.5, loadType: 'kg', reps: 3, rpe: 7, note: 'ok' }];
  const saved = await (await put('/api/gym/session/1/1?profile=athlete-a', { entries, dayNotes: 'slept 7h' })).json();
  assert.equal(saved.entries.length, 1);
  const reread = await (await get('/api/gym/session/1/1?profile=athlete-a')).json();
  assert.deepEqual(reread.log.entries, entries);
  assert.equal(reread.log.dayNotes, 'slept 7h');
});

test('put rejects an entry that is not in the day', async () => {
  const res = await put('/api/gym/session/1/2?profile=athlete-a', {
    entries: [{ itemId: 'nope', set: 1, load: 10, loadType: 'kg', reps: 3, rpe: 7, note: '' }],
  });
  assert.equal(res.status, 400);
  assert.equal((await res.json()).code, 'gym_invalid_entry');
});

test('exercises returns the library', async () => {
  const body = await (await get('/api/gym/exercises?profile=athlete-a')).json();
  assert.equal(body['back-squat'].name, 'Back squat');
});

test('exercises rejects a missing or unknown profile like every other gym route', async () => {
  const missing = await get('/api/gym/exercises');
  assert.equal(missing.status, 400);
  assert.equal((await missing.json()).code, 'gym_profile_required');
  const unknown = await get('/api/gym/exercises?profile=stan');
  assert.equal(unknown.status, 400);
  assert.equal((await unknown.json()).code, 'gym_profile_required');
});

test('stats reflects the saved partial session', async () => {
  const body = await (await get('/api/gym/stats?profile=athlete-a')).json();
  const week1 = body.weeks.find((w) => w.week === 1);
  assert.equal(week1.sessionsCompleted, 0);
  assert.equal(week1.tonnage, 128);        // 42.5 × 3, rounded
});

test('assessments is an empty list before any run', async () => {
  const body = await (await get('/api/gym/assessments?profile=athlete-a')).json();
  assert.deepEqual(body.assessments, []);
});

test('finish saves the log even when the gym-cyclist skill is absent', async () => {
  await put('/api/gym/session/2/1?profile=athlete-a', {
    entries: [{ itemId: 'a-back-squat', set: 1, load: 55, loadType: 'kg', reps: 3, rpe: 8, note: '' }],
  });
  const res = await fetch(`${BASE}/api/gym/session/2/1/finish?profile=athlete-a`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${SECRET}`, 'Content-Type': 'application/json' },
    body: '{}',
  });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.log.status, 'complete');
  assert.equal(body.maxes['back-squat'].threeRm, 55);
  // Unconditional on purpose. The spawned server runs with GYM_ASSESSMENT_DISABLED,
  // so no model call can ever be made from a test run, whether or not the skill
  // is installed on this machine.
  assert.equal(body.jobId, null);
  assert.match(body.assessmentSkipped, /GYM_ASSESSMENT_DISABLED/);
});

test('reopen refuses a session that was never logged', async () => {
  const res = await fetch(`${BASE}/api/gym/session/4/2/reopen?profile=athlete-a`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${SECRET}`, 'Content-Type': 'application/json' },
    body: '{}',
  });
  assert.equal(res.status, 404);
  assert.equal((await res.json()).code, 'gym_session_not_found');
});

test('a finished session can be reopened and edited again over HTTP', async () => {
  const entries = [{ itemId: 'a-back-squat', set: 1, load: 70, loadType: 'kg', reps: 3, rpe: 9, note: '' }];
  await put('/api/gym/session/3/1?profile=athlete-a', { entries });
  const finished = await (await fetch(`${BASE}/api/gym/session/3/1/finish?profile=athlete-a`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${SECRET}`, 'Content-Type': 'application/json' },
    body: '{}',
  })).json();
  assert.equal(finished.log.status, 'complete');

  // A finished session refuses edits until it is reopened.
  assert.equal((await put('/api/gym/session/3/1?profile=athlete-a', { dayNotes: 'x' })).status, 409);

  const reopened = await fetch(`${BASE}/api/gym/session/3/1/reopen?profile=athlete-a`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${SECRET}`, 'Content-Type': 'application/json' },
    body: '{}',
  });
  assert.equal(reopened.status, 200);
  assert.equal((await reopened.json()).status, 'in_progress');
  assert.equal((await put('/api/gym/session/3/1?profile=athlete-a', { dayNotes: 'corrected' })).status, 200);
});

test('assessments come back newest first once they exist', async () => {
  const dir = path.join(dataRoot, 'athlete-a', 'assessments');
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'W1D1.md'), '# W1 D1\n\nBaseline.', 'utf8');
  fs.writeFileSync(path.join(dir, 'W2D1.md'), '# W2 D1\n\nHeavier.', 'utf8');
  const body = await (await get('/api/gym/assessments?profile=athlete-a')).json();
  assert.deepEqual(body.assessments.map((a) => `${a.week}-${a.day}`), ['2-1', '1-1']);
  assert.match(body.assessments[1].body, /Baseline/);
});

test('finish stores the calendar date the phone sends', async () => {
  // Yesterday on this machine's calendar: inside the store's one-day window, and
  // not the date the server would fall back to, so a pass proves the hint was
  // used. The spawned server inherits this process's timezone.
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  const performedOn = localDateString(yesterday);

  await put('/api/gym/session/5/1?profile=athlete-a', {
    entries: [{ itemId: 'a-back-squat', set: 1, load: 60, loadType: 'kg', reps: 3, rpe: 8, note: '' }],
  });
  const res = await fetch(`${BASE}/api/gym/session/5/1/finish?profile=athlete-a`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${SECRET}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ performedOn }),
  });
  assert.equal(res.status, 200);
  assert.equal((await res.json()).log.performedOn, performedOn);
  const reread = await (await get('/api/gym/session/5/1?profile=athlete-a')).json();
  assert.equal(reread.log.performedOn, performedOn);
});
