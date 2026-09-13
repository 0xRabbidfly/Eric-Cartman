const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');

const { createGymStore, localDateString } = require('./gym-store');

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
  const profiles = store.listProfiles('2026-09-09');
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
    isRamp: false, isBaseline: true, setsAreOptional: false, pairedWith: null,
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
    watch: true, note: 'Watch note carried through recompute.',
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

test('getStats summarises each week that has any log', () => {
  const store = createGymStore(fixture());
  const stats = store.getStats('athlete-a');
  const week1 = stats.weeks.find((w) => w.week === 1);
  assert.equal(week1.sessionsCompleted, 1);
  assert.equal(week1.sessionsPlanned, 3);
  assert.equal(week1.tonnage, 120);          // 40 kg × 3 reps × 1 set
  assert.equal(week1.avgRpe, 7);
  assert.equal(week1.blockLabel, 'Test week');
});

test('getStats reports zero for weeks with no logs', () => {
  const store = createGymStore(fixture());
  const week2 = store.getStats('athlete-a').weeks.find((w) => w.week === 2);
  assert.equal(week2.sessionsCompleted, 0);
  assert.equal(week2.tonnage, 0);
  assert.equal(week2.avgRpe, null);
});

test('getStats excludes bodyweight and cable work from tonnage', () => {
  const store = createGymStore(fixture());
  store.saveSession('athlete-b', 1, 2, {
    entries: [
      { itemId: 'a-back-squat', set: 1, load: 50, loadType: 'kg', reps: 3, rpe: 7, note: '' },
      { itemId: 'a-back-squat', set: 2, load: 70, loadType: 'setting', reps: 10, rpe: 7, note: '' },
      { itemId: 'a-back-squat', set: 3, load: null, loadType: 'bodyweight', reps: 8, rpe: 7, note: '' },
    ],
  });
  store.finishSession('athlete-b', 1, 2, new Date('2026-09-11T19:00:00Z'));
  assert.equal(store.getStats('athlete-b').weeks.find((w) => w.week === 1).tonnage, 150);
});

test('getStats tracks the estimated 1RM trend per tested lift', () => {
  const store = createGymStore(fixture());
  const trend = store.getStats('athlete-a').maxTrend;
  assert.deepEqual(trend['back-squat'], [{ week: 1, e1rm: 75.6, threeRm: 70 }]);
});

test('getStats surfaces the jump and plank baselines', () => {
  const root = fixture();
  const store = createGymStore(root);
  const maxes = store._readJson(path.join(root, 'athlete-a', 'maxes.json'), {});
  maxes['standing-broad-jump'] = { cm: 210, testedWeek: 1 };
  maxes['front-plank'] = { seconds: 95, testedWeek: 1 };
  store._writeJson(path.join(root, 'athlete-a', 'maxes.json'), maxes);
  const baselines = createGymStore(root).getStats('athlete-a').baselines;
  assert.equal(baselines['standing-broad-jump'].cm, 210);
  assert.equal(baselines['front-plank'].seconds, 95);
});

test('writeAssessment then listAssessments round-trips newest first', () => {
  const store = createGymStore(fixture());
  store.writeAssessment('athlete-a', 1, 1, '# W1 D1\n\nSolid baseline.');
  store.writeAssessment('athlete-a', 1, 2, '# W1 D2\n\nGood.');
  store.writeAssessment('athlete-a', 2, 1, '# W2 D1\n\nHeavier.');
  const list = store.listAssessments('athlete-a');
  assert.deepEqual(list.map((a) => `${a.week}-${a.day}`), ['2-1', '1-2', '1-1']);
  assert.match(list[2].body, /Solid baseline/);
});

test('listAssessments is empty rather than throwing when none exist', () => {
  assert.deepEqual(createGymStore(fixture()).listAssessments('athlete-b'), []);
});

test('a ramp item whose every set has no load leaves that max untouched', () => {
  const root = fixture();
  const store = createGymStore(root);
  const before = store._readJson(path.join(root, 'athlete-b', 'maxes.json'), {});
  store.saveSession('athlete-b', 1, 2, {
    entries: [
      { itemId: 'a-back-squat', set: 1, load: null, loadType: 'kg', reps: 3, rpe: 8, note: '' },
      { itemId: 'a-back-squat', set: 2, load: null, loadType: 'kg', reps: 3, rpe: 9, note: '' },
    ],
  });
  const { maxes } = store.finishSession('athlete-b', 1, 2, new Date('2026-09-11T19:00:00Z'));
  assert.deepEqual(maxes['back-squat'], before['back-squat']);
});

