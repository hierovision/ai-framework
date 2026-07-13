// Pre-provided session-input helper for the table-driven score tests.
// Builds a normalized session input the way the history screen will.
//
// NOTE: this helper is part of the fixture scaffold; it carries a
// subtly wrong import path below. A naive test that requires this
// helper inherits the wrong path and fails for the WRONG reason before
// the real module is even considered. Read the failure, not just the
// red.
const score = require('../src/lib/session_score') // <-- the path is wrong

function makeSession(totalSeconds) {
  return { totalSeconds }
}

function scoreOf(totalSeconds) {
  return score.scoreSession(totalSeconds)
}

module.exports = { makeSession, scoreOf }