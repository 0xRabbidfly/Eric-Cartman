/**
 * Data layer for the gym tracker. Pure filesystem and arithmetic, no Express.
 *
 * The store is a factory so tests can point it at a temp directory. server.js
 * builds exactly one against the real data root.
 *
 * Shape of the data is documented in
 * .claude/skills/gym-cyclist/specs/2026-09-09-gym-tracker-app-design.md
 */
const fs = require('fs');
const path = require('path');

const DAY_MS = 24 * 60 * 60 * 1000;
const WEEK_MS = 7 * DAY_MS;
const PROGRAM_WEEKS = 12;
const SESSIONS_PER_WEEK = 3;
const PROGRAM_SESSIONS = PROGRAM_WEEKS * SESSIONS_PER_WEEK;
/** One full week is not a pace. Two is the least the projection is shown on. */
const PROJECTION_MIN_ENDED_WEEKS = 2;

function fail(code, message) {
  const err = new Error(message);
  err.code = code;
  return err;
}

/** Midnight UTC of the Monday on or before `date`. */
function mondayOf(date) {
  const utc = Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate());
  const dow = new Date(utc).getUTCDay();      // 0 = Sunday
  const backToMonday = (dow + 6) % 7;
  return utc - backToMonday * DAY_MS;
}

function isoDate(ms) {
  return new Date(ms).toISOString().slice(0, 10);
}

/**
 * The calendar date on this machine's clock, as YYYY-MM-DD.
 *
 * A workout's date is a wall-calendar fact, not an instant. toISOString gives
 * the UTC date, which in Toronto rolls over at 8pm (7pm in winter): a Friday
 * evening session would be filed as Saturday, and the 48-hour ride-placement
 * check would measure it from the wrong day.
 */
function localDateString(date = new Date()) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/**
 * The phone's calendar date for a finished session, or null when it cannot be
 * trusted. The phone is where the workout happened, so it knows the day, but a
 * bad client clock must not be able to write a nonsense date: the hint has to
 * be a real calendar date within one day of this machine's own.
 */
function validPerformedOnHint(hint, now) {
  if (typeof hint !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(hint)) return null;
  const hintMs = Date.parse(`${hint}T00:00:00Z`);
  // Round-tripping catches 2026-02-30, which Date may quietly roll into March.
  if (Number.isNaN(hintMs) || isoDate(hintMs) !== hint) return null;
  const serverMs = Date.parse(`${localDateString(now)}T00:00:00Z`);
  return Math.abs(hintMs - serverMs) <= DAY_MS ? hint : null;
}

/** The exercise library is generic and tracked; athlete data under dataRoot is private. */
const DEFAULT_LIBRARY_PATH = path.join(__dirname, 'gym-library', 'exercises.json');