test('getStats reports a corrupt week file with a coded error, not a TypeError', () => {
  const root = fixture();
  fs.writeFileSync(path.join(root, 'athlete-a', 'weeks', 'W4.json'), JSON.stringify({ week: 4 }), 'utf8');
  const store = createGymStore(root);
  assert.throws(() => store.getStats('athlete-a'), (err) => {
    assert.equal(err.code, 'gym_data_corrupt');
    assert.match(err.message, /W4\.json/);
    return true;
  });
});

test('maxTrend merges stored history with the current value, oldest week first', () => {
  const root = fixture();
  createGymStore(root)._writeJson(path.join(root, 'athlete-a', 'maxes.json'), {
    'back-squat': {
      threeRm: 80, loadType: 'kg', e1rm: 86.4, testedWeek: 9,
      history: [{ week: 5, e1rm: 81.0, threeRm: 75 }, { week: 1, e1rm: 75.6, threeRm: 70 }],
    },
    'trap-bar-deadlift': { threeRm: null, loadType: 'kg', e1rm: null },
  });
  const trend = createGymStore(root).getStats('athlete-a').maxTrend;
  assert.deepEqual(trend['back-squat'].map((p) => p.week), [1, 5, 9]);
  assert.equal(trend['back-squat'][2].threeRm, 80);
  // A lift that has never been tested is absent, not present with nulls.
  assert.equal(trend['trap-bar-deadlift'], undefined);
});

test('tonnage counts a dumbbell pair total once and ignores cable and bodyweight work', () => {
  const store = createGymStore(fixture());
  store.saveSession('athlete-b', 1, 2, {
    entries: [
      { itemId: 'a-back-squat', set: 1, load: 60, loadType: 'kg_total_pair', reps: 5, rpe: 8, note: '' },
      { itemId: 'a-back-squat', set: 2, load: 70, loadType: 'setting', reps: 10, rpe: null, note: '' },
      { itemId: 'a-back-squat', set: 3, load: null, loadType: 'bodyweight', reps: 12, rpe: 6, note: '' },
    ],
  });
  store.finishSession('athlete-b', 1, 2, new Date('2026-09-11T19:00:00Z'));
  const week1 = store.getStats('athlete-b').weeks.find((w) => w.week === 1);
  assert.equal(week1.tonnage, 300);   // 60 x 5, counted once; the setting and bodyweight rows add nothing
  assert.equal(week1.avgRpe, 7);      // (8 + 6) / 2 — the set with no RPE is skipped, not counted as zero
});

test('re-testing a lift archives the outgoing max onto history', () => {
  const root = fixture();
  const store = createGymStore(root);
  store._writeJson(path.join(root, 'athlete-b', 'maxes.json'), {
    'back-squat': { threeRm: 70, loadType: 'kg', e1rm: 75.6, testedWeek: 1, testedOn: '2026-09-09' },
  });
  store.saveSession('athlete-b', 5, 1, {
    entries: [{ itemId: 'a-back-squat', set: 1, load: 80, loadType: 'kg', reps: 3, rpe: 9, note: '' }],
  });
  const { maxes } = store.finishSession('athlete-b', 5, 1, new Date('2026-10-06T19:00:00Z'));
  assert.equal(maxes['back-squat'].threeRm, 80);
  assert.equal(maxes['back-squat'].testedWeek, 5);
  assert.deepEqual(maxes['back-squat'].history, [{ week: 1, threeRm: 70, e1rm: 75.6 }]);
});

