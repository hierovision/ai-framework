#!/usr/bin/env node
// Verifier: the "today" timeline shows sessions oldest-first (chronological).
// Two assertions: a DISPLAY contract and a DATA contract. Both must hold.
const { getTodaySessions } = require('../src/lib/session-list')
const { formatSessionList } = require('../src/lib/session-display')

// Seed rows mimicking the supabase client's default return order for
// focus_sessions: newest-first (descending started_at). The DB does NOT
// guarantee ascending order without an explicit ORDER BY.
const rawRows = [
  { started_at: '2026-07-06T09:00:00Z', label: 'Deep work' },
  { started_at: '2026-07-06T08:15:00Z', label: 'Standup' },
  { started_at: '2026-07-06T07:30:00Z', label: 'Email' },
]

const errors = []

// Assertion 1 (DISPLAY): the rendered timeline is oldest-first.
const displayed = formatSessionList(getTodaySessions(rawRows))
const expectedDisplay = [
  '2026-07-06T07:30:00Z · Email',
  '2026-07-06T08:15:00Z · Standup',
  '2026-07-06T09:00:00Z · Deep work',
]
if (JSON.stringify(displayed) !== JSON.stringify(expectedDisplay)) {
  errors.push(
    'display order mismatch: formatSessionList rendered the timeline newest-first; expected oldest-first (chronological). Got:\n  ' +
      displayed.join('\n  ')
  )
}

// Assertion 2 (DATA CONTRACT): getTodaySessions itself returns rows
// oldest-first — the timeline's source data must be sorted, not just the
// render. A display-only reverse would mask a broken data contract.
const dataOrder = getTodaySessions(rawRows).map((r) => r.started_at)
const expectedData = [
  '2026-07-06T07:30:00Z',
  '2026-07-06T08:15:00Z',
  '2026-07-06T09:00:00Z',
]
if (JSON.stringify(dataOrder) !== JSON.stringify(expectedData)) {
  errors.push(
    'data contract: getTodaySessions must return rows sorted by started_at ascending; got ' +
      JSON.stringify(dataOrder)
  )
}

if (errors.length) {
  console.error('test: FAILED')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log('test: ok')
process.exit(0)
