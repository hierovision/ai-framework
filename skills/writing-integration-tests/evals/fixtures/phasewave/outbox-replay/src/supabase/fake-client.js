// Faked supabase transport at the outermost boundary. Records inserts
// in the order received so the integration test can assert replay
// ordering. The outbox + store under test are real; the transport is
// the only fake.
function createClient() {
  const inserted = []
  return {
    from(table) {
      return {
        insert(row) {
          inserted.push({ table, row })
          return Promise.resolve({ data: [row], error: null })
        },
      }
    },
    _inserted: inserted,
  }
}

module.exports = { createClient }