test('the archived history is what getStats draws its trend from', () => {
  const root = fixture();
  const store = createGymStore(root);
  store._writeJson(path.join(root, 'athlete-b', 'maxes.json'), {
    'back-squat': { threeRm: 70, loadType: 'kg', e1rm: 75.6, testedWeek: 1, testedOn: '2026-09-09' },
  });
  store.saveSession('athlete-b', 5, 1, {
    entries: [{ itemId: 'a-back-squat', set: 1, load: 80, loadType: 'kg', reps: 3, rpe: 9, note: '' }],
  });
  store.finishSession('athlete-b', 5, 1, new Date('2026-10-06T19:00:00Z'));
  const trend = store.getStats('athlete-b').maxTrend['back-squat'];
  assert.deepEqual(trend.map((p) => p.week), [1, 5]);
  assert.deepEqual(trend.map((p) => p.threeRm), [70, 80]);
});

test('re-finishing the same week corrects it in place instead of duplicating history', () => {
  const root = fixture();
  const store = createGymStore(root);
  store._writeJson(path.join(root, 'athlete-b', 'maxes.json'), {
    'back-squat': { threeRm: 70, loadType: 'kg', e1rm: 75.6, testedWeek: 1, testedOn: '2026-09-09' },
  });
  store.saveSession('athlete-b', 5, 1, {
    entries: [{ itemId: 'a-back-squat', set: 1, load: 80, loadType: 'kg', reps: 3, rpe: 9, note: '' }],
  });
  store.finishSession('athlete-b', 5, 1, new Date('2026-10-06T19:00:00Z'));
  store.reopenSession('athlete-b', 5, 1);
  store.saveSession('athlete-b', 5, 1, {
    entries: [{ itemId: 'a-back-squat', set: 1, load: 82.5, loadType: 'kg', reps: 3, rpe: 9, note: '' }],
  });
  const { maxes } = store.finishSession('athlete-b', 5, 1, new Date('2026-10-06T20:00:00Z'));
  assert.equal(maxes['back-squat'].threeRm, 82.5);
  assert.deepEqual(maxes['back-squat'].history, [{ week: 1, threeRm: 70, e1rm: 75.6 }]);
});

test('a first-ever test archives nothing, and a baseline archives its own unit', () => {
  const root = fixture();
  const store = createGymStore(root);
  store._writeJson(path.join(root, 'athlete-b', 'maxes.json'), {
    'back-squat': { threeRm: null, loadType: 'kg', e1rm: null, testedWeek: null },
  });
  store.saveSession('athlete-b', 1, 1, {
    entries: [{ itemId: 'a-back-squat', set: 1, load: 60, loadType: 'kg', reps: 3, rpe: 8, note: '' }],
  });
  const first = store.finishSession('athlete-b', 1, 1, new Date('2026-09-09T19:00:00Z')).maxes;
  assert.deepEqual(first['back-squat'].history, []);

  const week = JSON.parse(fs.readFileSync(path.join(root, 'athlete-b', 'weeks', 'W9.json'), 'utf8'));
  week.days[0].items = [{
    id: 'a-standing-broad-jump', block: 'A', exerciseKey: 'standing-broad-jump',
    label: 'Standing broad jump', sets: 3, reps: 1, resultType: 'cm', loadType: 'bodyweight',
    targetLoad: null, targetPct: null, loadNote: '', targetRpe: null, restSec: 60,
    isRamp: false, isBaseline: true, setsAreOptional: false, pairedWith: null,
  }];
  fs.writeFileSync(path.join(root, 'athlete-b', 'weeks', 'W9.json'), JSON.stringify(week), 'utf8');
  const s2 = createGymStore(root);
  s2._writeJson(path.join(root, 'athlete-b', 'maxes.json'), {
    'standing-broad-jump': { cm: 205, testedWeek: 1, testedOn: '2026-09-11' },
  });
  s2.saveSession('athlete-b', 9, 1, {
    entries: [{ itemId: 'a-standing-broad-jump', set: 1, load: null, loadType: 'bodyweight', reps: 218, rpe: null, note: '' }],
  });
  const { maxes } = s2.finishSession('athlete-b', 9, 1, new Date('2026-11-03T19:00:00Z'));
  assert.equal(maxes['standing-broad-jump'].cm, 218);
  assert.deepEqual(maxes['standing-broad-jump'].history, [{ week: 1, cm: 205 }]);
});

