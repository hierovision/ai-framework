// Returns the user's sessions for the "recent sessions" view. SHOULD be
// newest-first (started_at descending) per feat-session-sort, but this
// version still returns rows in the order they arrive (unsorted), which
// is the latent defect the test was meant to catch.
function getTodaySessions(rawRows) {
  return [...rawRows]
}

module.exports = { getTodaySessions }