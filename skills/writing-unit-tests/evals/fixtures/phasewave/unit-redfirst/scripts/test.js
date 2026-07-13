#!/usr/bin/env node
// Red-first test discoverer. Discovers tests/**/*.test.js and runs
// each. Exits non-0 when none exist OR any fail. The red-first signal:
// in the pre-implementation state, the authored test requires
// src/lib/pomodoro-label (absent) -> the test process throws
// MODULE_NOT_FOUND naming the missing module -> discoverer reports
// red. That red IS the proof (it names the missing behaviour); the
// agent confirms the right reason and records the mode.
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
if (tests.length === 0) {
  console.error('test: FAILED — no tests discovered under tests/*.test.js')
  process.exit(1)
}

const errors = []
for (const t of tests) {
  try {
    execFileSync('node', [t], { stdio: 'inherit', cwd: repoRoot })
  } catch (e) {
    errors.push(path.relative(repoRoot, t) + ' exited non-zero')
  }
}
if (errors.length) {
  console.error('test: FAILED')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log('test: ok (' + tests.length + ' file(s))')
process.exit(0)