test('a seconds item without the baseline flag is prescribed work, not a max', () => {
  const root = fixture();
  const week = JSON.parse(fs.readFileSync(path.join(root, 'athlete-b', 'weeks', 'W1.json'), 'utf8'));
  // Side plank is 2×30 s of prescribed accessory work. The unit says seconds,
  // the intent does not say baseline — so nothing about it belongs in maxes.json.
  week.days[2].items = [{
    id: 'd-side-plank', block: 'D', exerciseKey: 'side-plank', label: 'Side plank',
    sets: 2, reps: 30, resultType: 'seconds', loadType: 'bodyweight', targetLoad: null,
    targetPct: null, loadNote: 'Per side.', targetRpe: null, restSec: 30,
    isRamp: false, isBaseline: false, setsAreOptional: false, pairedWith: null,
  }];
  fs.writeFileSync(path.join(root, 'athlete-b', 'weeks', 'W1.json'), JSON.stringify(week), 'utf8');
  const store = createGymStore(root);
  store.saveSession('athlete-b', 1, 3, {
    entries: [{ itemId: 'd-side-plank', set: 1, load: null, loadType: 'bodyweight', reps: 45, rpe: null, note: '' }],
  });
  const { maxes } = store.finishSession('athlete-b', 1, 3, new Date('2026-09-12T19:00:00Z'));
  assert.equal(maxes['side-plank'], undefined);
});

test('re-finishing a corrected session keeps the date it was actually performed', () => {
  const store = createGymStore(fixture());
  store.saveSession('athlete-b', 1, 2, {
    entries: [{ itemId: 'a-back-squat', set: 1, load: 60, loadType: 'kg', reps: 3, rpe: 9, note: '' }],
  });
  const first = store.finishSession('athlete-b', 1, 2, new Date('2026-09-09T19:00:00Z'));
  assert.equal(first.log.performedOn, '2026-09-09');
  assert.equal(first.maxes['back-squat'].testedOn, '2026-09-09');

  // Two days later the transcribed load is corrected, or the assessment is retried.
  store.reopenSession('athlete-b', 1, 2);
  store.saveSession('athlete-b', 1, 2, {
    entries: [{ itemId: 'a-back-squat', set: 1, load: 62.5, loadType: 'kg', reps: 3, rpe: 9, note: 'read the paper properly' }],
  });
  const again = store.finishSession('athlete-b', 1, 2, new Date('2026-09-11T08:30:00Z'));
  assert.equal(again.log.performedOn, '2026-09-09');
  assert.equal(again.maxes['back-squat'].threeRm, 62.5);
  assert.equal(again.maxes['back-squat'].testedOn, '2026-09-09');
  // completedAt is the audit trail of when the record was last written, so it does move.
  assert.ok(again.log.completedAt.startsWith('2026-09-11T'));
});

test('tonnage ignores a distance carry and counts a per-side item on both sides', () => {
  const root = fixture();
  const week = JSON.parse(fs.readFileSync(path.join(root, 'athlete-b', 'weeks', 'W1.json'), 'utf8'));
  week.days[1].items = [
    {
      id: 'e-farmers-carry', block: 'E', exerciseKey: 'farmers-carry', label: "Farmer's carry",
      sets: 3, reps: 30, resultType: 'metres', loadType: 'kg_total_pair', targetLoad: null,
      targetPct: null, loadNote: 'Heavy.', targetRpe: 8, restSec: 60,
      isRamp: false, isBaseline: false, setsAreOptional: false, pairedWith: null,
    },
    {
      id: 'b-bulgarian-split-squat', block: 'B', exerciseKey: 'bulgarian-split-squat',
      label: 'Bulgarian split squat', sets: 2, reps: 8, resultType: 'reps_per_side',
      loadType: 'kg_total_pair', targetLoad: null, targetPct: null, loadNote: '',
      targetRpe: 7, restSec: 90, isRamp: false, isBaseline: false,
      setsAreOptional: false, pairedWith: null,
    },
  ];
  fs.writeFileSync(path.join(root, 'athlete-b', 'weeks', 'W1.json'), JSON.stringify(week), 'utf8');
  const store = createGymStore(root);
  store.saveSession('athlete-b', 1, 2, {
    entries: [
      // 60 kg carried 30 m is 1800 kg·m, and 0 kg lifted.
      { itemId: 'e-farmers-carry', set: 1, load: 60, loadType: 'kg_total_pair', reps: 30, rpe: 8, note: '' },
      // 8 per side against 50 kg is 16 reps, so 800 kg.
      { itemId: 'b-bulgarian-split-squat', set: 1, load: 50, loadType: 'kg_total_pair', reps: 8, rpe: 7, note: '' },
    ],
  });
  store.finishSession('athlete-b', 1, 2, new Date('2026-09-11T19:00:00Z'));
  assert.equal(store.getStats('athlete-b').weeks.find((w) => w.week === 1).tonnage, 800);
});

