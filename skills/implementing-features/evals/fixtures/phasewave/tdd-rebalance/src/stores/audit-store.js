// Audit store (audit-log slice). The store is a REAL collaborator;
// only the supabase transport is faked at the edge. Pre-existing
// `loadEntries()` reads server rows through the client. The plan asks
// this pass to ADD `dedupeAuditEntries(candidate)` that reconciles a
// candidate mutation against the server-side entries already loaded
// via the client (latest `occurred_at` wins per `event_id`). It is a
// STORE action precisely because the reconciliation only has meaning
// against the server rows the client returns — a pure-array helper
// would assert against a stub, not the reconciled server state.

function createAuditStore(client) {
  return {
    loadEntries() {
      return client.query('audit_entries')
    },
    // TODO(feat-audit-log-dedupe): add dedupeAuditEntries(candidate)
    // reconciling candidate against loadEntries() by event_id, latest
    // occurred_at wins. Replaces the TODO at implement time.
  }
}

module.exports = { createAuditStore }