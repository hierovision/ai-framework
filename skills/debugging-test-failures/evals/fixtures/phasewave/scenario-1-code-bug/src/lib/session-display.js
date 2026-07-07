// Renders session rows as display strings for the timeline view. Takes
// the rows in the order the list module gives them — it does not re-order.
function formatSessionList(rows) {
  return rows.map((r) => `${r.started_at} · ${r.label}`)
}

module.exports = { formatSessionList }
