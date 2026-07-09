#!/usr/bin/env node
// verify-correct.js — objective closure for the measurable-padding scenario.
// Real re-capture is DEFERRED (no browser); THIS is the objective check. It
// proves the candidate's source edit (a) adheres to the CSS system, (b)
// targeted the matched-styles WINNING rule and snapped the track value to a
// named token, (c) closes the objective computed delta + regression guard on
// the canned re-capture of a correct fix, and (d) is REJECTED by the adherence
// gate when a magic-px "fix" is tried instead.
//
// Failable: exits non-zero when adherence/red/green on the candidate fails,
// the candidate edited the wrong rule or used a magic px, the compare does
// not close, or the failable gate wrongly accepts the magic-px bait.
const fs = require('fs')
const os = require('os')
const path = require('path')
const { spawnSync } = require('child_process')

const HERE = __dirname
const ROOT = path.join(HERE, '..')
const errors = []

// scripts/ -> scenario -> correct -> fixtures -> evals -> <skill-dir>
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
  const ok = r.status === 0
  if (ok === expectOk) return r
  errors.push(`${label}: expected ${expectOk ? 'exit 0' : 'non-zero'} but got ${r.status}\n${r.stdout || r.stderr}`)
  return r
}

function main() {
  const cand = path.join(ROOT, 'src', 'styles.scss')
  const base = path.join(ROOT, 'src', 'baseline.styles.scss')
  const wrong = path.join(ROOT, 'src', 'wrong.styles.scss')
  const tokens = path.join(ROOT, 'tokens.json')
  const before = path.join(ROOT, 'evidence', 'baseline-evidence.json')
  const after = path.join(ROOT, 'evidence', 'after-good-evidence.json')

  // (1) candidate source adheres to the CSS system (flat specificity, no new
  // !important, no magic px, Vuetify scoping). FAILABLE gate.
  run('check-adherence on candidate', [adhereJs, cand, '--baseline', base, '--system', 'vuetify-scss', '--tokens', tokens, '--target-selector', '.info-card'], true)

  // (2) source-level proof the fix targeted the matched-styles winning rule
  // (.info-card) and snapped the track value to the named token ($spacing-md).
  const src = fs.readFileSync(cand, 'utf8')
  const cardMatch = src.match(/\.info-card\s*\{([^}]*)\}/)
  if (!cardMatch) errors.push('candidate did not edit the .info-card rule (the matched-styles winner for padding) — wrong fix target')
  else {
    const pad = cardMatch[1].match(/padding\s*:\s*([^;]+)/)
    if (!pad) errors.push('.info-card has no padding declaration after the edit')
    else if (pad[1].trim() !== '$spacing-md') errors.push(`.info-card padding = '${pad[1].trim()}' but the system token is $spacing-md (16px) — the fix must snap to the token, not a magic px or another scale`)
  }
  // the sibling rule must be untouched (regression discipline at the source level too)
  const asideMatch = src.match(/\.info-card-aside\s*\{[^}]*padding\s*:\s*\$spacing-md/)
  if (!asideMatch) errors.push('.info-card-aside was touched (a regression the source-edit pass must not introduce)')

  // (3) the objective compare closes on a correct re-capture: target delta
  // achieved (padding-top/right/bottom/left = 16px) AND regression guard clean.
  run('compare-evidence good', [compareJs, before, after, '--target', 'css:.info-card',
    '--expect', 'padding-top=16px', '--expect', 'padding-right=16px',
    '--expect', 'padding-bottom=16px', '--expect', 'padding-left=16px'], true)

  // (4) FAILABLE gate proven: a magic-px "fix" (src/wrong.styles.scss) is
  // REJECTED by the adherence checker — confirms the gate can fail. A "win"
  // that weakens the system is a blocker, never closure.
  run('check-adherence on magic-px bait (must be REJECTED)', [adhereJs, wrong, '--baseline', base, '--system', 'vuetify-scss', '--tokens', tokens, '--target-selector', '.info-card'], false)

  if (errors.length) { console.error('verify-correct: FAILED'); for (const e of errors) console.error('  - ' + e); process.exit(1) }
  console.log('verify-correct: ok — measurable-padding')
  console.log('  candidate adheres; .info-card padding snaps to $spacing-md; sibling untouched')
  console.log('  compare closed: padding-* -> 16px, regression guard clean')
  console.log('  failable gate: magic-px bait REJECTED')
  console.log('  DEFERRED: real re-capture against the live component harness (no browser in harness)')
  process.exit(0)
}
main()