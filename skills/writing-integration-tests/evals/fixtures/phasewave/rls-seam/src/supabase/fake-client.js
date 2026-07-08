// Faked supabase transport at the outermost boundary. Enforces RLS by
// applying the policy from db/policies.js to the seeded rows, given the
// client's auth uid. This is the transport fake — the store under test
// is real and is wired to this client at the seam. Real collaborators
// where feasible; the transport is the only fake.
const { focusSessionsPolicy } = require('../../db/policies')

function createClient({ authUid, serviceRole = false, seed = [] }) {
  return {
    from(table) {
      return {
        select() {
          if (table !== 'focus_sessions') {
            return Promise.resolve({ data: [], error: { message: 'unknown table ' + table } })
          }
          const visible = seed.filter((row) => focusSessionsPolicy(row, authUid, serviceRole))
          return Promise.resolve({ data: visible, error: null })
        },
      }
    },
  }
}

module.exports = { createClient }
