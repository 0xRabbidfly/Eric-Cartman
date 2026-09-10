const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');

const { createGymStore } = require('./gym-store');

function fixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'gym-'));
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
  write('exercises.json', {
    'back-squat': { key: 'back-squat', name: 'Back squat', group: 'Lower', why: 'w', how: 'h', cues: 'c', video: 'https://v' },
  });
  const week = (n) => ({
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
  for (const profile of ['athlete-a', 'athlete-b']) {
    for (let n = 1; n <= 12; n += 1) write(`${profile}/weeks/W${n}.json`, week(n));
    write(`${profile}/maxes.json`, { 'back-squat': { threeRm: 70, e1rm: 75.6, loadType: 'kg', testedWeek: 1 } });
  }
  write('athlete-a/logs/W1D1.json', {
    profileId: 'athlete-a', week: 1, day: 1, status: 'complete', performedOn: '2026-09-09',
    startedAt: '2026-09-09T17:05:00Z', completedAt: '2026-09-09T18:02:00Z',
    entries: [{ itemId: 'a-back-squat', set: 1, load: 40, loadType: 'kg', reps: 3, rpe: 7, note: '' }],
    dayNotes: 'baseline',
  });
  return root;
}

function expectCode(fn, code) {
  assert.throws(fn, (err) => err.code === code, `expected error code ${code}`);
}

test('isEnabled is false when the data root does not exist', () => {
  const store = createGymStore(path.join(os.tmpdir(), 'gym-does-not-exist'));
  assert.equal(store.isEnabled(), false);
});

test('every read throws gym_not_configured when disabled', () => {
  const store = createGymStore(path.join(os.tmpdir(), 'gym-does-not-exist'));
  expectCode(() => store.listProfiles(), 'gym_not_configured');
  expectCode(() => store.getWeek('athlete-a', 1), 'gym_not_configured');
});

test('listProfiles returns both profiles with a current week', () => {
  const store = createGymStore(fixture());
  const profiles = store.listProfiles(new Date('2026-09-09T12:00:00Z'));
  assert.deepEqual(profiles.map((p) => p.id), ['athlete-a', 'athlete-b']);
  assert.equal(profiles[0].name, 'Athlete A');
  assert.equal(profiles[0].currentWeek, 1);
});

test('currentWeekFor counts calendar weeks from the start Monday', () => {
  const store = createGymStore(fixture());
  const at = (iso) => store.currentWeekFor('2026-09-07', new Date(iso));
  assert.equal(at('2026-09-07T00:00:00Z'), 1);
  assert.equal(at('2026-09-09T23:00:00Z'), 1);
  assert.equal(at('2026-09-13T23:59:00Z'), 1);
  assert.equal(at('2026-09-14T00:00:00Z'), 2);
  assert.equal(at('2026-10-05T00:00:00Z'), 5);
});

test('currentWeekFor clamps before the start and past the program', () => {
  const store = createGymStore(fixture());
  assert.equal(store.currentWeekFor('2026-09-07', new Date('2026-08-01T00:00:00Z')), 1);
  assert.equal(store.currentWeekFor('2026-09-07', new Date('2027-01-01T00:00:00Z')), 13);
});

test('weekBounds gives the Monday and Sunday of that week', () => {
  const store = createGymStore(fixture());
  assert.deepEqual(store.weekBounds('2026-09-07', 1), { start: '2026-09-07', end: '2026-09-13' });
  assert.deepEqual(store.weekBounds('2026-09-07', 3), { start: '2026-09-21', end: '2026-09-27' });
});

test('getWeek annotates each day with its log status', () => {
  const store = createGymStore(fixture());
  const week = store.getWeek('athlete-a', 1);
  assert.equal(week.week, 1);
  assert.deepEqual(week.days.map((d) => d.logStatus), ['complete', 'not_started', 'not_started']);
  assert.equal(week.days[0].performedOn, '2026-09-09');
  assert.equal(week.days[0].loggedSets, 1);
  assert.deepEqual(week.bounds, { start: '2026-09-07', end: '2026-09-13' });
});

test('getWeek reports a profile with no logs as untouched', () => {
  const store = createGymStore(fixture());
  const week = store.getWeek('athlete-b', 1);
  assert.deepEqual(week.days.map((d) => d.logStatus), ['not_started', 'not_started', 'not_started']);
  assert.equal(week.days[0].performedOn, null);
});

test('getWeek rejects an unknown profile and an out-of-range week', () => {
  const store = createGymStore(fixture());
  expectCode(() => store.getWeek('stan', 1), 'gym_profile_required');
  expectCode(() => store.getWeek('athlete-a', 0), 'gym_week_not_found');
  expectCode(() => store.getWeek('athlete-a', 99), 'gym_week_not_found');
});

test('getSession merges the prescription with the saved log', () => {
  const store = createGymStore(fixture());
  const session = store.getSession('athlete-a', 1, 1);
  assert.equal(session.day.title, 'Day 1');
  assert.equal(session.log.status, 'complete');
  assert.equal(session.log.entries.length, 1);
  assert.equal(session.week.blockLabel, 'Test week');
});

test('getSession returns an empty in-progress log when nothing is saved', () => {
  const store = createGymStore(fixture());
  const session = store.getSession('athlete-b', 1, 2);
  assert.equal(session.log.status, 'in_progress');
  assert.deepEqual(session.log.entries, []);
  assert.equal(session.log.dayNotes, '');
});

test('getSession rejects a day outside 1 to 3', () => {
  const store = createGymStore(fixture());
  expectCode(() => store.getSession('athlete-a', 1, 4), 'gym_session_not_found');
});

test('getExercises returns the library', () => {
  const store = createGymStore(fixture());
  assert.equal(store.getExercises()['back-squat'].name, 'Back squat');
});

test('corrupt JSON reports the file rather than throwing a parse error', () => {
  const root = fixture();
  fs.writeFileSync(path.join(root, 'athlete-a', 'weeks', 'W2.json'), '{ not json', 'utf8');
  const store = createGymStore(root);
  assert.throws(() => store.getWeek('athlete-a', 2), (err) => {
    assert.equal(err.code, 'gym_data_corrupt');
    assert.match(err.message, /W2\.json/);
    return true;
  });
});

test('a week file that is valid JSON but has no days array is reported as corrupt', () => {
  const root = fixture();
  fs.writeFileSync(path.join(root, 'athlete-a', 'weeks', 'W3.json'), JSON.stringify({ week: 3 }), 'utf8');
  const store = createGymStore(root);
  assert.throws(() => store.getWeek('athlete-a', 3), (err) => {
    assert.equal(err.code, 'gym_data_corrupt');
    assert.match(err.message, /days array/);
    return true;
  });
});

test('a profiles file holding null is reported as corrupt, not a TypeError', () => {
  const root = fixture();
  fs.writeFileSync(path.join(root, 'profiles.json'), 'null', 'utf8');
  const store = createGymStore(root);
  assert.throws(() => store.listProfiles(), (err) => err.code === 'gym_data_corrupt');
});

test('an unusable startDate throws a coded error instead of returning NaN', () => {
  const store = createGymStore(fixture());
  assert.throws(() => store.currentWeekFor('not-a-date', new Date('2026-09-09T00:00:00Z')),
    (err) => err.code === 'gym_data_corrupt');
});

test('a session file that is valid JSON but not an object is reported as corrupt', () => {
  const root = fixture();
  fs.writeFileSync(path.join(root, 'athlete-a', 'logs', 'W1D1.json'), '42', 'utf8');
  const store = createGymStore(root);
  assert.throws(() => store.getSession('athlete-a', 1, 1), (err) => err.code === 'gym_data_corrupt');
});
