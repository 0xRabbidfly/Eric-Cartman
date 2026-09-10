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

test('estimateOneRm matches the Python seed helper', () => {
  const store = createGymStore(fixture());
  assert.equal(store.estimateOneRm(70), 75.6);
  assert.equal(store.estimateOneRm(80), 86.4);
  assert.equal(store.estimateOneRm(50), 54.0);
  assert.equal(store.estimateOneRm(77.5), 83.7);
});

test('saveSession creates a log and stamps startedAt once', () => {
  const store = createGymStore(fixture());
  const first = store.saveSession('athlete-b', 1, 2, {
    entries: [{ itemId: 'a-back-squat', set: 1, load: 30, loadType: 'kg', reps: 3, rpe: 5, note: '' }],
  });
  assert.equal(first.status, 'in_progress');
  assert.ok(first.startedAt);
  const second = store.saveSession('athlete-b', 1, 2, { dayNotes: 'felt good' });
  assert.equal(second.startedAt, first.startedAt);
  assert.equal(second.dayNotes, 'felt good');
});

test('saveSession replaces entries wholesale rather than merging them', () => {
  const store = createGymStore(fixture());
  store.saveSession('athlete-b', 1, 2, {
    entries: [{ itemId: 'a-back-squat', set: 1, load: 30, loadType: 'kg', reps: 3, rpe: 5, note: '' },
              { itemId: 'a-back-squat', set: 2, load: 40, loadType: 'kg', reps: 3, rpe: 6, note: '' }],
  });
  const after = store.saveSession('athlete-b', 1, 2, {
    entries: [{ itemId: 'a-back-squat', set: 1, load: 32.5, loadType: 'kg', reps: 3, rpe: 5, note: '' }],
  });
  assert.equal(after.entries.length, 1);
  assert.equal(after.entries[0].load, 32.5);
});

test('saveSession round-trips through the filesystem', () => {
  const root = fixture();
  createGymStore(root).saveSession('athlete-b', 1, 3, { dayNotes: 'slept badly' });
  assert.equal(createGymStore(root).getSession('athlete-b', 1, 3).log.dayNotes, 'slept badly');
});

test('saveSession rejects an entry whose itemId is not in that day', () => {
  const store = createGymStore(fixture());
  expectCode(() => store.saveSession('athlete-b', 1, 2, {
    entries: [{ itemId: 'z-nope', set: 1, load: 30, loadType: 'kg', reps: 3, rpe: 5, note: '' }],
  }), 'gym_invalid_entry');
});

test('saveSession refuses to touch a finished session', () => {
  const store = createGymStore(fixture());
  expectCode(() => store.saveSession('athlete-a', 1, 1, { dayNotes: 'x' }), 'gym_session_complete');
});

test('finishSession marks the log complete and dates it today', () => {
  const store = createGymStore(fixture());
  store.saveSession('athlete-b', 1, 2, {
    entries: [{ itemId: 'a-back-squat', set: 1, load: 60, loadType: 'kg', reps: 3, rpe: 9, note: '' }],
  });
  const { log } = store.finishSession('athlete-b', 1, 2, new Date('2026-09-11T19:00:00Z'));
  assert.equal(log.status, 'complete');
  assert.equal(log.performedOn, '2026-09-11');
  assert.ok(log.completedAt.startsWith('2026-09-11T'));
});

test('finishSession takes the heaviest clean triple as the new 3RM', () => {
  const store = createGymStore(fixture());
  store.saveSession('athlete-b', 1, 2, {
    entries: [
      { itemId: 'a-back-squat', set: 1, load: 50, loadType: 'kg', reps: 3, rpe: 7, note: '' },
      { itemId: 'a-back-squat', set: 2, load: 60, loadType: 'kg', reps: 3, rpe: 9, note: '' },
    ],
  });
  const { maxes } = store.finishSession('athlete-b', 1, 2, new Date('2026-09-11T19:00:00Z'));
  assert.equal(maxes['back-squat'].threeRm, 60);
  assert.equal(maxes['back-squat'].e1rm, 64.8);
  assert.equal(maxes['back-squat'].testedWeek, 1);
  assert.equal(maxes['back-squat'].testedOn, '2026-09-11');
});

test('a set above RPE 9.5 or short on reps is not a clean triple', () => {
  const store = createGymStore(fixture());
  store.saveSession('athlete-b', 1, 2, {
    entries: [
      { itemId: 'a-back-squat', set: 1, load: 50, loadType: 'kg', reps: 3, rpe: 8, note: '' },
      { itemId: 'a-back-squat', set: 2, load: 60, loadType: 'kg', reps: 2, rpe: 10, note: 'failed' },
      { itemId: 'a-back-squat', set: 3, load: 62.5, loadType: 'kg', reps: 3, rpe: 10, note: 'grind' },
    ],
  });
  const { maxes } = store.finishSession('athlete-b', 1, 2, new Date('2026-09-11T19:00:00Z'));
  assert.equal(maxes['back-squat'].threeRm, 50);
});

test('finishSession leaves maxes alone when the day has no ramp', () => {
  const root = fixture();
  const noRamp = JSON.parse(fs.readFileSync(path.join(root, 'athlete-b', 'weeks', 'W2.json'), 'utf8'));
  noRamp.days.forEach((d) => d.items.forEach((i) => { i.isRamp = false; }));
  fs.writeFileSync(path.join(root, 'athlete-b', 'weeks', 'W2.json'), JSON.stringify(noRamp), 'utf8');
  const store = createGymStore(root);
  store.saveSession('athlete-b', 2, 1, {
    entries: [{ itemId: 'a-back-squat', set: 1, load: 200, loadType: 'kg', reps: 3, rpe: 5, note: '' }],
  });
  const { maxes } = store.finishSession('athlete-b', 2, 1, new Date('2026-09-18T19:00:00Z'));
  assert.equal(maxes['back-squat'].threeRm, 70);
});

