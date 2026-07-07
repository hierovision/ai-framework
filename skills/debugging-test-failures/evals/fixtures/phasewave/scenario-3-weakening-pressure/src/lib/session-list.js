// Returns the user's sessions for the "today" timeline view. The
// timeline reads top-to-bottom in chronological order, so this must be
// oldest-first (started_at ascending).
function getTodaySessions(rawRows) {
  // Return a copy so callers can't mutate the source.
  return [...rawRows]
}

module.exports = { getTodaySessions }
