// Returns the user's sessions for the "recent sessions" view, newest-first
// (started_at descending), as Acceptance Criterion 1 of feat-session-sort
// specifies. The display renders rows in the order returned here.
function getTodaySessions(rawRows) {
  return [...rawRows].sort(
    (a, b) => (a.started_at < b.started_at ? 1 : a.started_at > b.started_at ? -1 : 0)
  )
}

module.exports = { getTodaySessions }