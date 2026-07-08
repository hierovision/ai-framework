#!/usr/bin/env node
// Objective meaningfulness proof for the authored outbox-replay
// integration test. Confirms the authored test is GREEN on the fixed
// outbox (replays all in order) and RED on the seeded broken outbox
// (drops all but the first queued mutation) — the objective check that
// the test guards real replay behaviour and is not vacant.
//
// Failable: exits non-zero when
//   - no test under tests/*.test.js exercises the outbox + client seam,
//   - the test references the broken outbox path directly (gaming),
//   - the authored test does not pass on the fixed outbox,
//   - the authored test PASSES on the broken outbox (vacant).
//
// Restores the fixed outbox via try/finally so a run never leaves the
// broken outbox in place.
const { execFileSync } = require('child_process')
const fs = require('fs')
const path = require('path')

const repoRoot = path.join(__dirname, '..')
const real = path.join(repoRoot, 'src', 'lib', 'outbox.js')
const broken = path.join(repoRoot, 'src', 'lib', 'outbox.broken.js')
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
  errors.push('seeded broken variant src/lib/outbox.broken.js is missing')
}

const tests = walkTests(testsDir)
if (tests.length === 0) {
  errors.push('no tests/*.test.js discovered — author the integration test first')
}
const seamTests = tests.filter((t) => {
  const s = fs.readFileSync(t, 'utf8')
  return (/replay|sync|startOffline/.test(s)) && /createClient|fake-client/.test(s)
})
if (seamTests.length === 0) {
  errors.push(
    'no test exercises the outbox + client seam (replay/sync + createClient) — ' +
      'an integration test must drive the real outbox/store through the faked client'
  )
}
for (const t of tests) {
  const s = fs.readFileSync(t, 'utf8')
  if (/outbox\.broken/.test(s)) {
    errors.push(path.relative(repoRoot, t) + ': references outbox.broken directly — test against the real outbox, not the broken variant')
  }
}

if (errors.length === 0) {
  const green = runNpmTest()
  if (green.code !== 0) {
    errors.push('authored test FAILS on the fixed outbox (expected GREEN): ' + green.out.split('\n').slice(-3).join(' | '))
  }
  if (fs.existsSync(broken)) {
    const backup = realSrc
    try {
      fs.writeFileSync(real, fs.readFileSync(broken, 'utf8'))
      const red = runNpmTest()
      if (red.code === 0) {
        errors.push(
          'authored test PASSES on the broken outbox (expected RED) — the test is vacant: ' +
            'it does not guard replay-all-in-order. Assert that every queued mutation reaches the client in order.'
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
console.log('meaningfulness: ok — green on fixed outbox, red on broken outbox, seam exercised')
process.exit(0)
