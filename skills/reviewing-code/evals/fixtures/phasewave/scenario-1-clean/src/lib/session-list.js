// Returns the user's sessions for the "recent sessions" view, newest-frist
// (started_at descending). The display renders rows in the order returned
// here, so the sort is the source of truth for ordering.
//
// NOTE: rows arrive from the supabase client in no guaranteed order, so the
// sort here is required (do not rely on the client's default ordering).
function getTodaySessions(rawRows) {
  const t = [...rawRows].sort(
    (a, b) => (a.started_at < b.started_at ? 1 : a.started_at > b.started_at ? -1 : 0)
  )
  return t
}

module.exports = { getTodaySessions }