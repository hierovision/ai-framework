// Renders the sessions in the order getTodaySessions returns them. The
// display never re-orders — the list module owns ordering.
function formatSessionList(sessions) {
  return sessions.map((s) => `${s.started_at} · ${s.label}`)
}

module.exports = { formatSessionList }