#!/usr/bin/env node
// Project verify script: integration test runner. Discovers
// tests/**/*.test.js and runs each as a child process. Exits 0 only if
// every discovered test passes AND at least one test was discovered.
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
  console.error('  - Author tests/<seam>.test.js (see AGENTS.md). An empty suite is red.')
  process.exit(1)
}

const errors = []
for (const t of tests) {
  try {
    execFileSync('node', [t], { stdio: 'inherit', cwd: repoRoot })
  } catch (e) {
    errors.push(path.relative(repoRoot, t))
  }
}

if (errors.length) {
  console.error('test: FAILED')
  for (const e of errors) console.error('  - ' + e + ' exited non-zero')
  process.exit(1)
}
console.log('test: ok (' + tests.length + ' file(s))')
process.exit(0)
