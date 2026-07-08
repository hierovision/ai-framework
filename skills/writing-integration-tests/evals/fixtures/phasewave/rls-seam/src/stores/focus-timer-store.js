// The real store (CommonJS stub of the Pinia store). The store is a
// thin passthrough over the supabase client — the RLS isolation lives
// at the DB + client seam, not here. The integration test wires a faked
// client (transport fake) to this real store and asserts the seam
// behaviour.
function createFocusTimerStore(client) {
  return {
    sessions: [],
    async loadSessions() {
      const { data, error } = await client.from('focus_sessions').select('*')
      if (error) throw error
      this.sessions = data
      return data
    },
  }
}

module.exports = { createFocusTimerStore }
