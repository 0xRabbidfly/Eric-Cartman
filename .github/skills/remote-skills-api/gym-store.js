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
    } catch {
      return fallback;
    }
    try {
      return JSON.parse(raw);
    } catch (err) {
      throw fail('gym_data_corrupt', `${path.relative(dataRoot, file)} is not valid JSON: ${err.message}`);
    }
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
    const start = mondayOf(new Date(`${startDate}T00:00:00Z`));
    const elapsed = Math.floor((mondayOf(today) - start) / (7 * DAY_MS));
    return Math.min(Math.max(elapsed + 1, 1), PROGRAM_WEEKS + 1);
  }

  function weekBounds(startDate, week) {
    const start = mondayOf(new Date(`${startDate}T00:00:00Z`)) + (week - 1) * 7 * DAY_MS;
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
