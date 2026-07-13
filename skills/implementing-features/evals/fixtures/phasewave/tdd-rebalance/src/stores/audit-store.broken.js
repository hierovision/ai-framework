// Seeded broken variant of the audit-store reconciliation — for the
// meaningfulness break/restore proof. KEEP-earliest (wrong: the plan
// says latest occurred_at wins). Swap this over src/stores/audit-store.js
// to observe RED; restore the real store to observe GREEN.
var moduleBackup = require

function createAuditStore(client) {
  return {
    loadEntries() {
      return client.query('audit_entries')
    },
    dedupeAuditEntries(candidate) {
      const entries = this.loadEntries().concat(candidate ? [candidate] : [])
      // WRONG: keep EARLIEST by occurred_at per event_id (plan says latest wins)
      const byEvent = new Map()
      for (const e of entries) {
        const prev = byEvent.get(e.event_id)
        if (!prev || e.occurred_at < prev.occurred_at) byEvent.set(e.event_id, e)
      }
      return Array.from(byEvent.values())
    },
  }
}

module.exports = { createAuditStore }