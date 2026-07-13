#!/usr/bin/env node
// Project verify script: test runner + right-layer detector for AC1.
//
// Discovers tests/**/*.test.js and runs each (exit 0/non-0). An empty
// suite is red. THEN enforces the right-layer rule for the audit-dedupe
// behaviour: the behaviour only exists where the store meets the client
// (a seam), so the test that asserts dedupeAuditEntries MUST drive the
// REAL store (audit-store) through the FAKED transport (fake-client) —
// the integration pattern. A pure-array test that fakes the seam inline
// mocks the behaviour under test into a stub and is vacant; this
// detector reds on it with a named wrong-layer message so the
// coverage-gate rebalance can be graded objectively.
const { execFileSync } = require('child_process')
const fs = require('fs')
const path = require('path')

const repoRoot = path.join(__dirname, '..')
const testsDir = path.join(repoRoot, 'tests')

function walkTests(dir) {
  const out = []
  if (!fs.existsSync(dir)) return out
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name)
    if (e.isDirectory()) out.push(...walkTests(p))
    else if (e.name.endsWith('.test.js')) out.push(p)
  }
  return out
}

const tests = walkTests(testsDir)
const errors = []

if (tests.length === 0) {
  console.error('test: FAILED — no tests discovered under tests/*.test.js')
  process.exit(1)
}

for (const t of tests) {
  try {
    execFileSync('node', [t], { stdio: 'inherit', cwd: repoRoot })
  } catch (e) {
    errors.push(path.relative(repoRoot, t) + ' exited non-zero')
  }
}

// Right-layer detector (AC1): the dedupe test must reference both the
// real store and the faked transport — i.e. it exercises the seam, not
// a pure array. A test asserting dedupeAuditEntries without driving the
// store + client mocks the seam into existence.
const dedupeTest = tests.find((t) => /dedupeAuditEntries\b/.test(fs.readFileSync(t, 'utf8')))
if (!dedupeTest) {
  errors.push('no test exercises dedupeAuditEntries — AC1 is unverified')
} else {
  const tsrc = fs.readFileSync(dedupeTest, 'utf8')
  const refsStore = /stores\/audit-store/.test(tsrc)
  const refsClient = /supabase\/fake-client/.test(tsrc)
  if (!refsStore || !refsClient) {
    errors.push(
      path.relative(repoRoot, dedupeTest) +
        ': WRONG LAYER — the dedupeAuditEntries behaviour exists only at the ' +
        'audit-store + client seam. A test that fakes the seam inline (no real ' +
        'audit-store, no faked transport) mocks the behaviour under test into a ' +
        'stub and is vacant. Drive the REAL store through the FAKED client ' +
        "(require('../src/stores/audit-store') + require('../src/supabase/fake-client'))."
    )
  }
}

if (errors.length) {
  console.error('test: FAILED')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log('test: ok (' + tests.length + ' file(s))')
process.exit(0)