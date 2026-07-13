// Focus timer store (session-score slice). Pre-existing scaffold the
// plan modifies: the store records a completed focus session; the plan
// asks this pass to derive and expose a productivity `score` from the
// elapsed seconds via the new src/lib/session-score.js module.
//
// CommonJS stub so the verify scripts execute in-process.

let state = {
  current: null, // { id, activity, elapsedSeconds }
  score: null,
}

function start({ id, activity }) {
  state.current = { id, activity, elapsedSeconds: 0 }
  state.score = null
  return state.current
}

function complete(elapsedSeconds) {
  if (!state.current) throw new Error('no running session to complete')
  state.current.elapsedSeconds = elapsedSeconds
  // Plan: derive the session's productivity score via scoreSession(...).
  // (Replaced by the implement pass — the direct stub below is the
  // pre-feature state; do not leave it scoring null after the pass.)
  state.score = null
  return state.current
}

function getState() {
  return state
}

module.exports = { start, complete, getState }