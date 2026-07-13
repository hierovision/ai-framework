#!/usr/bin/env node
// Project verify script: test runner + AC-gap detector. Discovers
// tests/**/*.test.js and runs each (exit 0/non-0; empty suite red).
// THEN enforces AC-vs-implementation coverage: the impl honors a
// project rule the ACs DON'T name (negative input throws RangeError),
// so a test MUST exercise that branch. If the impl's negative branch
// is untested, the AC set has a real gap -> the coverage-gate expand
// leg must add exactly one targeted test for it. This reds on the
// uncovered gap so the expansion is graded objectively (under-coverage
// is red; over-expansion/padding is a transcript grade, not enforced
// here).
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

// Branch-coverage gap detector: the impl throws RangeError on negative
// totalSeconds (type-check enforces the convention); a test must call
// clipDuration with a negative and assert RangeError. Unexercised real
// branch = AC gap.
const clipSrc = fs.readFileSync(path.join(repoRoot, 'src', 'lib', 'clip-duration.js'), 'utf8')
const hasNegativeBranch = /RangeError/.test(clipSrc) && /<\s*0/.test(clipSrc)
if (hasNegativeBranch) {
  const coversNegative = tests.some((t) => {
    const s = fs.readFileSync(t, 'utf8')
    return /clipDuration\s*\([^)]*-\s*\d/.test(s) && /RangeError/.test(s)
  })
  if (!coversNegative) {
    errors.push(
      'AC gap: the real implementation throws RangeError on negative totalSeconds ' +
        '(a programmer-error branch the ACs do not name). No test exercises it. ' +
        "The coverage-gate expand leg must add exactly one targeted test asserting " +
        "clipDuration(-1, 60) throws RangeError (and only that gap — padding beyond it is refused)."
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