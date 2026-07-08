// Real store stub. startOffline queues a session mutation to the
// outbox; sync replays the outbox to the client on reconnect. The
// outbox + client seam is what the integration test exercises.
const outbox = require('../lib/outbox')

function createFocusTimerStore() {
  return {
    async startOffline(insert) {
      return outbox.queueSession(insert)
    },
    async sync(client) {
      return outbox.replay(client)
    },
    pending() {
      return outbox.pending()
    },
  }
}

module.exports = { createFocusTimerStore }