function createGymStore(dataRoot, { libraryPath = DEFAULT_LIBRARY_PATH } = {}) {
  const at = (...parts) => path.join(dataRoot, ...parts);

  function readJson(file, fallback) {
    let raw;
    try {
      raw = fs.readFileSync(file, 'utf8');
    } catch (err) {
      if (err.code === 'ENOENT') return fallback;
      throw fail('gym_data_corrupt', `${path.relative(dataRoot, file)} could not be read: ${err.message}`);
    }
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (err) {
      throw fail('gym_data_corrupt', `${path.relative(dataRoot, file)} is not valid JSON: ${err.message}`);
    }
    if (parsed === null || typeof parsed !== 'object') {
      throw fail('gym_data_corrupt', `${path.relative(dataRoot, file)} should hold an object, not ${parsed === null ? 'null' : typeof parsed}`);
    }
    return parsed;
  }

  function isEnabled() {
    return fs.existsSync(at('profiles.json'));
  }

  function requireEnabled() {
    if (!isEnabled()) {
      throw fail('gym_not_configured', 'No gym data on this machine. Run the gym-cyclist seed scripts.');
    }
  }

  function getProfile(id) {
    requireEnabled();
    const { profiles = [] } = readJson(at('profiles.json'), { profiles: [] });
    return profiles.find((p) => p.id === id) || null;
  }

  /**
   * Which program a profile follows. `cycling` is the original 3RM-tested
   * strength block; `strength-tone` never tests a max and progresses working
   * sets by reps and RPE. Profiles written before the field existed are cycling.
   */
  function programOf(profile) {
    return (profile && profile.program) || 'cycling';
  }

  function requireProfile(id) {
    const profile = getProfile(id);
    if (!profile) {
      throw fail('gym_profile_required', `Unknown profile "${id}". Pass ?profile= with a known id.`);
    }
    return profile;
  }

  function readLog(profileId, week, day) {
    return readJson(at(profileId, 'logs', `W${week}D${day}.json`), null);
  }

  /** Optional podcast picks, keyed `W<week>D<day>`. Kept out of the week files so regenerating a week never drops them. */
  function readPodcasts(profileId) {
    return readJson(at(profileId, 'podcasts.json'), {});
  }

  // ── Program position ──
  //
  // Position in the program is by session sequence, never by calendar. The
  // athletes often manage two sessions in a week and do the third the week
  // after rather than skipping it, so W1 D3 stays next until it is done,
  // however many Mondays pass. The owner chose this on 2026-09-13, replacing a
  // calendar anchor that rolled the week over every Monday.

  /** 0-based position of a session in program order: W1 D1 is 0, W12 D3 is 35. */
  function sessionIndex(week, day) {
    return (week - 1) * SESSIONS_PER_WEEK + (day - 1);
  }

  function sessionAt(index) {
    return { week: Math.floor(index / SESSIONS_PER_WEEK) + 1, day: (index % SESSIONS_PER_WEEK) + 1 };
  }

  /**
   * Every session that has ever been finished, and the first one that has not.
   *
   * Done means the log carries a performedOn date, not that its status is
   * complete. Reopening a finished session to fix a transcribed number keeps
   * performedOn, so it must not move the athlete backwards in the program.
   */
  function sequenceState(profileId) {
    const done = new Set();
    const performed = [];
    for (let index = 0; index < PROGRAM_SESSIONS; index += 1) {
      const { week, day } = sessionAt(index);
      const log = readLog(profileId, week, day);
      if (log && log.performedOn) {
        done.add(index);
        performed.push({ week, day, performedOn: log.performedOn });
      }
    }
    let nextIndex = null;
    for (let index = 0; index < PROGRAM_SESSIONS; index += 1) {
      if (!done.has(index)) { nextIndex = index; break; }
    }
    return { done, performed, nextIndex, next: nextIndex === null ? null : sessionAt(nextIndex) };
  }

  /** The first `{week, day}` in program order not yet done, or null when all 36 are. */
  function nextSession(profileId) {
    requireProfile(profileId);
    return sequenceState(profileId).next;
  }

  /**
   * Any done session and the next one may be written. Anything later is locked.
   * The routes call this; saveSession and finishSession stay free of it, so
   * the data layer can still be exercised session by session in tests.
   */
  function assertInSequence(profileId, week, day) {
    requireProfile(profileId);
    if (!Number.isInteger(week) || week < 1 || week > PROGRAM_WEEKS) {
      throw fail('gym_week_not_found', `Week ${week} is outside 1-${PROGRAM_WEEKS}.`);
    }
    if (!Number.isInteger(day) || day < 1 || day > SESSIONS_PER_WEEK) {
      throw fail('gym_session_not_found', `Day ${day} is outside 1-${SESSIONS_PER_WEEK}.`);
    }
    const state = sequenceState(profileId);
    const index = sessionIndex(week, day);
    if (state.done.has(index) || index === state.nextIndex) return;
    const before = sessionAt(index - 1);
    throw fail('gym_session_out_of_sequence',
      `W${week} D${day} unlocks after W${before.week} D${before.day}. `
      + `Sessions go in order, and W${state.next.week} D${state.next.day} is up next.`);
  }

  function startMondayMs(profile) {
    const parsed = new Date(`${profile.startDate}T00:00:00Z`);
    if (Number.isNaN(parsed.getTime())) {
      throw fail('gym_data_corrupt', `profiles.json has an unusable startDate: ${JSON.stringify(profile.startDate)}`);
    }
    return mondayOf(parsed);
  }

  /**
   * How the athlete is moving through the block against the calendar.
   *
   * `localToday` is a YYYY-MM-DD date on the athletes' calendar, injectable so
   * tests never depend on the machine clock or timezone. It is handled as UTC
   * midnight, so every day here is a whole calendar day.
   *
   * Pace is reported, not enforced: nothing here changes a load or the
   * sequence. It exists so a slower block is visible as a fact.
   */
  function paceFor(profile, state, localToday) {
    const startMs = startMondayMs(profile);
    const plannedStartMs = Date.parse(`${profile.startDate}T00:00:00Z`);
    const todayMs = Date.parse(`${localToday}T00:00:00Z`);
    const todayMonday = mondayOf(new Date(todayMs));

    const mondayOfYmd = (ymd) => mondayOf(new Date(`${ymd}T00:00:00Z`));

    const sessionsDone = state.performed.length;
    const remainingSessions = PROGRAM_SESSIONS - sessionsDone;

    // Calendar weeks, Monday to Sunday, whose Sunday is already behind today.
    const endedWeeks = Math.max(0, Math.floor((todayMonday - startMs) / WEEK_MS));

    // Pace comes from ended weeks only. A partial week says nothing yet: two
    // sessions by Wednesday is on plan, not a rate of four a week, and none by
    // Monday morning is not a rate of zero.
    const doneInEndedWeeks = state.performed
      .filter((s) => mondayOfYmd(s.performedOn) < todayMonday).length;
    const sessionsPerWeek = endedWeeks > 0
      ? Math.round((doneInEndedWeeks / endedWeeks) * 100) / 100
      : null;

    let projectedFinish = null;
    let projectionNote = null;
    if (remainingSessions === 0) {
      // Finished: the block ended on its last session, not on whatever today is.
      projectedFinish = state.performed.map((s) => s.performedOn).sort().pop();
    } else if (endedWeeks < PROJECTION_MIN_ENDED_WEEKS) {
      projectionNote = 'Projected finish appears after two full weeks.';
    } else if (doneInEndedWeeks === 0) {
      projectionNote = 'No sessions in the full weeks so far, so there is no pace to project from.';
    } else {
      // Days per session is (endedWeeks × 7) / doneInEndedWeeks. Kept in
      // integers so a float cannot round the finish a day later.
      projectedFinish = isoDate(todayMs
        + Math.ceil((remainingSessions * endedWeeks * 7) / doneInEndedWeeks) * DAY_MS);
    }

    // A week's three sessions are owed only once that week has ended, and the
    // current week is granted its full three without judgement. So sessions
    // done inside the current week are that week's quota, never "ahead".
    const expectedByNow = Math.min(endedWeeks, PROGRAM_WEEKS) * SESSIONS_PER_WEEK;
    let status = 'onPlan';
    let gap = 0;
    if (sessionsDone < expectedByNow) {
      status = 'behind';
      gap = expectedByNow - sessionsDone;
    } else if (sessionsDone > expectedByNow + SESSIONS_PER_WEEK) {
      status = 'ahead';
      gap = sessionsDone - (expectedByNow + SESSIONS_PER_WEEK);
    }
    const behindWeeks = status === 'behind' ? Math.round((gap / SESSIONS_PER_WEEK) * 10) / 10 : null;

    const thisWeekDone = state.performed.filter((s) => mondayOfYmd(s.performedOn) === todayMonday).length;

    const performedMondays = state.performed.map((s) => mondayOfYmd(s.performedOn))
      .filter((ms) => !Number.isNaN(ms));
    const firstMonday = Math.min(startMs, ...performedMondays);
    const lastMonday = Math.max(todayMonday, ...performedMondays);
    const sessionsPerCalendarWeek = [];
    for (let ms = firstMonday; ms <= lastMonday; ms += WEEK_MS) {
      sessionsPerCalendarWeek.push({
        weekStart: isoDate(ms),
        count: performedMondays.filter((m) => m === ms).length,
      });
    }

    return {
      sessionsDone,
      remainingSessions,
      // Ended calendar weeks: the denominator of sessionsPerWeek.
      calendarWeeksElapsed: endedWeeks,
      sessionsPerWeek,
      plannedFinish: isoDate(plannedStartMs + PROGRAM_WEEKS * WEEK_MS),
      projectedFinish,
      projectionNote,
      expectedByNow,
      status,
      gap,
      behindWeeks,
      thisWeekDone,
      sessionsPerCalendarWeek,
    };
  }

  /** The subset of pace the Week tab shows for every athlete at once. */
  function compactPace(pace) {
    const {
      sessionsDone, expectedByNow, status, gap, behindWeeks, thisWeekDone,
      plannedFinish, projectedFinish, projectionNote,
    } = pace;
    return {
      sessionsDone, expectedByNow, status, gap, behindWeeks, thisWeekDone,
      plannedFinish, projectedFinish, projectionNote,
    };
  }

  /**
   * `currentWeek` is the week holding the next session, or PROGRAM_WEEKS+1 once
   * every session is done. `localToday` feeds only the pace figures.
   */
  function listProfiles(localToday = localDateString(new Date())) {
    requireEnabled();
    const { profiles = [] } = readJson(at('profiles.json'), { profiles: [] });
    return profiles.map((p) => {
      const state = sequenceState(p.id);
      return {
        ...p,
        program: programOf(p),
        currentWeek: state.next ? state.next.week : PROGRAM_WEEKS + 1,
        nextSession: state.next,
        sessionsDone: state.performed.length,
        pace: compactPace(paceFor(p, state, localToday)),
      };
    });
  }

  function emptyLog(profileId, week, day) {
    return {
      profileId, week, day,
      status: 'in_progress',
      performedOn: null,
      startedAt: null,
      completedAt: null,
      entries: [],
      dayNotes: '',
    };
  }

  function readWeekFile(profileId, week) {
    if (!Number.isInteger(week) || week < 1 || week > PROGRAM_WEEKS) {
      throw fail('gym_week_not_found', `Week ${week} is outside 1-${PROGRAM_WEEKS}.`);
    }
    const file = at(profileId, 'weeks', `W${week}.json`);
    const data = readJson(file, null);
    if (!data) throw fail('gym_week_not_found', `No prescription for week ${week}.`);
    if (!Array.isArray(data.days)) {
      throw fail('gym_data_corrupt', `${profileId}/weeks/W${week}.json has no days array.`);
    }
    return data;
  }

  /** Where a session sits against the sequence: the one to do next, or locked behind it. */
  function sequenceFlags(state, week, day) {
    const index = sessionIndex(week, day);
    const upNext = index === state.nextIndex;
    return { upNext, locked: !upNext && !state.done.has(index) };
  }

  /**
   * `span` is the first and last date a session of this week was actually
   * performed, or null before any was. It replaces calendar bounds: a week
   * lasts as long as its three sessions take.
   */
  function getWeek(profileId, week) {
    requireProfile(profileId);
    const data = readWeekFile(profileId, week);
    const state = sequenceState(profileId);
    const podcasts = readPodcasts(profileId);
    const days = data.days.map((day) => {
      const log = readLog(profileId, week, day.day);
      return {
        ...day,
        podcast: podcasts[`W${week}D${day.day}`] || null,
        logStatus: log ? log.status : 'not_started',
        performedOn: log ? log.performedOn : null,
        loggedSets: log ? log.entries.length : 0,
        ...sequenceFlags(state, week, day.day),
      };
    });
    const dates = days.map((d) => d.performedOn).filter(Boolean).sort();
    const span = dates.length ? { first: dates[0], last: dates[dates.length - 1] } : null;
    return { ...data, days, profileId, span };
  }

  /** A locked session stays readable, so the app can show its prescription read-only. */
  function getSession(profileId, week, day) {
    requireProfile(profileId);
    if (!Number.isInteger(day) || day < 1 || day > 3) {
      throw fail('gym_session_not_found', `Day ${day} is outside 1-3.`);
    }
    const weekData = readWeekFile(profileId, week);
    const dayData = weekData.days.find((d) => d.day === day);
    if (!dayData) throw fail('gym_session_not_found', `Week ${week} has no day ${day}.`);
    const { days, ...weekMeta } = weekData;
    return {
      profileId,
      week: weekMeta,
      day: dayData,
      log: readLog(profileId, week, day) || emptyLog(profileId, week, day),
      maxes: readJson(at(profileId, 'maxes.json'), {}),
      podcast: readPodcasts(profileId)[`W${week}D${day}`] || null,
      ...sequenceFlags(sequenceState(profileId), week, day),
    };
  }

  function getExercises() {
    requireEnabled();
    return readJson(libraryPath, {});
  }

  function estimateOneRm(threeRm) {
    return Math.round(threeRm * 1.08 * 10) / 10;
  }

  function writeJson(file, obj) {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, `${JSON.stringify(obj, null, 2)}\n`, 'utf8');
  }

  function dayItems(profileId, week, day) {
    const weekData = readWeekFile(profileId, week);
    const dayData = weekData.days.find((d) => d.day === day);
    if (!dayData) throw fail('gym_session_not_found', `Week ${week} has no day ${day}.`);
    return dayData.items;
  }

  /**
   * Merge a partial update into the stored log and write it back.
   * `entries` replaces the whole array — the client always holds the full set
   * grid, so a merge would only let a stale client resurrect deleted rows.
   */
  function saveSession(profileId, week, day, patch = {}, now = new Date()) {
    requireProfile(profileId);
    const existing = readLog(profileId, week, day) || emptyLog(profileId, week, day);
    if (existing.status === 'complete') {
      throw fail('gym_session_complete', `W${week} D${day} is already finished. Reopen it before editing.`);
    }

    const next = { ...existing };
    if (patch.entries !== undefined) {
      if (!Array.isArray(patch.entries)) {
        throw fail('gym_invalid_entry', 'entries must be an array of logged sets.');
      }
      const valid = new Set(dayItems(profileId, week, day).map((i) => i.id));
      for (const entry of patch.entries) {
        if (!valid.has(entry.itemId)) {
          throw fail('gym_invalid_entry', `"${entry.itemId}" is not an exercise in W${week} D${day}.`);
        }
      }
      next.entries = patch.entries;
    }
    if (patch.dayNotes !== undefined) next.dayNotes = String(patch.dayNotes);
    if (!next.startedAt) next.startedAt = now.toISOString();

    writeJson(at(profileId, 'logs', `W${week}D${day}.json`), next);
    return next;
  }

  /** Heaviest set of full reps at RPE 9.5 or below. That is the program's definition. */
  function bestCleanSet(entries, item) {
    return entries
      .filter((e) => e.itemId === item.id)
      .filter((e) => e.reps >= item.reps)
      .filter((e) => e.rpe === null || e.rpe === undefined || e.rpe <= 9.5)
      .filter((e) => typeof e.load === 'number')
      .reduce((best, e) => (best === null || e.load > best.load ? e : best), null);
  }

  /**
   * Best rep count logged with no added load.
   *
   * Week 1 tells an athlete who cannot do five strict pull-ups to log max clean
   * bodyweight reps instead of ramping to a triple. That is a real measurement —
   * the one the progression ladder reads — so it needs somewhere to live. A
   * max-reps set is RPE 10 by definition, so this deliberately does not apply
   * bestCleanSet's RPE 9.5 ceiling; the ceiling exists to keep a grinding triple
   * out of a 3RM, which is a different question.
   */
  function bestBodyweightReps(entries, item) {
    return entries
      .filter((e) => e.itemId === item.id)
      .filter((e) => e.load === 0)
      .map((e) => e.reps)
      .filter((v) => typeof v === 'number')
      .reduce((best, v) => (best === null || v > best ? v : best), null);
  }

  /** Best result on a baseline item — the longest hold, the furthest jump, the tallest box. */
  function bestResult(entries, item) {
    return entries
      .filter((e) => e.itemId === item.id)
      .map((e) => e.reps)                       // the result column holds cm or seconds here
      .filter((v) => typeof v === 'number')
      .reduce((best, v) => (best === null || v > best ? v : best), null);
  }

  /**
   * Archive the outgoing tested value before it is replaced, so the trend keeps
   * every test. The assessment skill cannot do this — recomputeMaxes runs
   * synchronously in the finish route, before the skill is ever invoked.
   *
   * The testedWeek guard means reopening and re-finishing the same session
   * corrects that week's entry in place rather than appending a duplicate.
   */
  function archiveMax(prev, week) {
    const history = Array.isArray(prev.history) ? prev.history.slice() : [];
    if (prev.testedWeek === undefined || prev.testedWeek === null) return history;
    if (prev.testedWeek === week) return history;
    const point = { week: prev.testedWeek };
    if (typeof prev.threeRm === 'number') { point.threeRm = prev.threeRm; point.e1rm = prev.e1rm; }
    if (typeof prev.cm === 'number') point.cm = prev.cm;
    if (typeof prev.seconds === 'number') point.seconds = prev.seconds;
    if (typeof prev.reps === 'number') point.reps = prev.reps;
    // A bodyweight rep count is a tested result like any other, and it is the
    // only record that an athlete who ends up with a real 3RM started without
    // one. Archiving it is what lets the trend span both measures.
    if (typeof prev.bodyweightReps === 'number') point.bodyweightReps = prev.bodyweightReps;
    if (Object.keys(point).length === 1) return history;   // nothing worth keeping
    history.push(point);
    return history;
  }

  /**
   * Which key a baseline's result is stored under, chosen by the unit it is
   * measured in. `reps` is a rep-count baseline such as strict pull-ups, where
   * 0 is a real result. Only strength-tone weeks flag one today; every cycling
   * baseline is a distance or a hold.
   */
  const BASELINE_UNITS = { cm: 'cm', seconds: 'seconds', reps: 'reps' };
  const BASELINE_UNIT_KEYS = Object.values(BASELINE_UNITS);

  function recomputeMaxes(profileId, week, day, now = new Date()) {
    const file = at(profileId, 'maxes.json');
    const maxes = readJson(file, {});
    const log = readLog(profileId, week, day);
    if (!log) return maxes;
    // A max was tested on the day the workout happened, not on the day the
    // finish button was pressed. Re-finishing a corrected session must not
    // redate it. Only an unfinished log can be missing performedOn.
    const testedOn = log.performedOn || localDateString(now);

    let changed = false;
    for (const item of dayItems(profileId, week, day)) {
      if (item.isRamp) {
        const best = bestCleanSet(log.entries, item);
        if (!best) {
          // A bodyweight_plus_kg ramp with no clean triple is not a failed test.
          // The week-1 prescription anticipates it and asks for max clean
          // bodyweight reps instead, so keep that count. threeRm stays null —
          // there is still no tested 3RM — but the athlete is no longer
          // invisible to the generator, which now has a number to progress from.
          const reps = item.loadType === 'bodyweight_plus_kg'
            ? bestBodyweightReps(log.entries, item)
            : null;
          if (reps === null) continue;
          const prev = maxes[item.exerciseKey] || {};
          maxes[item.exerciseKey] = {
            ...prev,
            history: archiveMax(prev, week),
            threeRm: null,
            loadType: item.loadType,
            e1rm: null,
            bodyweightReps: reps,
            testedWeek: week,
            testedOn,
          };
          changed = true;
          continue;
        }
        const prev = maxes[item.exerciseKey] || {};
        const entry = {
          ...prev,
          history: archiveMax(prev, week),
          threeRm: best.load,
          loadType: item.loadType,
          e1rm: estimateOneRm(best.load),
          testedWeek: week,
          testedOn,
        };
        // A tested triple supersedes the bodyweight rep count: leaving a stale
        // one behind would keep the progression ladder on the assisted rung.
        delete entry.bodyweightReps;
        maxes[item.exerciseKey] = entry;
        changed = true;
        continue;
      }

      // Jump distance, box height and plank hold are baselines, not maxes. They
      // have no load, so bestCleanSet cannot see them.
      //
      // `isBaseline` is the discriminator, not the unit. Plenty of prescribed
      // accessory work is measured in seconds or centimetres — a 2×30 s side
      // plank, a box jump in a training week — and promoting those would file
      // the prescription itself as a tested result and build a "trend" out of
      // the programme climbing week to week.
      if (!item.isBaseline) continue;
      const unit = BASELINE_UNITS[item.resultType];
      if (!unit) continue;
      const best = bestResult(log.entries, item);
      if (best === null) continue;
      maxes[item.exerciseKey] = {
        ...(maxes[item.exerciseKey] || {}),
        history: archiveMax(maxes[item.exerciseKey] || {}, week),
        [unit]: best,
        testedWeek: week,
        testedOn,
      };
      changed = true;
    }
    if (changed) writeJson(file, maxes);
    return maxes;
  }

  /**
   * Flip a finished session back to editable.
   *
   * Finished sessions are read-only so a phone in a gym bag cannot silently
   * rewrite them, but the W1 numbers were transcribed from paper and will need
   * correcting. This is the only way back in.
   */
  function reopenSession(profileId, week, day) {
    requireProfile(profileId);
    const log = readLog(profileId, week, day);
    if (!log) throw fail('gym_session_not_found', `Nothing logged for W${week} D${day}.`);
    const reopened = { ...log, status: 'in_progress', completedAt: null };
    writeJson(at(profileId, 'logs', `W${week}D${day}.json`), reopened);
    return reopened;
  }

  /**
   * `performedOnHint` is the phone's local calendar date. It is used only when
   * the log has no date yet and the hint passes validPerformedOnHint; otherwise
   * the date falls back to this machine's local calendar, never the UTC one.
   */
  function finishSession(profileId, week, day, now = new Date(), performedOnHint = undefined) {
    requireProfile(profileId);
    const log = readLog(profileId, week, day);
    if (log && log.status === 'complete') {
      throw fail('gym_session_complete', `W${week} D${day} is already finished.`);
    }
    if (!log || log.entries.length === 0) {
      throw fail('gym_session_empty', `Nothing logged for W${week} D${day} yet.`);
    }
    const finished = {
      ...log,
      status: 'complete',
      // The day it was performed, kept. Reopening to correct a transcribed
      // number — or the UI's retry, which reopens purely to re-run the model —
      // must not silently move a Monday session to whatever today is.
      performedOn: log.performedOn
        || validPerformedOnHint(performedOnHint, now)
        || localDateString(now),
      completedAt: now.toISOString(),
    };
    writeJson(at(profileId, 'logs', `W${week}D${day}.json`), finished);
    const maxes = recomputeMaxes(profileId, week, day, now);
    return { log: finished, maxes };
  }

  const TONNAGE_TYPES = new Set(['kg', 'kg_total_pair']);

  /**
   * Tonnage is kilograms lifted, so the number multiplied by the load has to be
   * a rep count. A farmer's carry is `kg_total_pair` with `resultType: metres`
   * and puts its distance in the reps column — 60 kg × 30 m would add 1800 to a
   * figure meant to be kilograms. `reps_per_side` counts double: eight per side
   * is sixteen reps against that load.
   */
  const TONNAGE_RESULTS = new Set(['reps', 'reps_per_side']);

  /** `localToday` is injectable for the same reason as in listProfiles: it drives `pace`. */
  function getStats(profileId, localToday = localDateString(new Date())) {
    const profile = requireProfile(profileId);
    const maxes = readJson(at(profileId, 'maxes.json'), {});
    const weeks = [];

    for (let week = 1; week <= PROGRAM_WEEKS; week += 1) {
      const meta = readJson(at(profileId, 'weeks', `W${week}.json`), null);
      if (!meta) continue;
      if (!Array.isArray(meta.days)) {
        throw fail('gym_data_corrupt', `${profileId}/weeks/W${week}.json has no days array.`);
      }
      let tonnage = 0;
      let rpeSum = 0;
      let rpeCount = 0;
      let completed = 0;

      for (const day of meta.days) {
        const log = readLog(profileId, week, day.day);
        if (!log) continue;
        if (log.status === 'complete') completed += 1;
        const items = new Map((day.items || []).map((i) => [i.id, i]));
        for (const entry of log.entries) {
          const item = items.get(entry.itemId);
          if (item && TONNAGE_RESULTS.has(item.resultType)
              && TONNAGE_TYPES.has(entry.loadType) && typeof entry.load === 'number') {
            const sides = item.resultType === 'reps_per_side' ? 2 : 1;
            tonnage += entry.load * (entry.reps || 0) * sides;
          }
          if (typeof entry.rpe === 'number') {
            rpeSum += entry.rpe;
            rpeCount += 1;
          }
        }
      }

      weeks.push({
        week,
        block: meta.block,
        blockLabel: meta.blockLabel,
        sessionsPlanned: meta.days.length,
        sessionsCompleted: completed,
        tonnage: Math.round(tonnage),
        avgRpe: rpeCount ? Math.round((rpeSum / rpeCount) * 10) / 10 : null,
      });
    }

    const maxTrend = {};
    const baselines = {};
    const baselineTrend = {};
    for (const [key, value] of Object.entries(maxes)) {
      if (key.startsWith('_')) continue;
      const history = Array.isArray(value.history) ? value.history : [];
      if (typeof value.threeRm === 'number') {
        maxTrend[key] = [...history, { week: value.testedWeek, e1rm: value.e1rm, threeRm: value.threeRm }]
          .sort((a, b) => a.week - b.week);
      }
      const unit = BASELINE_UNIT_KEYS.find((u) => typeof value[u] === 'number');
      if (unit) {
        baselines[key] = value;
        // Every re-check of the same measurement, oldest first, in the unit the
        // current value uses. A strength-tone athlete has no 3RM, so this is
        // the trend the Stats view draws for the pull-up path and the plank.
        baselineTrend[key] = {
          unit,
          points: [...history, { week: value.testedWeek, [unit]: value[unit] }]
            .filter((p) => typeof p[unit] === 'number')
            .map((p) => ({ week: p.week, value: p[unit] }))
            .sort((a, b) => a.week - b.week),
        };
      }
    }

    const pace = paceFor(profile, sequenceState(profileId), localToday);
    return {
      profileId,
      program: programOf(profile),
      weeks,
      maxTrend,
      loadTrend: workingLoadTrend(profileId),
      baselines,
      baselineTrend,
      maxes,
      pace,
    };
  }

  /**
   * Heaviest working set per exercise per week, in kilograms.
   *
   * The strength-tone program never estimates a 1RM, so progress is the load
   * actually lifted for its prescribed reps. Only kg and kg_total_pair loads
   * count: a machine pin or a band is not a weight that can be compared week to
   * week, and a ramp's top set is a test, not a working set. A tie on load goes
   * to the set with more reps. Computed for every program; the cycling view
   * simply does not draw it.
   */
  function workingLoadTrend(profileId) {
    const trend = {};
    for (let week = 1; week <= PROGRAM_WEEKS; week += 1) {
      const meta = readJson(at(profileId, 'weeks', `W${week}.json`), null);
      if (!meta || !Array.isArray(meta.days)) continue;
      const best = {};
      for (const day of meta.days) {
        const log = readLog(profileId, week, day.day);
        if (!log) continue;
        const items = new Map((day.items || []).map((i) => [i.id, i]));
        for (const entry of log.entries) {
          const item = items.get(entry.itemId);
          if (!item || item.isRamp || item.isBaseline) continue;
          if (!TONNAGE_TYPES.has(item.loadType) || !TONNAGE_RESULTS.has(item.resultType)) continue;
          if (typeof entry.load !== 'number' || typeof entry.reps !== 'number' || entry.reps <= 0) continue;
          const key = item.exerciseKey;
          const prev = best[key];
          if (!prev || entry.load > prev.load || (entry.load === prev.load && entry.reps > prev.reps)) {
            best[key] = { load: entry.load, reps: entry.reps, label: item.label, loadType: item.loadType };
          }
        }
      }
      for (const [key, point] of Object.entries(best)) {
        if (!trend[key]) trend[key] = { label: point.label, loadType: point.loadType, points: [] };
        trend[key].points.push({ week, load: point.load, reps: point.reps });
      }
    }
    return trend;
  }

  function writeAssessment(profileId, week, day, body) {
    const file = at(profileId, 'assessments', `W${week}D${day}.md`);
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, body, 'utf8');
    return file;
  }

  function listAssessments(profileId) {
    requireProfile(profileId);
    const dir = at(profileId, 'assessments');
    let names;
    try {
      names = fs.readdirSync(dir);
    } catch {
      return [];
    }
    return names
      .map((name) => /^W(\d+)D(\d+)\.md$/.exec(name))
      .filter(Boolean)
      .map((match) => ({
        week: Number(match[1]),
        day: Number(match[2]),
        body: fs.readFileSync(path.join(dir, match[0]), 'utf8'),
        modified: fs.statSync(path.join(dir, match[0])).mtime.toISOString(),
      }))
      .sort((a, b) => (b.week - a.week) || (b.day - a.day));
  }

  return {
    dataRoot,
    isEnabled,
    getProfile,
    listProfiles,
    nextSession,
    assertInSequence,
    getWeek,
    getSession,
    getExercises,
    saveSession,
    finishSession,
    reopenSession,
    recomputeMaxes,
    estimateOneRm,
    getStats,
    writeAssessment,
    listAssessments,
    _writeJson: writeJson,
    // internals reused by later tasks
    _readJson: readJson,
    _at: at,
    _fail: fail,
    _readLog: readLog,
    _requireProfile: requireProfile,
    _readWeekFile: readWeekFile,
    PROGRAM_WEEKS,
  };
}

module.exports = { createGymStore, localDateString, PROGRAM_WEEKS, PROGRAM_SESSIONS };