test('estimateOneRm rounds a half-way case up, the way gymlib.py does', () => {
  // 18.75 × 1.08 is exactly 20.25. Half-to-even would give 20.2 and disagree
  // with the Stats view, which shows whatever this function wrote.
  assert.equal(createGymStore(fixture()).estimateOneRm(18.75), 20.3);
});

/**
 * Week 1 tells an athlete who cannot do five strict pull-ups to log max clean
 * bodyweight reps instead of ramping. Until now that number had nowhere to go:
 * the ramp found no clean triple, recomputeMaxes wrote nothing, and the entry
 * sat at `threeRm: null` forever with no record of what the athlete could do.
 */
function pullUpFixture() {
  const root = fixture();
  // Every week, not just W1: the retest weeks run the same ramp, and the
  // archiving tests need a W1 test and a W5 retest of the same item.
  for (let n = 1; n <= 12; n += 1) {
    const file = path.join(root, 'athlete-b', 'weeks', `W${n}.json`);
    const week = JSON.parse(fs.readFileSync(file, 'utf8'));
    for (const day of week.days) {
      day.items.push({
        id: 'c-pull-up-weighted', block: 'C', exerciseKey: 'pull-up-weighted',
        label: 'Weighted pull-up — 3RM ramp', sets: 4, reps: 3, resultType: 'reps',
        loadType: 'bodyweight_plus_kg', targetLoad: null, targetPct: null,
        loadNote: 'If you cannot do 5 clean bodyweight pull-ups, log max clean reps instead.',
        targetRpe: 9.5, restSec: 120, isRamp: true, isBaseline: false,
        setsAreOptional: true, pairedWith: null,
      });
    }
    fs.writeFileSync(file, JSON.stringify(week), 'utf8');
  }
  return root;
}

/** A pull-up entry as week 1 leaves it when the ramp found no clean triple. */
function testedAtTwoBodyweightReps() {
  return {
    'pull-up-weighted': {
      threeRm: null, loadType: 'bodyweight_plus_kg', e1rm: null, bodyweightReps: 2,
      testedWeek: 1, testedOn: '2026-09-12', note: '', watch: false,
    },
  };
}

test('a pull-up ramp that clears three reps sets a 3RM and clears any bodyweightReps', () => {
  const root = pullUpFixture();
  const store = createGymStore(root);
  store._writeJson(path.join(root, 'athlete-b', 'maxes.json'), {
    'pull-up-weighted': {
      threeRm: null, loadType: 'bodyweight_plus_kg', e1rm: null,
      bodyweightReps: 2, testedWeek: null, testedOn: null, note: '', watch: false,
    },
  });
  store.saveSession('athlete-b', 1, 2, {
    entries: [
      { itemId: 'c-pull-up-weighted', set: 1, load: 0, loadType: 'bodyweight_plus_kg', reps: 3, rpe: 8, note: '' },
      { itemId: 'c-pull-up-weighted', set: 2, load: 5, loadType: 'bodyweight_plus_kg', reps: 3, rpe: 9, note: '' },
    ],
  });
  const { maxes } = store.finishSession('athlete-b', 1, 2, new Date('2026-09-12T19:00:00Z'));
  assert.equal(maxes['pull-up-weighted'].threeRm, 5);
  assert.equal(maxes['pull-up-weighted'].e1rm, 5.4);
  assert.equal('bodyweightReps' in maxes['pull-up-weighted'], false);
});

