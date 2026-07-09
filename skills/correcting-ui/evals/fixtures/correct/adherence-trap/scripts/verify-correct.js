#!/usr/bin/env node
// verify-correct.js — objective closure for the adherence-trap scenario.
// Real re-capture is DEFERRED; this is the objective check. It proves the
// candidate snapped border-radius to the $radius-lg token (closing the delta)
// while the adherence gate REJECTS the two weakening "wins": a magic px and a
// raw !important. A "win" that weakens the system is a blocker, never closure.
const fs = require('fs')
const os = require('os')
const path = require('path')
const { spawnSync } = require('child_process')

const HERE = __dirname
const ROOT = path.join(HERE, '..')
const errors = []
const SCHEMES = [
  process.env.CORRECT_SKILL_DIR,
  path.join(os.homedir(), '.config/opencode/skills/correcting-ui'),
  path.resolve(HERE, '..', '..', '..', '..', '..'),
].filter(Boolean)
const SKILL_DIR = SCHEMES.find((d) => d && fs.existsSync(path.join(d, 'scripts', 'check-adherence.js')))
if (!SKILL_DIR) { console.error('verify-correct: could not locate correcting-ui scripts — set CORRECT_SKILL_DIR'); process.exit(1) }
const adhereJs = path.join(SKILL_DIR, 'scripts', 'check-adherence.js')
const compareJs = path.join(SKILL_DIR, 'scripts', 'compare-evidence.js')

function run(label, args, expectOk) {
  const r = spawnSync('node', args, { encoding: 'utf8' })
  if ((r.status === 0) === expectOk) return r
  errors.push(`${label}: expected ${expectOk ? 'exit 0' : 'non-zero'} but got ${r.status}\n${r.stdout || r.stderr}`)
  return r
}

function main() {
  const cand = path.join(ROOT, 'src', 'styles.scss')
  const base = path.join(ROOT, 'src', 'baseline.styles.scss')
  const magicpx = path.join(ROOT, 'src', 'wrong-magicpx.styles.scss')
  const important = path.join(ROOT, 'src', 'wrong-important.styles.scss')
  const tokens = path.join(ROOT, 'tokens.json')
  const before = path.join(ROOT, 'evidence', 'baseline-evidence.json')
  const after = path.join(ROOT, 'evidence', 'after-good-evidence.json')

  // (1) candidate source adheres (no magic px, no new !important, flat specificity).
  run('check-adherence on candidate', [adhereJs, cand, '--baseline', base, '--system', 'vuetify-scss', '--tokens', tokens, '--target-selector', '.tag'], true)

  // (2) source-level: .tag border-radius snapped to the token ($radius-lg).
  const src = fs.readFileSync(cand, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '').replace(/^[ \t]*@(use|forward|import)[^;]*;[ \t]*\n/gm, '')
  const tag = src.match(/\.tag\s*\{([^}]*)\}/)
  if (!tag) errors.push('candidate did not edit the .tag rule (the matched-styles winner for border-radius)')
  else {
    const br = tag[1].match(/border-radius\s*:\s*([^;]+)/)
    if (!br) errors.push('.tag has no border-radius declaration after the edit')
    else if (br[1].trim() !== '$radius-lg') errors.push(`.tag border-radius = '${br[1].trim()}' but the system token is $radius-lg (12px) — snap to the token, not a magic px or force-win`)
    if (/\!important/.test(tag[1])) errors.push('.tag gained an !important — a raw cascade override; the system gate rejects it')
  }

  // (3) objective compare closes (border-radius -> 12px).
  run('compare-evidence good', [compareJs, before, after, '--target', 'css:.tag', '--expect', 'border-radius=12px'], true)

  // (4) FAILABLE: the two weakening "wins" are REJECTED by the adherence gate.
  run('check-adherence on magic-px bait (must be REJECTED)', [adhereJs, magicpx, '--baseline', base, '--system', 'vuetify-scss', '--tokens', tokens, '--target-selector', '.tag'], false)
  run('check-adherence on !important bait (must be REJECTED)', [adhereJs, important, '--baseline', base, '--system', 'vuetify-scss', '--tokens', tokens, '--target-selector', '.tag'], false)

  if (errors.length) { console.error('verify-correct: FAILED'); for (const e of errors) console.error('  - ' + e); process.exit(1) }
  console.log('verify-correct: ok — adherence-trap')
  console.log('  .tag border-radius -> $radius-lg (token); no magic px, no !important, specificity flat')
  console.log('  compare closed: border-radius -> 12px')
  console.log('  failable gate: magic-px + !important baits both REJECTED')
  console.log('  DEFERRED: real re-capture against the live component harness (no browser in harness)')
  process.exit(0)
}
main()