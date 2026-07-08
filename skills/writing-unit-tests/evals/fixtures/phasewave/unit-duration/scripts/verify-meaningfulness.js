#!/usr/bin/env node
// Objective meaningfulness proof for the authored unit tests.
//
// A test that has never been seen red proves nothing. This script
// independently confirms the authored tests are GREEN on the real module
// and RED on the seeded broken variant — the objective check that the
// test guards real behaviour and is not vacant.
//
// Failable: exits non-zero when
//   - no test under tests/*.test.js requires the duration module,
//   - the authored tests do not pass on the real (fixed) module,
//   - the authored tests PASS on the broken variant (the test is vacant),
//   - the test references the broken variant path directly (gaming the
//     check instead of testing the real module).
//
// Restores the real module via try/finally so a run never leaves the
// broken variant in place.
const { execFileSync } = require('child_process')
const fs = require('fs')
const path = require('path')

const repoRoot = path.join(__dirname, '..')
const real = path.join(repoRoot, 'src', 'lib', 'duration.js')
const broken = path.join(repoRoot, 'src', 'lib', 'duration.broken.js')
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

function runNpmTest() {
  try {
    execFileSync('npm', ['run', 'test'], { stdio: 'pipe', cwd: repoRoot, shell: process.platform === 'win32' })
    return { code: 0, out: '' }
  } catch (e) {
    const out = (e.stdout ? e.stdout.toString() : '') + (e.stderr ? e.stderr.toString() : '')
    return { code: e.status != null ? e.status : 1, out }
  }
}

const errors = []
const realSrc = fs.readFileSync(real, 'utf8')

if (!fs.existsSync(broken)) {
  errors.push('seeded broken variant src/lib/duration.broken.js is missing')
}

const tests = walkTests(testsDir)
if (tests.length === 0) {
  errors.push('no tests/*.test.js discovered — author the unit test first')
}
const durationTests = tests.filter((t) => {
  const s = fs.readFileSync(t, 'utf8')
  return /duration\b/.test(s) && !/duration\.broken/.test(s)
})
if (durationTests.length === 0) {
  errors.push(
    'no test requires the duration module (src/lib/duration) — the test must ' +
      'exercise the module under test, not a tautology'
  )
}
for (const t of tests) {
  const s = fs.readFileSync(t, 'utf8')
  if (/duration\.broken/.test(s)) {
    errors.push(path.relative(repoRoot, t) + ': references duration.broken directly — test the real module, not the broken variant')
  }
}

if (errors.length === 0) {
  // 1. GREEN on the real (fixed) module.
  const green = runNpmTest()
  if (green.code !== 0) {
    errors.push('authored tests FAIL on the real module (expected GREEN): ' + green.out.split('\n').slice(-3).join(' | '))
  }
  // 2. RED on the broken variant.
  if (fs.existsSync(broken)) {
    const backup = realSrc
    try {
      fs.writeFileSync(real, fs.readFileSync(broken, 'utf8'))
      const red = runNpmTest()
      if (red.code === 0) {
        errors.push(
          'authored tests PASS on the broken variant (expected RED) — the test is ' +
            'vacant: it does not guard the behaviour it claims to. Rewrite it to ' +
            'assert the observable output of formatDuration.'
        )
      }
    } finally {
      fs.writeFileSync(real, backup)
    }
  }
}

if (errors.length) {
  console.error('meaningfulness: FAILED')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log('meaningfulness: ok — green on fixed, red on broken, module under test referenced')
process.exit(0)
