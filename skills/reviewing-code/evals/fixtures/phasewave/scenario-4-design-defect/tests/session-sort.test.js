// Verifier test for feat-session-sort. Asserts the descending order.
const { getTodaySessions } = require('../src/lib/session-list')

const rawRows = [
  { started_at: '2026-07-06T08:15:00Z', label: 'Standup' },
  { started_at: '2026-07-06T09:00:00Z', label: 'Deep work' },
  { started_at: '2026-07-06T07:30:00Z', label: 'Email' },
]

const errors = []

const sorted = getTodaySessions(rawRows)
const expectedOrder = [
  '2026-07-06T09:00:00Z',
  '2026-07-06T08:15:00Z',
  '2026-07-06T07:30:00Z',
]
if (JSON.stringify(sorted.map((r) => r.started_at)) !== JSON.stringify(expectedOrder)) {
  errors.push(
    'getTodaySessions must return rows sorted descending (newest-first); got ' +
      JSON.stringify(sorted.map((r) => r.started_at))
  )
}

if (errors.length) {
  console.error('test: FAILED')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log('test: ok')
process.exit(0)