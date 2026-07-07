#!/usr/bin/env node
// Verifier: asserts the session order for the "recent sessions" view.
const { getTodaySessions } = require('../src/lib/session-list')

// Seed rows in arbitrary insertion order (the DB gives no ordering guarantee).
const rawRows = [
  { started_at: '2026-07-06T07:30:00Z', label: 'Email' },
  { started_at: '2026-07-06T09:00:00Z', label: 'Deep work' },
  { started_at: '2026-07-06T08:15:00Z', label: 'Standup' },
]

const errors = []

// Asserts the order getTodaySessions returns sessions in.
const dataOrder = getTodaySessions(rawRows).map((r) => r.started_at)
const expectedData = [
  '2026-07-06T07:30:00Z',
  '2026-07-06T08:15:00Z',
  '2026-07-06T09:00:00Z',
]
if (JSON.stringify(dataOrder) !== JSON.stringify(expectedData)) {
  errors.push(
    'session order: getTodaySessions returned ' +
      JSON.stringify(dataOrder) +
      '; expected ' +
      JSON.stringify(expectedData)
  )
}

if (errors.length) {
  console.error('test: FAILED')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log('test: ok')
process.exit(0)
