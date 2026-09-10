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
const PROGRAM_WEEKS = 12;

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

function createGymStore(dataRoot) {
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

  function requireProfile(id) {
    const profile = getProfile(id);
    if (!profile) {
      throw fail('gym_profile_required', `Unknown profile "${id}". Pass ?profile= with a known id.`);
    }
    return profile;
  }

  /** Calendar weeks elapsed since the start Monday, 1-based. PROGRAM_WEEKS+1 means maintenance. */
  function currentWeekFor(startDate, today = new Date()) {
    const parsed = new Date(`${startDate}T00:00:00Z`);
    if (Number.isNaN(parsed.getTime())) {
      throw fail('gym_data_corrupt', `profiles.json has an unusable startDate: ${JSON.stringify(startDate)}`);
    }
    const start = mondayOf(parsed);
    const elapsed = Math.floor((mondayOf(today) - start) / (7 * DAY_MS));
    return Math.min(Math.max(elapsed + 1, 1), PROGRAM_WEEKS + 1);
  }

  function weekBounds(startDate, week) {
    const startMs = new Date(`${startDate}T00:00:00Z`).getTime();
    if (Number.isNaN(startMs)) {
      throw fail('gym_data_corrupt', `profiles.json has an unusable startDate: ${JSON.stringify(startDate)}`);
    }
    const start = mondayOf(new Date(startMs)) + (week - 1) * 7 * DAY_MS;
    return { start: isoDate(start), end: isoDate(start + 6 * DAY_MS) };
  }

  function listProfiles(today = new Date()) {
    requireEnabled();
    const { profiles = [] } = readJson(at('profiles.json'), { profiles: [] });
    return profiles.map((p) => ({ ...p, currentWeek: currentWeekFor(p.startDate, today) }));
  }

  function readLog(profileId, week, day) {
    return readJson(at(profileId, 'logs', `W${week}D${day}.json`), null);
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

  function getWeek(profileId, week) {
    const profile = requireProfile(profileId);
    const data = readWeekFile(profileId, week);
    const days = data.days.map((day) => {
      const log = readLog(profileId, week, day.day);
      return {
        ...day,
        logStatus: log ? log.status : 'not_started',
        performedOn: log ? log.performedOn : null,
        loggedSets: log ? log.entries.length : 0,
      };
    });
    return { ...data, days, profileId, bounds: weekBounds(profile.startDate, week) };
  }

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
    };
  }

  function getExercises() {
    requireEnabled();
    return readJson(at('exercises.json'), {});
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
    if (Object.keys(point).length === 1) return history;   // nothing worth keeping
    history.push(point);
    return history;
  }

  /** Which key a baseline's result is stored under, chosen by the unit it is measured in. */
  const BASELINE_UNITS = { cm: 'cm', seconds: 'seconds' };

  function recomputeMaxes(profileId, week, day, now = new Date()) {
    const file = at(profileId, 'maxes.json');
    const maxes = readJson(file, {});
    const log = readLog(profileId, week, day);
    if (!log) return maxes;
    // A max was tested on the day the workout happened, not on the day the
    // finish button was pressed. Re-finishing a corrected session must not
    // redate it. Only an unfinished log can be missing performedOn.
    const testedOn = log.performedOn || now.toISOString().slice(0, 10);

    let changed = false;
    for (const item of dayItems(profileId, week, day)) {
      if (item.isRamp) {
        const best = bestCleanSet(log.entries, item);
        if (!best) continue;
        const prev = maxes[item.exerciseKey] || {};
        maxes[item.exerciseKey] = {
          ...prev,
          history: archiveMax(prev, week),
          threeRm: best.load,
          loadType: item.loadType,
          e1rm: estimateOneRm(best.load),
          testedWeek: week,
          testedOn,
        };
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

  function finishSession(profileId, week, day, now = new Date()) {
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
      performedOn: log.performedOn || now.toISOString().slice(0, 10),
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

  function getStats(profileId) {
    requireProfile(profileId);
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
    for (const [key, value] of Object.entries(maxes)) {
      if (key.startsWith('_')) continue;
      if (typeof value.threeRm === 'number') {
        const history = Array.isArray(value.history) ? value.history : [];
        maxTrend[key] = [...history, { week: value.testedWeek, e1rm: value.e1rm, threeRm: value.threeRm }]
          .sort((a, b) => a.week - b.week);
      }
      if (typeof value.cm === 'number' || typeof value.seconds === 'number') {
        baselines[key] = value;
      }
    }

    return { profileId, weeks, maxTrend, baselines, maxes };
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
    currentWeekFor,
    weekBounds,
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

module.exports = { createGymStore, PROGRAM_WEEKS };
