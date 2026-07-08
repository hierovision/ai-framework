// Pre-seeded focus_sessions for the RLS integration test. Seeding is
// pre-provided so the test never needs a service-role bypass to set up
// rows — asserting isolation through the service role mocks away the
// security behaviour under test.
module.exports = [
  { id: 's1', user_id: 'user-a', duration_seconds: 1500, started_at: '2026-07-06T09:00:00Z', status: 'completed' },
  { id: 's2', user_id: 'user-a', duration_seconds: 600, started_at: '2026-07-06T10:00:00Z', status: 'completed' },
  { id: 's3', user_id: 'user-b', duration_seconds: 300, started_at: '2026-07-06T09:30:00Z', status: 'completed' },
]
