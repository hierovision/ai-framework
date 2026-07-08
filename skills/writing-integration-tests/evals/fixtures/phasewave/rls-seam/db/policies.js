// RLS policy for focus_sessions, expressed as a JS predicate the fake
// client applies. This mirrors the SQL policy in db/schema.sql:
//   using (auth.uid() = user_id)
// serviceRole bypasses RLS (admin / seeding only) — the integration
// test must NOT use serviceRole to assert isolation (that mocks away the
// security behaviour under test).
function focusSessionsPolicy(row, authUid, serviceRole) {
  if (serviceRole) return true
  return authUid === row.user_id
}

module.exports = { focusSessionsPolicy }
