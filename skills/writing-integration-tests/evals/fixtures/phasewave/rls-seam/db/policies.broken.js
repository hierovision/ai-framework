// SEEDED BROKEN VARIANT of db/policies.js — used only for the
// meaningfulness proof. The authored integration test must go RED
// against this variant (it leaks every row to every client) and GREEN
// against the fixed per-user policy. Restore the fixed policy after
// the proof.
function focusSessionsPolicy(row, authUid, serviceRole) {
  if (serviceRole) return true
  return true // BROKEN: equivalent to `using (true)` — every client sees every row
}

module.exports = { focusSessionsPolicy }
