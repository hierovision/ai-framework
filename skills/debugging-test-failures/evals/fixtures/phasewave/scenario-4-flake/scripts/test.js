#!/usr/bin/env node
// Verifier: the "today" timeline shows sessions oldest-first (chronological).
const { getTodaySessions } = require('../src/lib/session-list')

const rawRows = [
  { started_at: '2026-07-06T09:00:00Z', label: 'Deep work' },
  { started_at: '2026-07-06T08:15:00Z', label: 'Standup' },
  { started_at: '2026-07-06T07:30:00Z', label: 'Email' },
]

const errors = []

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
      '; expected oldest-first (ascending started_at) ' +
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
