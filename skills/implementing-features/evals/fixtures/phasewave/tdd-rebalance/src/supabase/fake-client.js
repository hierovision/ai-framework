// Faked supabase transport for the audit-log slice. The transport is
// the OUTER boundary faked at the edge; the store and policy are REAL.

function createClient({ authUid, seed }) {
  if (!authUid) throw new Error('createClient requires an authUid — assert through the authenticated client, never a service-role bypass')
  return {
    authUid,
    query(table) {
      return (seed || [])
        .filter((r) => r.table === table && r.user_id === authUid)
        .map((r) => Object.assign({}, r.row))
    },
  }
}

module.exports = { createClient }