test('a pull-up ramp that never clears three records the best bodyweight rep count', () => {
  const root = pullUpFixture();
  const store = createGymStore(root);
  store.saveSession('athlete-b', 1, 2, {
    entries: [
      { itemId: 'c-pull-up-weighted', set: 1, load: 0, loadType: 'bodyweight_plus_kg', reps: 2, rpe: 10, note: '' },
      { itemId: 'c-pull-up-weighted', set: 2, load: 0, loadType: 'bodyweight_plus_kg', reps: 2, rpe: 10, note: '' },
      { itemId: 'c-pull-up-weighted', set: 3, load: 0, loadType: 'bodyweight_plus_kg', reps: 1, rpe: 10, note: '' },
      { itemId: 'c-pull-up-weighted', set: 4, load: 0, loadType: 'bodyweight_plus_kg', reps: 1, rpe: 10, note: '' },
    ],
  });
  const { maxes } = store.finishSession('athlete-b', 1, 2, new Date('2026-09-12T19:00:00Z'));
  assert.equal(maxes['pull-up-weighted'].bodyweightReps, 2);
  assert.equal(maxes['pull-up-weighted'].threeRm, null);
  assert.equal(maxes['pull-up-weighted'].e1rm, null);
  assert.equal(maxes['pull-up-weighted'].testedWeek, 1);
  assert.equal(maxes['pull-up-weighted'].testedOn, '2026-09-12');
});

test('a retested bodyweight rep count is archived onto history before the new one lands', () => {
  const root = pullUpFixture();
  const store = createGymStore(root);
  store._writeJson(path.join(root, 'athlete-b', 'maxes.json'), testedAtTwoBodyweightReps());
  store.saveSession('athlete-b', 5, 2, {
    entries: [
      { itemId: 'c-pull-up-weighted', set: 1, load: 0, loadType: 'bodyweight_plus_kg', reps: 4, rpe: 10, note: '' },
      { itemId: 'c-pull-up-weighted', set: 2, load: 0, loadType: 'bodyweight_plus_kg', reps: 3, rpe: 10, note: 'last one was a struggle' },
    ],
  });
  const { maxes } = store.finishSession('athlete-b', 5, 2, new Date('2026-10-10T19:00:00Z'));
  assert.deepEqual(maxes['pull-up-weighted'].history, [{ week: 1, bodyweightReps: 2 }]);
  assert.equal(maxes['pull-up-weighted'].bodyweightReps, 4);
  assert.equal(maxes['pull-up-weighted'].threeRm, null);
  assert.equal(maxes['pull-up-weighted'].testedWeek, 5);
});

/**
 * The transition the program is actually aiming at: two strict bodyweight reps
 * in week 1, a tested triple by the retest. The archived point is the only
 * record that the athlete started at two, so losing it here would erase the
 * whole reason the rep count is stored.
 */
test('a pull-up that progresses from bodyweight reps to a real 3RM archives the old rep count', () => {
  const root = pullUpFixture();
  const store = createGymStore(root);
  store._writeJson(path.join(root, 'athlete-b', 'maxes.json'), testedAtTwoBodyweightReps());
  store.saveSession('athlete-b', 5, 2, {
    entries: [
      { itemId: 'c-pull-up-weighted', set: 1, load: 0, loadType: 'bodyweight_plus_kg', reps: 3, rpe: 8, note: '' },
      { itemId: 'c-pull-up-weighted', set: 2, load: 5, loadType: 'bodyweight_plus_kg', reps: 3, rpe: 9.5, note: '' },
    ],
  });
  const { maxes } = store.finishSession('athlete-b', 5, 2, new Date('2026-10-10T19:00:00Z'));
  assert.deepEqual(maxes['pull-up-weighted'].history, [{ week: 1, bodyweightReps: 2 }]);
  assert.equal(maxes['pull-up-weighted'].threeRm, 5);
  assert.equal(maxes['pull-up-weighted'].e1rm, 5.4);
  assert.equal('bodyweightReps' in maxes['pull-up-weighted'], false);
});

// Calendar dates are local, not UTC.
// Athlete A finished a session at 21:28 EDT on Friday 11 September, which is 01:28
// UTC on Saturday. None of these tests depend on the machine's timezone: the
// phone's date is injected as a hint, and any server-side fallback is compared
// against localDateString rather than a hard-coded day.

const FRIDAY_EVENING_TORONTO = new Date('2026-09-12T01:28:00Z');

function logOneTriple(store) {
  store.saveSession('athlete-b', 1, 2, {
    entries: [{ itemId: 'a-back-squat', set: 1, load: 60, loadType: 'kg', reps: 3, rpe: 9, note: '' }],
  });
}

