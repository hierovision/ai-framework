// Share store (share-session slice). Pre-existing scaffold: loadSessions
// reads server rows through the client. The plan asks this pass to ADD
// a `shareSession(sessionId, recipientUid)` action — it is intentionally
// ABSENT in the red-first state so an authored integration test fails
// naturally with "store.shareSession is not a function" (the missing seam
// behaviour), which IS the red-first proof. The action is implemented in
// a later implementing-features pass, NOT in this authoring pass.
function createShareStore(client) {
  return {
    loadSessions() {
      return client.query('focus_sessions')
    },
    // TODO(feat-share-session): add shareSession(sessionId, recipientUid)
    // posting a share via the client and asserting the recipient's read
    // access appears at the seam.
  }
}
module.exports = { createShareStore }