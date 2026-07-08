// Offline outbox: queues session mutations while offline and replays
// them to the supabase client on reconnect. The queue + client seam is
// what the integration test exercises (real outbox, faked transport).
// Persistence in the real app is IndexedDB; the runnable fixture uses
// an in-memory queue (persistence is a separate concern — see plan).
const queue = []

function queueSession(insert) {
  queue.push(insert)
  return queue.length
}

async function replay(client) {
  let flushed = 0
  for (const insert of queue) {
    await client.from('focus_sessions').insert(insert)
    flushed++
  }
  queue.length = 0 // clear after replay — every mutation flushed
  return flushed
}

function pending() {
  return queue.length
}

function _reset() {
  queue.length = 0
}

module.exports = { queueSession, replay, pending, _reset }
