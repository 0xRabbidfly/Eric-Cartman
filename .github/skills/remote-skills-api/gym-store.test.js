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

test('getWeek annotates each day with its log status', () => {
  const store = createGymStore(fixture());
  const week = store.getWeek('athlete-a', 1);
  assert.equal(week.week, 1);
  assert.deepEqual(week.days.map((d) => d.logStatus), ['complete', 'not_started', 'not_started']);
  assert.equal(week.days[0].performedOn, '2026-09-09');
  assert.equal(week.days[0].loggedSets, 1);
  assert.equal(week.bounds, undefined);
  assert.deepEqual(week.span, { first: '2026-09-09', last: '2026-09-09' });
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
  const root = fixture();
  fs.writeFileSync(path.join(root, 'profiles.json'), JSON.stringify({
    programWeeks: 12,
    profiles: [{ id: 'athlete-a', name: 'Athlete A', startDate: 'not-a-date' }],
  }), 'utf8');
  const store = createGymStore(root);
  assert.throws(() => store.listProfiles('2026-09-09'), (err) => err.code === 'gym_data_corrupt');
  assert.throws(() => store.getStats('athlete-a', '2026-09-09'), (err) => err.code === 'gym_data_corrupt');
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

// Program position is by session sequence, not by calendar.
// A session is done once it has ever been finished: its log carries a
// performedOn date. Every date below is injected, so none of these tests
// depends on the machine clock or its timezone.

/** Write a finished log straight into the fixture, dated `performedOn`. */
function markDone(root, profile, week, day, performedOn) {
  const target = path.join(root, profile, 'logs', `W${week}D${day}.json`);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, JSON.stringify({
    profileId: profile, week, day, status: 'complete', performedOn,
    startedAt: `${performedOn}T17:00:00Z`, completedAt: `${performedOn}T18:00:00Z`,
    entries: [], dayNotes: '',
  }), 'utf8');
}

test('listProfiles keeps an unfinished week current after its Sunday has passed', () => {
  const store = createGymStore(fixture());
  // athlete-a has done W1 D1 only. Months later, W1 is still where they are.
  for (const today of ['2026-09-13', '2026-09-14', '2026-12-25']) {
    const [a, b] = store.listProfiles(today);
    assert.equal(a.currentWeek, 1, today);
    assert.deepEqual(a.nextSession, { week: 1, day: 2 }, today);
    assert.equal(a.sessionsDone, 1);
    assert.deepEqual(b.nextSession, { week: 1, day: 1 });
    assert.equal(b.sessionsDone, 0);
  }
});

test('nextSession is W1 D1 when nothing is logged', () => {
  assert.deepEqual(createGymStore(fixture()).nextSession('athlete-b'), { week: 1, day: 1 });
});

test('nextSession is W1 D3 once W1 D1 and D2 are done', () => {
  const root = fixture();
  markDone(root, 'athlete-a', 1, 2, '2026-09-11');
  assert.deepEqual(createGymStore(root).nextSession('athlete-a'), { week: 1, day: 3 });
});

test('nextSession is null once all 36 sessions are done, and the profile moves past week 12', () => {
  const root = fixture();
  for (let week = 1; week <= 12; week += 1) {
    for (let day = 1; day <= 3; day += 1) markDone(root, 'athlete-b', week, day, '2026-11-20');
  }
  markDone(root, 'athlete-b', 12, 3, '2026-11-29');
  const store = createGymStore(root);
  assert.equal(store.nextSession('athlete-b'), null);
  const b = store.listProfiles('2026-12-01')[1];
  assert.equal(b.currentWeek, 13);
  assert.equal(b.nextSession, null);
  assert.equal(b.sessionsDone, 36);
  // Finished: the block ended on its last session, not on today.
  assert.equal(b.pace.projectedFinish, '2026-11-29');
  assert.equal(b.pace.projectionNote, null);
  assert.equal(b.pace.status, 'onPlan');
});

test('a session saved but never finished is not done, so it stays next', () => {
  const store = createGymStore(fixture());
  store.saveSession('athlete-a', 1, 2, {
    entries: [{ itemId: 'a-back-squat', set: 1, load: 60, loadType: 'kg', reps: 3, rpe: 8, note: '' }],
  });
  assert.deepEqual(store.nextSession('athlete-a'), { week: 1, day: 2 });
});

test('reopening a finished earlier session does not move the athlete backwards', () => {
  const root = fixture();
  const store = createGymStore(root);
  store.saveSession('athlete-a', 1, 2, {
    entries: [{ itemId: 'a-back-squat', set: 1, load: 60, loadType: 'kg', reps: 3, rpe: 8, note: '' }],
  });
  store.finishSession('athlete-a', 1, 2, new Date('2026-09-11T19:00:00Z'), '2026-09-11');
  assert.deepEqual(store.nextSession('athlete-a'), { week: 1, day: 3 });

  store.reopenSession('athlete-a', 1, 1);
  assert.equal(store.getSession('athlete-a', 1, 1).log.status, 'in_progress');
  assert.deepEqual(store.nextSession('athlete-a'), { week: 1, day: 3 });
  // Still writable, because it was done before it was reopened.
  store.assertInSequence('athlete-a', 1, 1);
});

test('assertInSequence allows the next session and any done one, and locks anything later', () => {
  const root = fixture();
  markDone(root, 'athlete-a', 1, 2, '2026-09-11');
  const store = createGymStore(root);
  store.assertInSequence('athlete-a', 1, 3);   // next
  store.assertInSequence('athlete-a', 1, 1);   // done
  store.assertInSequence('athlete-a', 1, 2);   // done
  for (const [week, day] of [[2, 1], [2, 3], [12, 3]]) {
    assert.throws(() => store.assertInSequence('athlete-a', week, day), (err) => {
      assert.equal(err.code, 'gym_session_out_of_sequence');
      assert.match(err.message, /W1 D3 is up next/);
      return true;
    }, `W${week} D${day}`);
  }
  assert.throws(() => store.assertInSequence('athlete-a', 2, 2), /unlocks after W2 D1/);
});

test('assertInSequence reports an unknown profile or a session outside the program as such', () => {
  const store = createGymStore(fixture());
  expectCode(() => store.assertInSequence('stan', 1, 1), 'gym_profile_required');
  expectCode(() => store.assertInSequence('athlete-a', 13, 1), 'gym_week_not_found');
  expectCode(() => store.assertInSequence('athlete-a', Number.NaN, 1), 'gym_week_not_found');
  expectCode(() => store.assertInSequence('athlete-a', 1, 4), 'gym_session_not_found');
});

test('getWeek marks exactly one day up next and every later day locked', () => {
  const store = createGymStore(fixture());
  const week1 = store.getWeek('athlete-a', 1);
  assert.deepEqual(week1.days.map((d) => d.upNext), [false, true, false]);
  assert.deepEqual(week1.days.map((d) => d.locked), [false, false, true]);
  const week2 = store.getWeek('athlete-a', 2);
  assert.deepEqual(week2.days.map((d) => d.upNext), [false, false, false]);
  assert.deepEqual(week2.days.map((d) => d.locked), [true, true, true]);
  assert.equal(week2.span, null);
});

test('getWeek span runs from the first to the last session performed that week', () => {
  const root = fixture();
  markDone(root, 'athlete-a', 1, 2, '2026-09-11');
  markDone(root, 'athlete-a', 1, 3, '2026-09-15');
  const week = createGymStore(root).getWeek('athlete-a', 1);
  assert.deepEqual(week.span, { first: '2026-09-09', last: '2026-09-15' });
  assert.deepEqual(week.days.map((d) => d.locked), [false, false, false]);
  assert.equal(createGymStore(root).getWeek('athlete-a', 2).days[0].upNext, true);
});

test('getSession says whether the session is locked or up next, and stays readable when locked', () => {
  const store = createGymStore(fixture());
  const next = store.getSession('athlete-a', 1, 2);
  assert.equal(next.upNext, true);
  assert.equal(next.locked, false);
  const later = store.getSession('athlete-a', 1, 3);
  assert.equal(later.locked, true);
  assert.equal(later.upNext, false);
  assert.equal(later.day.title, 'Day 3');
  assert.equal(store.getSession('athlete-a', 1, 1).locked, false);
});

// Tracker semantics. Three sessions are owed for each calendar week that has
// ended; the current week is granted its three without judgement. Behind means
// fewer than owed, ahead means more than owed plus the current week's three.

/** athlete-a's W1 D1 is in the fixture on 2026-09-09; add these after it, in order. */
function doneOn(root, dates) {
  let index = 1;                                          // W1 D2 is index 1
  for (const date of dates) {
    markDone(root, 'athlete-a', Math.floor(index / 3) + 1, (index % 3) + 1, date);
    index += 1;
  }
}

test('pace on the Sunday ending week 1 with two sessions done is on plan', () => {
  const root = fixture();
  doneOn(root, ['2026-09-11']);
  const { pace } = createGymStore(root).getStats('athlete-a', '2026-09-13');
  assert.equal(pace.sessionsDone, 2);
  assert.equal(pace.remainingSessions, 34);
  assert.equal(pace.expectedByNow, 0);                  // week 1 has not ended
  assert.equal(pace.status, 'onPlan');
  assert.equal(pace.gap, 0);
  assert.equal(pace.behindWeeks, null);
  assert.equal(pace.thisWeekDone, 2);
  assert.equal('delta' in pace, false);
  // No week has ended, so there is no pace and no projection yet.
  assert.equal(pace.calendarWeeksElapsed, 0);
  assert.equal(pace.sessionsPerWeek, null);
  assert.equal(pace.projectedFinish, null);
  assert.match(pace.projectionNote, /two full weeks/);
  assert.equal(pace.plannedFinish, '2026-11-30');       // 7 Sep plus 12 weeks
  assert.deepEqual(pace.sessionsPerCalendarWeek, [{ weekStart: '2026-09-07', count: 2 }]);
});

test('pace on the Monday of week 2 with the same two sessions is one behind', () => {
  const root = fixture();
  doneOn(root, ['2026-09-11']);
  const { pace } = createGymStore(root).getStats('athlete-a', '2026-09-14');
  assert.equal(pace.expectedByNow, 3);
  assert.equal(pace.status, 'behind');
  assert.equal(pace.gap, 1);
  assert.equal(pace.behindWeeks, 0.3);
  assert.equal(pace.thisWeekDone, 0);
  assert.equal(pace.calendarWeeksElapsed, 1);
  assert.equal(pace.sessionsPerWeek, 2);
  // One ended week is not enough to project from.
  assert.equal(pace.projectedFinish, null);
  assert.match(pace.projectionNote, /two full weeks/);
  assert.deepEqual(pace.sessionsPerCalendarWeek, [
    { weekStart: '2026-09-07', count: 2 },
    { weekStart: '2026-09-14', count: 0 },
  ]);
});

test('seven sessions during week 2 is one ahead', () => {
  const root = fixture();
  doneOn(root, ['2026-09-10', '2026-09-11', '2026-09-14', '2026-09-15', '2026-09-15', '2026-09-16']);
  const { pace } = createGymStore(root).getStats('athlete-a', '2026-09-16');
  assert.equal(pace.sessionsDone, 7);
  assert.equal(pace.expectedByNow, 3);
  assert.equal(pace.status, 'ahead');
  assert.equal(pace.gap, 1);
  assert.equal(pace.behindWeeks, null);
  assert.equal(pace.thisWeekDone, 4);
});

test('three sessions owed and three done is on plan, and so is six done during that week', () => {
  const root = fixture();
  doneOn(root, ['2026-09-10', '2026-09-11']);
  const store = createGymStore(root);
  const three = store.getStats('athlete-a', '2026-09-15').pace;
  assert.equal(three.expectedByNow, 3);
  assert.equal(three.status, 'onPlan');
  assert.equal(three.gap, 0);
  doneOn(root, ['2026-09-10', '2026-09-11', '2026-09-14', '2026-09-15', '2026-09-15']);
  const six = createGymStore(root).getStats('athlete-a', '2026-09-15').pace;
  assert.equal(six.sessionsDone, 6);
  assert.equal(six.status, 'onPlan');
});

test('the projected finish appears once two calendar weeks have ended', () => {
  const root = fixture();
  // Four sessions in the two ended weeks, one on the Monday of week 3.
  doneOn(root, ['2026-09-11', '2026-09-16', '2026-09-18', '2026-09-21']);
  const store = createGymStore(root);
  const sunday = store.getStats('athlete-a', '2026-09-20').pace;
  assert.equal(sunday.calendarWeeksElapsed, 1);
  assert.equal(sunday.projectedFinish, null);
  const monday = store.getStats('athlete-a', '2026-09-21').pace;
  assert.equal(monday.calendarWeeksElapsed, 2);
  assert.equal(monday.sessionsPerWeek, 2);              // 4 sessions over 2 ended weeks
  assert.equal(monday.remainingSessions, 31);           // every session done counts here
  // 31 sessions at 14 days per 4 sessions is 108.5, so 109 days after 21 Sep.
  assert.equal(monday.projectedFinish, '2027-01-08');
  assert.equal(monday.projectionNote, null);
  assert.equal(monday.expectedByNow, 6);
  assert.equal(monday.status, 'behind');
  assert.equal(monday.gap, 1);
});

test('pace ignores sessions performed in the current, unfinished week', () => {
  const ended = ['2026-09-11', '2026-09-16', '2026-09-18'];   // with W1 D1, four in ended weeks
  const without = fixture();
  doneOn(without, ended);
  const withCurrent = fixture();
  doneOn(withCurrent, [...ended, '2026-09-21', '2026-09-22']);

  const a = createGymStore(without).getStats('athlete-a', '2026-09-23').pace;
  const b = createGymStore(withCurrent).getStats('athlete-a', '2026-09-23').pace;
  assert.equal(a.sessionsPerWeek, 2);
  assert.equal(b.sessionsPerWeek, 2);
  assert.equal(b.thisWeekDone, 2);
  // Remaining sessions still count everything done: 32 against 30.
  assert.equal(a.projectedFinish, '2027-01-13');        // ceil(32 × 14 / 4) = 112 days
  assert.equal(b.projectedFinish, '2027-01-06');        // ceil(30 × 14 / 4) = 105 days
});

test('pace with nothing done has no projection rather than an infinite one', () => {
  const { pace } = createGymStore(fixture()).getStats('athlete-b', '2026-09-21');
  assert.equal(pace.sessionsDone, 0);
  assert.equal(pace.sessionsPerWeek, 0);
  assert.equal(pace.projectedFinish, null);
  assert.match(pace.projectionNote, /no pace to project from/);
  assert.equal(pace.plannedFinish, '2026-11-30');
  assert.equal(pace.expectedByNow, 6);
  assert.equal(pace.status, 'behind');
  assert.equal(pace.gap, 6);
  assert.equal(pace.behindWeeks, 2);
  assert.ok(Object.values(pace).every((v) => v === null || typeof v !== 'number' || Number.isFinite(v)));
});

test('pace before the start date owes nothing and divides by nothing', () => {
  const { pace } = createGymStore(fixture()).getStats('athlete-a', '2026-09-01');
  assert.equal(pace.calendarWeeksElapsed, 0);
  assert.equal(pace.sessionsPerWeek, null);
  assert.equal(pace.expectedByNow, 0);
  assert.equal(pace.status, 'onPlan');
});

test('thisWeekDone counts only sessions performed in the current calendar week', () => {
  const root = fixture();
  doneOn(root, ['2026-09-13', '2026-09-14', '2026-09-20']);   // Sunday wk 1, Monday and Sunday wk 2
  const { pace } = createGymStore(root).getStats('athlete-a', '2026-09-17');
  assert.equal(pace.thisWeekDone, 2);
  assert.deepEqual(pace.sessionsPerCalendarWeek.map((w) => w.count), [2, 2]);
  assert.equal(pace.expectedByNow, 3);
  assert.equal(pace.status, 'onPlan');
});

test('listProfiles gives every profile a compact pace object', () => {
  const root = fixture();
  doneOn(root, ['2026-09-11']);
  const profiles = createGymStore(root).listProfiles('2026-09-14');
  assert.equal(profiles.length, 2);
  for (const p of profiles) {
    assert.deepEqual(Object.keys(p.pace).sort(), [
      'behindWeeks', 'expectedByNow', 'gap', 'plannedFinish', 'projectedFinish', 'projectionNote',
      'sessionsDone', 'status', 'thisWeekDone',
    ]);
  }
  assert.deepEqual([profiles[0].pace.status, profiles[0].pace.gap], ['behind', 1]);
  assert.deepEqual([profiles[1].pace.status, profiles[1].pace.gap], ['behind', 3]);
  assert.equal(profiles[1].pace.behindWeeks, 1);
  assert.equal(profiles[1].pace.projectedFinish, null);
});

// ── Second program type: strength-tone ──
//
// A strength-tone athlete never ramps to a max. Their W1 records working sets
// and a handful of isBaseline measurements, some of them rep counts, so the
// store has to file a rep baseline (including a result of 0) and the stats
// view has to show something other than empty 3RM cards.

function toneItem(id, key, extra = {}) {
  return {
    id, block: id.charAt(0).toUpperCase(), exerciseKey: key, label: key, sets: 3, reps: 8,
    repsMax: 10, resultType: 'reps', loadType: 'kg', targetLoad: null, targetPct: null,
    loadNote: '', targetRpe: 7, restSec: 90, isRamp: false, isBaseline: false,
    setsAreOptional: false, pairedWith: null, ...extra,
  };
}

function toneFixture() {
  const root = fixture();
  const write = (rel, obj) => {
    const target = path.join(root, rel);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, JSON.stringify(obj), 'utf8');
  };
  const profiles = JSON.parse(fs.readFileSync(path.join(root, 'profiles.json'), 'utf8'));
  profiles.profiles.push({ id: 'athlete-c', name: 'Athlete C', startDate: '2026-09-14', program: 'strength-tone' });
  write('profiles.json', profiles);
  const baseline = (id, key, resultType) => toneItem(id, key, {
    sets: 2, reps: 1, repsMax: undefined, resultType, loadType: 'bodyweight', targetRpe: null, isBaseline: true,
  });
  const week = (n) => ({
    week: n, block: n === 1 ? 'baseline' : 'foundation', blockLabel: n === 1 ? 'Baseline week' : 'Foundation',
    goal: 'g', retest: n === 1 || n === 5, loadsResolved: n === 1, generatedAt: null,
    days: [
      { day: 1, title: 'Lower + core · knee', estMinutes: 50, warmup: ['rower'], items: [
        toneItem('a-goblet-squat', 'goblet-squat'),
        toneItem('b-dumbbell-step-up', 'dumbbell-step-up', { loadType: 'kg_total_pair', resultType: 'reps_per_side' }),
        toneItem('d-hip-abduction', 'hip-abduction', { loadType: 'setting', reps: 12, repsMax: 15 }),
        baseline('e-front-plank', 'front-plank', 'seconds'),
      ] },
      { day: 2, title: 'Upper + core · pull-up', estMinutes: 55, warmup: ['arm circles'], items: [
        baseline('a-dead-hang', 'dead-hang', 'seconds'),
        baseline('b-band-assisted-pull-up', 'band-assisted-pull-up', 'reps'),
        baseline('b-pull-up', 'pull-up', 'reps'),
        toneItem('c-lat-pulldown', 'lat-pulldown', { loadType: 'setting' }),
      ] },
      { day: 3, title: 'Lower + core · hip', estMinutes: 50, warmup: ['rower'], items: [
        toneItem('a-dumbbell-romanian-deadlift', 'dumbbell-romanian-deadlift', { loadType: 'kg_total_pair' }),
      ] },
    ],
  });
  for (let n = 1; n <= 12; n += 1) write(`athlete-c/weeks/W${n}.json`, week(n));
  write('athlete-c/maxes.json', {});
  return root;
}

