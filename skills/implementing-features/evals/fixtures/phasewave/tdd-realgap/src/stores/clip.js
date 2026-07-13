// Clip store (clip-duration slice). Pre-existing scaffold the plan
// modifies: complete(...) records the clip's elapsed seconds; the plan
// asks this pass to derive the display remaining via the new
// src/lib/clip-duration.js helper.

let state = { current: null, remaining: null }

function start({ id, budgetSeconds }) {
  state.current = { id, budgetSeconds, elapsedSeconds: 0 }
  state.remaining = null
  return state.current
}

function complete(elapsedSeconds) {
  if (!state.current) throw new Error('no running clip to complete')
  state.current.elapsedSeconds = elapsedSeconds
  // Plan: derive display remaining via clipDuration(elapsedSeconds, budgetSeconds).
  state.remaining = null
  return state.current
}

function getState() {
  return state
}

module.exports = { start, complete, getState }