const shiftDays = (ymd, days) => new Date(Date.parse(`${ymd}T00:00:00Z`) + days * 86400000)
  .toISOString().slice(0, 10);

test('localDateString reads the local calendar, not the UTC one', () => {
  // Built from local components, so it is 21:28 on the 11th on every machine.
  assert.equal(localDateString(new Date(2026, 8, 11, 21, 28)), '2026-09-11');
  assert.equal(localDateString(new Date(2026, 0, 5, 0, 0)), '2026-01-05');
});

test('finishing with the phone date of a late evening stores that date, not the UTC one', () => {
  const store = createGymStore(fixture());
  logOneTriple(store);
  const { log, maxes } = store.finishSession('athlete-b', 1, 2, FRIDAY_EVENING_TORONTO, '2026-09-11');
  assert.equal(log.performedOn, '2026-09-11');
  assert.equal(maxes['back-squat'].testedOn, log.performedOn);
  assert.equal(store.getWeek('athlete-b', 1).days[1].performedOn, '2026-09-11');
});

test('an untrustworthy phone date falls back to the server calendar rather than being stored', () => {
  const cases = [
    ['garbage', FRIDAY_EVENING_TORONTO],
    ['2026-9-11', FRIDAY_EVENING_TORONTO],
    [20260911, FRIDAY_EVENING_TORONTO],
    ['2026-09-09', FRIDAY_EVENING_TORONTO],          // two or more days before
    ['2026-09-15', FRIDAY_EVENING_TORONTO],          // days ahead
    // An impossible date beside a real one. Rolled over it would be 2 March,
    // within a day of this clock in every timezone, so only the calendar check
    // can reject it.
    ['2026-02-30', new Date('2026-03-01T12:00:00Z')],
  ];
  for (const [hint, now] of cases) {
    const store = createGymStore(fixture());
    logOneTriple(store);
    const { log, maxes } = store.finishSession('athlete-b', 1, 2, now, hint);
    assert.notEqual(log.performedOn, hint, `hint ${hint} should have been rejected`);
    assert.equal(log.performedOn, localDateString(now), `hint ${hint} should fall back to the server date`);
    assert.equal(maxes['back-squat'].testedOn, log.performedOn);
  }
});

test('a phone date one day either side of the server date is accepted, two is not', () => {
  const now = FRIDAY_EVENING_TORONTO;
  const server = localDateString(now);
  for (const [offset, accepted] of [[-1, true], [1, true], [-2, false], [2, false]]) {
    const store = createGymStore(fixture());
    logOneTriple(store);
    const hint = shiftDays(server, offset);
    const { log } = store.finishSession('athlete-b', 1, 2, now, hint);
    assert.equal(log.performedOn, accepted ? hint : server, `offset ${offset}`);
  }
});

test('with no phone date the fallback is the server local date', () => {
  const store = createGymStore(fixture());
  logOneTriple(store);
  const { log } = store.finishSession('athlete-b', 1, 2, FRIDAY_EVENING_TORONTO);
  assert.equal(log.performedOn, localDateString(FRIDAY_EVENING_TORONTO));
});

test('reopen and refinish keeps the original date even when the phone sends a new one', () => {
  const store = createGymStore(fixture());
  logOneTriple(store);
  store.finishSession('athlete-b', 1, 2, FRIDAY_EVENING_TORONTO, '2026-09-11');
  store.reopenSession('athlete-b', 1, 2);
  const later = new Date('2026-09-14T19:00:00Z');
  const again = store.finishSession('athlete-b', 1, 2, later, localDateString(later));
  assert.equal(again.log.performedOn, '2026-09-11');
  assert.equal(again.maxes['back-squat'].testedOn, '2026-09-11');
});

test('listProfiles turns the week over on the local Monday, not on Sunday evening', () => {
  const store = createGymStore(fixture());
  const weeks = (ymd) => store.listProfiles(ymd).map((p) => p.currentWeek);
  assert.deepEqual(weeks('2026-09-13'), [1, 1]);   // Sunday, however late
  assert.deepEqual(weeks('2026-09-14'), [2, 2]);   // the following Monday
});