const toneSet = (itemId, n, load, loadType, reps, rpe = null) => ({ itemId, set: n, load, loadType, reps, rpe, note: '' });

test('listProfiles passes the program through and treats a missing one as cycling', () => {
  const profiles = createGymStore(toneFixture()).listProfiles('2026-09-13');
  assert.deepEqual(profiles.map((p) => [p.id, p.program]), [
    ['athlete-a', 'cycling'], ['athlete-b', 'cycling'], ['athlete-c', 'strength-tone'],
  ]);
  const c = profiles[2];
  assert.deepEqual(c.nextSession, { week: 1, day: 1 });
  assert.equal(c.pace.status, 'onPlan');
});

test('a strength-tone week keeps the sequence rules: D1 up next, D2 and D3 locked', () => {
  const week = createGymStore(toneFixture()).getWeek('athlete-c', 1);
  assert.deepEqual(week.days.map((d) => [d.upNext, d.locked]), [[true, false], [false, true], [false, true]]);
  assert.equal(week.days[0].items[0].repsMax, 10);
});

test('rep-count baselines are filed, and a strict pull-up result of 0 is kept rather than dropped', () => {
  const root = toneFixture();
  const store = createGymStore(root);
  const days = {
    1: [toneSet('a-goblet-squat', 1, 12, 'kg', 10, 7), toneSet('e-front-plank', 1, null, 'bodyweight', 45)],
    2: [
      toneSet('a-dead-hang', 1, null, 'bodyweight', 18), toneSet('a-dead-hang', 2, null, 'bodyweight', 22),
      toneSet('b-band-assisted-pull-up', 1, null, 'bodyweight', 6),
      toneSet('b-pull-up', 1, null, 'bodyweight', 0), toneSet('b-pull-up', 2, null, 'bodyweight', 0),
      toneSet('c-lat-pulldown', 1, 5, 'setting', 10, 7),
    ],
  };
  for (const day of [1, 2]) {
    store.saveSession('athlete-c', 1, day, { entries: days[day] });
    store.finishSession('athlete-c', 1, day, new Date(`2026-09-1${4 + day}T18:00:00`));
  }
  const maxes = JSON.parse(fs.readFileSync(path.join(root, 'athlete-c', 'maxes.json'), 'utf8'));
  assert.deepEqual(Object.keys(maxes).sort(), ['band-assisted-pull-up', 'dead-hang', 'front-plank', 'pull-up']);
  assert.equal(maxes['dead-hang'].seconds, 22);
  assert.equal(maxes['band-assisted-pull-up'].reps, 6);
  assert.equal(maxes['pull-up'].reps, 0);
  assert.equal(maxes['front-plank'].seconds, 45);
  // Working sets are never promoted: no 3RM, no estimated 1RM, nothing for goblet squat.
  for (const value of Object.values(maxes)) {
    assert.equal(value.threeRm, undefined);
    assert.equal(value.e1rm, undefined);
  }
});

