// Renders session rows as display strings, in the order the list module
// gives them (no re-ordering here).
function formatSessionList(rows) {
  return rows.map((r) => `${r.started_at} · ${r.label}`)
}

module.exports = { formatSessionList }
