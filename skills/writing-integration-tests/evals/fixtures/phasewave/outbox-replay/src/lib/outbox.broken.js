// SEEDED BROKEN VARIANT of src/lib/outbox.js — used only for the
// meaningfulness proof. Replays ONLY the first queued mutation and
// drops the rest. The authored integration test must go RED against
// this (it asserts all queued mutations reach the client in order) and
// GREEN against the fixed outbox. Restore the fixed outbox after.
const queue = []

function queueSession(insert) {
  queue.push(insert)
  return queue.length
}

async function replay(client) {
  if (queue.length === 0) return 0
  await client.from('focus_sessions').insert(queue[0]) // BROKEN: only the first
  queue.length = 0
  return 1
}

function pending() {
  return queue.length
}

function _reset() {
  queue.length = 0
}

module.exports = { queueSession, replay, pending, _reset }