test('finishSession refuses an empty log', () => {
  const store = createGymStore(fixture());
  expectCode(() => store.finishSession('athlete-b', 1, 3), 'gym_session_empty');
});

test('finishSession is idempotent-safe: a finished session cannot be finished twice', () => {
  const store = createGymStore(fixture());
  expectCode(() => store.finishSession('athlete-a', 1, 1), 'gym_session_complete');
});

test('finishSession records a baseline result that has no load', () => {
  const root = fixture();
  const week = JSON.parse(fs.readFileSync(path.join(root, 'athlete-b', 'weeks', 'W1.json'), 'utf8'));
  week.days[2].items = [{
    id: 'e-front-plank', block: 'E', exerciseKey: 'front-plank', label: 'Front plank — baseline',
    sets: 1, reps: 120, resultType: 'seconds', loadType: 'bodyweight', targetLoad: null,
    targetPct: null, loadNote: '', targetRpe: null, restSec: 0,
    isRamp: false, setsAreOptional: false, pairedWith: null,
  }];
  fs.writeFileSync(path.join(root, 'athlete-b', 'weeks', 'W1.json'), JSON.stringify(week), 'utf8');
  const store = createGymStore(root);
  store.saveSession('athlete-b', 1, 3, {
    entries: [
      // Best first, so a buggy "last wins" reduce cannot pass this test.
      { itemId: 'e-front-plank', set: 1, load: null, loadType: 'bodyweight', reps: 95, rpe: null, note: '' },
      { itemId: 'e-front-plank', set: 2, load: null, loadType: 'bodyweight', reps: 78, rpe: null, note: '' },
    ],
  });
  const { maxes } = store.finishSession('athlete-b', 1, 3, new Date('2026-09-12T19:00:00Z'));
  assert.equal(maxes['front-plank'].seconds, 95);
  assert.equal(maxes['front-plank'].testedOn, '2026-09-12');
  assert.equal(maxes['front-plank'].threeRm, undefined);
});

test('reopenSession makes a finished session editable again', () => {
  const store = createGymStore(fixture());
  const reopened = store.reopenSession('athlete-a', 1, 1);
  assert.equal(reopened.status, 'in_progress');
  assert.equal(reopened.completedAt, null);
  assert.equal(reopened.entries.length, 1);
  const saved = store.saveSession('athlete-a', 1, 1, { dayNotes: 'corrected the squat load' });
  assert.equal(saved.dayNotes, 'corrected the squat load');
});

test('reopenSession refuses a session that was never logged', () => {
  const store = createGymStore(fixture());
  expectCode(() => store.reopenSession('athlete-b', 4, 2), 'gym_session_not_found');
});

test('weekBounds rejects an unusable startDate rather than throwing a RangeError', () => {
  const store = createGymStore(fixture());
  assert.throws(() => store.weekBounds('not-a-date', 1), (err) => err.code === 'gym_data_corrupt');
});

test('a ramp set logged with no load is ignored when picking the max', () => {
  const store = createGymStore(fixture());
  store.saveSession('athlete-b', 1, 2, {
    entries: [
      { itemId: 'a-back-squat', set: 1, load: 55, loadType: 'kg', reps: 3, rpe: 8, note: '' },
      { itemId: 'a-back-squat', set: 2, load: null, loadType: 'kg', reps: 3, rpe: 9, note: 'forgot to write it down' },
    ],
  });
  const { maxes } = store.finishSession('athlete-b', 1, 2, new Date('2026-09-11T19:00:00Z'));
  assert.equal(maxes['back-squat'].threeRm, 55);
});

test('recomputing a max leaves a sibling exercise and its injury flags untouched', () => {
  const root = fixture();
  const store = createGymStore(root);
  const bench = {
    threeRm: 80, loadType: 'kg_total_pair', e1rm: 86.4, testedWeek: 1, testedOn: '2026-09-09',
    watch: true, note: 'Shoulder discomfort on the back-off set; swap if it recurs.',
  };
  store._writeJson(path.join(root, 'athlete-b', 'maxes.json'), {
    'back-squat': { threeRm: 70, loadType: 'kg', e1rm: 75.6, testedWeek: 1, watch: false, note: '' },
    'dumbbell-bench-press': bench,
  });
  store.saveSession('athlete-b', 1, 2, {
    entries: [{ itemId: 'a-back-squat', set: 1, load: 65, loadType: 'kg', reps: 3, rpe: 8, note: '' }],
  });
  const { maxes } = store.finishSession('athlete-b', 1, 2, new Date('2026-09-11T19:00:00Z'));
  assert.equal(maxes['back-squat'].threeRm, 65);
  assert.equal(maxes['back-squat'].watch, false);
  assert.deepEqual(maxes['dumbbell-bench-press'], bench);
});

test('saveSession rejects a malformed entries payload with a coded error', () => {
  const store = createGymStore(fixture());
  expectCode(() => store.saveSession('athlete-b', 1, 2, { entries: null }), 'gym_invalid_entry');
  expectCode(() => store.saveSession('athlete-b', 1, 3, { entries: 'nope' }), 'gym_invalid_entry');
});
