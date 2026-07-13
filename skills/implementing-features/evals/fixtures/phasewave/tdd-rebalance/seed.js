// Seed: audit_entries with a duplicate event_id for user-a (the
// server-side state the reconciliation behaves against). The
// duplicates come from the offline outbox replaying a mutation the
// server already accepted — that is the whole reason this behaviour
// lives at the store + client seam, not as a pure array helper.
module.exports = [
  { table: 'audit_entries', user_id: 'user-a', row: { id: 'a1', event_id: 'evt-1', occurred_at: '2026-07-10T10:00:00Z', payload: 'first' } },
  { table: 'audit_entries', user_id: 'user-a', row: { id: 'a2', event_id: 'evt-1', occurred_at: '2026-07-10T11:00:00Z', payload: 'second' } },
  { table: 'audit_entries', user_id: 'user-a', row: { id: 'a3', event_id: 'evt-2', occurred_at: '2026-07-10T09:00:00Z', payload: 'third' } },
  { table: 'audit_entries', user_id: 'user-b', row: { id: 'b1', event_id: 'evt-1', occurred_at: '2026-07-10T12:00:00Z', payload: 'user-b-own' } },
]