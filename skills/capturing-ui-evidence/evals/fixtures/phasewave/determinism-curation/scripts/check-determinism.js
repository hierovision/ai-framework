#!/usr/bin/env node
// check-determinism.js — structural grep of the skill's capture.mjs for the
// determinism knobs that a nondeterministic-capture regression would remove.
// No live browser; this checks the SOURCE so it stays green even where
// Playwright is absent (matching the e2e real-browser-deferral precedent).
//
//   node scripts/check-determinism.js
//
// Failable: exits non-zero when any required knob is absent, OR when a
// forbidden sleep (`waitForTimeout`) is present — that is the canonical
// `debugging-test-failures` class-4 flake suspect authored INTO the capture
// path, and a fixed interval is the opposite of a condition wait.
const fs = require('fs')
const os = require('os')
const path = require('path')

const SCHEMES = [
  process.env.CAPTURE_SKILL_DIR,
  path.join(os.homedir(), '.config/opencode/skills/capturing-ui-evidence'),
  path.resolve(__dirname, '..', '..', '..', '..', '..', 'skills', 'capturing-ui-evidence'),
].filter(Boolean)
const SKILL_DIR = SCHEMES.find((d) => fs.existsSync(path.join(d, 'scripts', 'capture.mjs')))
if (!SKILL_DIR) { console.error('check-determinism: could not locate capture.mjs — set CAPTURE_SKILL_DIR'); process.exit(1) }

const src = fs.readFileSync(path.join(SKILL_DIR, 'scripts', 'capture.mjs'), 'utf8')

const required = [
  // animations + transitions disabled in-process (the freeze CSS)
  { re: /animation\s*:\s*none/, label: 'animation: none (freeze transient motion)' },
  { re: /transition\s*:\s*none/, label: 'transition: none (freeze transient motion)' },
  { re: /reducedMotion/, label: 'emulateMedia reducedMotion (UA-level motion freeze)' },
  // fonts + load awaited as a CONDITION, never a blind timeout
  { re: /document\.fonts\.ready|fonts\.ready/, label: 'document.fonts.ready awaited (font swap is async)' },
  { re: /waitForFunction/, label: 'waitForFunction (a layout-stability condition poll, not a sleep)' },
  { re: /networkidle/, label: 'waitUntil networkidle (wait on load as a condition)' },
  // viewport + device scale pinned
  { re: /deviceScaleFactor/, label: 'deviceScaleFactor pinned (scale would perturb computed + screenshots)' },
  { re: /setViewportSize|viewport\s*:\s*\{/, label: 'viewport pinned per run' },
]
const forbidden = [
  { re: /waitForTimeout\s*\(/, label: 'waitForTimeout (a blind sleep — the class-4 flake; replace with a condition wait)' },
]

const errors = []
for (const r of required) if (!r.re.test(src)) errors.push('missing determinism knob: ' + r.label)
for (const r of forbidden) if (r.re.test(src)) errors.push('forbidden in capture path: ' + r.label)

if (errors.length) {
  console.error('check-determinism: FAILED')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log('check-determinism: ok — animations frozen, fonts/load awaited, layout waited on a condition (no waitForTimeout), viewport + scale pinned')
process.exit(0)