// Returns the user's sessions for the "recent sessions" view, newest-first
// (started_at descending) so the latest work is at the top.
function getTodaySessions(rawRows) {
  return [...rawRows].sort((a, b) => b.started_at.localeCompare(a.started_at))
}

module.exports = { getTodaySessions }