test('a re-checked rep baseline archives the earlier count onto history', () => {
  const root = toneFixture();
  const store = createGymStore(root);
  store._writeJson(path.join(root, 'athlete-c', 'maxes.json'), {
    'pull-up': { reps: 0, testedWeek: 1, testedOn: '2026-09-16', history: [] },
  });
  // W5 D2 reuses the same item shapes in this fixture.
  store.saveSession('athlete-c', 5, 2, { entries: [toneSet('b-pull-up', 1, null, 'bodyweight', 1)] });
  store.finishSession('athlete-c', 5, 2, new Date('2026-10-14T18:00:00'));
  const maxes = JSON.parse(fs.readFileSync(path.join(root, 'athlete-c', 'maxes.json'), 'utf8'));
  assert.deepEqual(maxes['pull-up'].history, [{ week: 1, reps: 0 }]);
  assert.equal(maxes['pull-up'].reps, 1);
  const trend = createGymStore(root).getStats('athlete-c', '2026-10-14').baselineTrend['pull-up'];
  assert.deepEqual(trend, { unit: 'reps', points: [{ week: 1, value: 0 }, { week: 5, value: 1 }] });
});

test('getStats for a strength-tone athlete has no 1RM trend but a working-load trend and baselines', () => {
  const root = toneFixture();
  const store = createGymStore(root);
  store.saveSession('athlete-c', 1, 1, { entries: [
    toneSet('a-goblet-squat', 1, 10, 'kg', 10, 6),
    toneSet('a-goblet-squat', 2, 12, 'kg', 10, 7),
    toneSet('a-goblet-squat', 3, 12, 'kg', 9, 7),
    toneSet('b-dumbbell-step-up', 1, 8, 'kg_total_pair', 10, 7),
    toneSet('d-hip-abduction', 1, 6, 'setting', 15, 7),
    toneSet('e-front-plank', 1, null, 'bodyweight', 40),
  ] });
  store.finishSession('athlete-c', 1, 1, new Date('2026-09-15T18:00:00'));
  const stats = createGymStore(root).getStats('athlete-c', '2026-09-15');
  assert.equal(stats.program, 'strength-tone');
  assert.deepEqual(stats.maxTrend, {});
  assert.deepEqual(stats.loadTrend['goblet-squat'],
    { label: 'goblet-squat', loadType: 'kg', points: [{ week: 1, load: 12, reps: 10 }] });
  assert.deepEqual(stats.loadTrend['dumbbell-step-up'].points, [{ week: 1, load: 8, reps: 10 }]);
  // A machine pin is not kilograms, so it has no load trend.
  assert.equal(stats.loadTrend['hip-abduction'], undefined);
  assert.equal(stats.baselines['front-plank'].seconds, 40);
  assert.deepEqual(stats.baselineTrend['front-plank'], { unit: 'seconds', points: [{ week: 1, value: 40 }] });
  // 12×10 + 10×10 + 12×9 on the squat, 8×10 per side on the step-up.
  assert.equal(stats.weeks[0].tonnage, 120 + 100 + 108 + 160);
});

test('a cycling athlete reports its program too, and its stats keep the 1RM trend', () => {
  const stats = createGymStore(toneFixture()).getStats('athlete-a', '2026-09-13');
  assert.equal(stats.program, 'cycling');
  assert.deepEqual(stats.maxTrend['back-squat'], [{ week: 1, e1rm: 75.6, threeRm: 70 }]);
  assert.deepEqual(stats.baselineTrend, {});
});
