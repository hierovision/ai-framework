#!/usr/bin/env node
// Objective meaningfulness proof for the authored RLS integration test.
//
// A test that has never been seen red proves nothing. This script
// independently confirms the authored test is GREEN on the fixed
// per-user policy and RED on the seeded broken leaky policy — the
// objective check that the test guards real isolation and is not
// vacant. It also enforces the "no service-role bypass" discipline:
// asserting isolation through `serviceRole: true` mocks away the
// security behaviour under test (the cardinal-rule weakening applied to
// security).
//
// Failable: exits non-zero when
//   - no test under tests/*.test.js exercises the store + client seam,
//   - the test passes `serviceRole: true` anywhere (bypasses RLS),
//   - the test references the broken policy path directly (gaming),
//   - the authored test does not pass on the fixed policy,
//   - the authored test PASSES on the broken leaky policy (vacant).
//
// Restores the fixed policy via try/finally so a run never leaves the
// leaky policy in place.
const { execFileSync } = require('child_process')
const fs = require('fs')
const path = require('path')

const repoRoot = path.join(__dirname, '..')
const real = path.join(repoRoot, 'db', 'policies.js')
const broken = path.join(repoRoot, 'db', 'policies.broken.js')
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
  errors.push('seeded broken variant db/policies.broken.js is missing')
}

const tests = walkTests(testsDir)
if (tests.length === 0) {
  errors.push('no tests/*.test.js discovered — author the integration test first')
}
const seamTests = tests.filter((t) => {
  const s = fs.readFileSync(t, 'utf8')
  return /createFocusTimerStore|focus-timer-store/.test(s) && /createClient|fake-client/.test(s)
})
if (seamTests.length === 0) {
  errors.push(
    'no test exercises the store + client seam (createFocusTimerStore + createClient) — ' +
      'an integration test must drive the real store through the faked client'
  )
}
for (const t of tests) {
  const s = fs.readFileSync(t, 'utf8')
  if (/policies\.broken/.test(s)) {
    errors.push(path.relative(repoRoot, t) + ': references policies.broken directly — test against the real policy, not the broken variant')
  }
  if (/serviceRole\s*:\s*true|serviceRole\s*=\s*true/.test(s)) {
    errors.push(
      path.relative(repoRoot, t) + ': uses serviceRole: true — asserting isolation through a service-role bypass ' +
        'mocks away the security behaviour under test. Assert through the authenticated client as the user (authUid).'
    )
  }
}

if (errors.length === 0) {
  // 1. GREEN on the fixed per-user policy.
  const green = runNpmTest()
  if (green.code !== 0) {
    errors.push('authored test FAILS on the fixed per-user policy (expected GREEN): ' + green.out.split('\n').slice(-3).join(' | '))
  }
  // 2. RED on the broken leaky policy.
  if (fs.existsSync(broken)) {
    const backup = realSrc
    try {
      fs.writeFileSync(real, fs.readFileSync(broken, 'utf8'))
      const red = runNpmTest()
      if (red.code === 0) {
        errors.push(
          'authored test PASSES on the broken leaky policy (expected RED) — the test is vacant: ' +
            'it does not guard RLS isolation. Assert that the wrong user gets zero of the other user\'s rows.'
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
console.log('meaningfulness: ok — green on fixed policy, red on leaky policy, no service-role bypass')
process.exit(0)
