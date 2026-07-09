// Verifier tests for feat-session-sort. Asserts the descending order and
// that the display renders the order returned (no re-order).
const { getTodaySessions } = require('../src/lib/session-list')
const { formatSessionList } = require('../src/lib/session-display')

const rawRows = [
  { started_at: '2026-07-06T08:15:00Z', label: 'Standup' },
  { started_at: '2026-07-06T09:00:00Z', label: 'Deep work' },
  { started_at: '2026-07-06T07:30:00Z', label: 'Email' },
]

const errors = []

// AC1: getTodaySessions returns rows descending (newest-first).
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

// AC2: formatSessionList renders rows in the order returned (no re-order).
const displayed = formatSessionList(sorted)
const expectedDisplay = [
  '2026-07-06T09:00:00Z · Deep work',
  '2026-07-06T08:15:00Z · Standup',
  '2026-07-06T07:30:00Z · Email',
]
if (JSON.stringify(displayed) !== JSON.stringify(expectedDisplay)) {
  errors.push('display must render in the order returned; got ' + JSON.stringify(displayed))
}

if (errors.length) {
  console.error('test: FAILED')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log('test: ok')
process.exit(0)