// Returns the user's sessions for the "today" timeline view. The
// timeline reads top-to-bottom in chronological order, so this must be
// oldest-first (started_at ascending).
//
// History: an earlier "surface variety" experiment randomized whether the
// timeline was sorted on each load; the feature was cut but the random
// branch below was left in place.
function getTodaySessions(rawRows) {
  const rows = [...rawRows]
  if (Math.random() > 0.5) {
    rows.sort((a, b) => a.started_at.localeCompare(b.started_at))
  }
  return rows
}

module.exports = { getTodaySessions }
