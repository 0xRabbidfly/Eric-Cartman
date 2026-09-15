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
    profiles: [
      { id: 'athlete-a', name: 'Athlete A', startDate: '2026-09-07' },
      { id: 'athlete-b', name: 'Athlete B', startDate: '2026-09-07' },
    ],
  });
  write('exercises.json', { 'back-squat': { key: 'back-squat', name: 'Back squat', video: 'https://v' } });
  for (const profile of ['athlete-a', 'athlete-b']) {
    for (let n = 1; n <= 12; n += 1) {
      write(`${profile}/weeks/W${n}.json`, {
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
    write(`${profile}/maxes.json`, { 'back-squat': { threeRm: 70, e1rm: 75.6, loadType: 'kg', testedWeek: 1 } });
  }

  // Sessions are done in order and the server refuses to write past the next
  // one. athlete-a starts untouched, for the tests that begin at W1 D1.
  // athlete-b arrives with earlier sessions already finished, so the finish
  // and reopen tests can work on W2 D1, W3 D1 and W5 D1, each of which is the
  // next session by the time its test runs.
  const seededDone = [[1, 1], [1, 2], [1, 3], [2, 2], [2, 3], [3, 2], [3, 3], [4, 1], [4, 2], [4, 3]];
  for (const [week, day] of seededDone) {
    const performedOn = new Date(Date.UTC(2026, 8, 7 + (week - 1) * 7 + (day - 1) * 2)).toISOString().slice(0, 10);
    write(`athlete-b/logs/W${week}D${day}.json`, {
      profileId: 'athlete-b', week, day, status: 'complete', performedOn,
      startedAt: `${performedOn}T17:00:00Z`, completedAt: `${performedOn}T18:00:00Z`,
      entries: [{ itemId: 'a-back-squat', set: 1, load: 50, loadType: 'kg', reps: 5, rpe: 7, note: '' }],
      dayNotes: '',
    });
  }
  return root;
}

let server;
let dataRoot;

test.before(async () => {
  dataRoot = seedDataRoot();
  server = spawn(process.execPath, [path.join(__dirname, 'server.js')], {
    env: { ...process.env, API_SECRET: SECRET, SKILLS_PORT: String(PORT), GYM_DATA_ROOT: dataRoot, GYM_LIBRARY_PATH: path.join(dataRoot, 'exercises.json'), GYM_ASSESSMENT_DISABLED: '1' },
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

test('profiles reports the app-wide weight unit, kg when none is set', async () => {
  const body = await (await get('/api/gym/profiles')).json();
  assert.equal(body.units, 'kg');
});

test('gym routes require the bearer token', async () => {
  const res = await fetch(`${BASE}/api/gym/profiles`);
  assert.equal(res.status, 401);
});

test('profiles places each athlete by the sessions they have done, not the calendar', async () => {
  const body = await (await get('/api/gym/profiles')).json();
  assert.equal(body.enabled, true);
  assert.deepEqual(body.profiles.map((p) => p.id), ['athlete-a', 'athlete-b']);
  const [a, b] = body.profiles;
  assert.equal(a.currentWeek, 1);
  assert.deepEqual(a.nextSession, { week: 1, day: 1 });
  assert.equal(a.sessionsDone, 0);
  assert.equal(b.currentWeek, 2);
  assert.deepEqual(b.nextSession, { week: 2, day: 1 });
  assert.equal(b.sessionsDone, 10);
  for (const p of body.profiles) {
    // Neither fixture profile names a program, so both read as the original one.
    assert.equal(p.program, 'cycling');
    assert.ok(['behind', 'onPlan', 'ahead'].includes(p.pace.status));
    assert.equal(typeof p.pace.gap, 'number');
    assert.equal('delta' in p.pace, false);
  }
});

test('week returns three days with log status, the next one up and the rest locked', async () => {
  const body = await (await get('/api/gym/week/1?profile=athlete-a')).json();
  assert.equal(body.week, 1);
  assert.equal(body.days.length, 3);
  assert.equal(body.days[0].logStatus, 'not_started');
  assert.equal(body.bounds, undefined);
  assert.equal(body.span, null);
  assert.deepEqual(body.days.map((d) => d.upNext), [true, false, false]);
  assert.deepEqual(body.days.map((d) => d.locked), [false, true, true]);
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

test('a PUT past the next session is refused with 409 and writes nothing', async () => {
  const entries = [{ itemId: 'a-back-squat', set: 1, load: 50, loadType: 'kg', reps: 3, rpe: 7, note: '' }];
  const res = await put('/api/gym/session/1/3?profile=athlete-a', { entries });
  assert.equal(res.status, 409);
  assert.equal((await res.json()).code, 'gym_session_out_of_sequence');
  // Still readable, so the app can show the prescription read-only.
  const locked = await get('/api/gym/session/1/3?profile=athlete-a');
  assert.equal(locked.status, 200);
  const body = await locked.json();
  assert.equal(body.locked, true);
  assert.equal(body.upNext, false);
  assert.deepEqual(body.log.entries, []);
});

test('finishing a session past the next one is refused with 409', async () => {
  // W1 D1 is saved but not finished, so W1 D2 is still locked.
  const res = await fetch(`${BASE}/api/gym/session/1/2/finish?profile=athlete-a`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${SECRET}`, 'Content-Type': 'application/json' },
    body: '{}',
  });
  assert.equal(res.status, 409);
  assert.equal((await res.json()).code, 'gym_session_out_of_sequence');
  const reread = await (await get('/api/gym/session/1/2?profile=athlete-a')).json();
  assert.equal(reread.log.status, 'in_progress');
  assert.equal(reread.log.performedOn, null);
});

test('the next session still saves while later ones are locked', async () => {
  const res = await put('/api/gym/session/1/1?profile=athlete-a', { dayNotes: 'slept 7h, easy spin' });
  assert.equal(res.status, 200);
  const reread = await (await get('/api/gym/session/1/1?profile=athlete-a')).json();
  assert.equal(reread.upNext, true);
  assert.equal(reread.log.dayNotes, 'slept 7h, easy spin');
});

test('put rejects an entry that is not in the day', async () => {
  // athlete-b's next session, so the sequence check passes and validation answers.
  const res = await put('/api/gym/session/2/1?profile=athlete-b', {
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
  assert.equal(body.pace.sessionsDone, 0);
  assert.equal(body.pace.projectedFinish, null);
  assert.equal(body.pace.plannedFinish, '2026-11-30');
});

test('assessments is an empty list before any run', async () => {
  const body = await (await get('/api/gym/assessments?profile=athlete-a')).json();
  assert.deepEqual(body.assessments, []);
});

test('finish saves the log even when the gym-cyclist skill is absent', async () => {
  const saved = await put('/api/gym/session/2/1?profile=athlete-b', {
    entries: [{ itemId: 'a-back-squat', set: 1, load: 55, loadType: 'kg', reps: 3, rpe: 8, note: '' }],
  });
  assert.equal(saved.status, 200);
  const res = await fetch(`${BASE}/api/gym/session/2/1/finish?profile=athlete-b`, {
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
  assert.equal((await put('/api/gym/session/3/1?profile=athlete-b', { entries })).status, 200);
  const finished = await (await fetch(`${BASE}/api/gym/session/3/1/finish?profile=athlete-b`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${SECRET}`, 'Content-Type': 'application/json' },
    body: '{}',
  })).json();
  assert.equal(finished.log.status, 'complete');

  // A finished session refuses edits until it is reopened.
  const refused = await put('/api/gym/session/3/1?profile=athlete-b', { dayNotes: 'x' });
  assert.equal(refused.status, 409);
  assert.equal((await refused.json()).code, 'gym_session_complete');

  const reopened = await fetch(`${BASE}/api/gym/session/3/1/reopen?profile=athlete-b`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${SECRET}`, 'Content-Type': 'application/json' },
    body: '{}',
  });
  assert.equal(reopened.status, 200);
  assert.equal((await reopened.json()).status, 'in_progress');
  assert.equal((await put('/api/gym/session/3/1?profile=athlete-b', { dayNotes: 'corrected' })).status, 200);
  // Reopening did not send the athlete back: W4 is seeded done, so W5 D1 is next.
  const profiles = await (await get('/api/gym/profiles')).json();
  assert.deepEqual(profiles.profiles[1].nextSession, { week: 5, day: 1 });
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

  const saved = await put('/api/gym/session/5/1?profile=athlete-b', {
    entries: [{ itemId: 'a-back-squat', set: 1, load: 60, loadType: 'kg', reps: 3, rpe: 8, note: '' }],
  });
  assert.equal(saved.status, 200);
  const res = await fetch(`${BASE}/api/gym/session/5/1/finish?profile=athlete-b`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${SECRET}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ performedOn }),
  });
  assert.equal(res.status, 200);
  assert.equal((await res.json()).log.performedOn, performedOn);
  const reread = await (await get('/api/gym/session/5/1?profile=athlete-b')).json();
  assert.equal(reread.log.performedOn, performedOn);
});
