#!/usr/bin/env node
// verify-correct.js — objective closure for the regression-guard scenario.
// Real re-capture is DEFERRED; this is the objective check. It proves the
// candidate fixed .hero padding (target delta) AND left the sibling .sidebar
// byte-identical (regression guard clean). The teaching point: a fix that hits
// the target but shifts a sibling passes the adherence gate (every value a
// token) yet is caught by the regression guard — closure is BOTH together.
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
const strip = (s) => s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1').replace(/^[ \t]*@(use|forward|import)[^;]*;[ \t]*\n/gm, '')

function run(label, args, expectOk) {
  const r = spawnSync('node', args, { encoding: 'utf8' })
  if ((r.status === 0) === expectOk) return r
  errors.push(`${label}: expected ${expectOk ? 'exit 0' : 'non-zero'} but got ${r.status}\n${r.stdout || r.stderr}`)
  return r
}

function main() {
  const cand = path.join(ROOT, 'src', 'styles.scss')
  const base = path.join(ROOT, 'src', 'baseline.styles.scss')
  const wrong = path.join(ROOT, 'src', 'wrong.styles.scss')
  const tokens = path.join(ROOT, 'tokens.json')
  const before = path.join(ROOT, 'evidence', 'baseline-evidence.json')
  const afterGood = path.join(ROOT, 'evidence', 'after-good-evidence.json')
  const afterBad = path.join(ROOT, 'evidence', 'after-bad-evidence.json')

  // (1) candidate source adheres (flat specificity, no new !important, tokens).
  run('check-adherence on candidate', [adhereJs, cand, '--baseline', base, '--system', 'vuetify-scss', '--tokens', tokens, '--target-selector', '.hero'], true)

  // (2) source-level: .hero padding snapped to $spacing-md; .sidebar + .layout untouched.
  const src = strip(fs.readFileSync(cand, 'utf8'))
  const hero = src.match(/\.hero\s*\{([^}]*)\}/)
  const pad = hero ? hero[1].match(/padding\s*:\s*([^;]+)/) : null
  if (!pad) errors.push('.hero has no padding declaration after the edit')
  else if (pad[1].trim() !== '$spacing-md') errors.push(`.hero padding = '${pad[1].trim()}' but the token is $spacing-md`)
  const candClean = src.replace(/\s+/g, ' ').trim()
  const baseClean = strip(fs.readFileSync(base, 'utf8')).replace(/\s+/g, ' ').trim()
  if (/\.sidebar\s*\{/.test(src)) {
    const sbCand = (src.match(/\.sidebar\s*\{([^}]*)\}/) || [])[1] || ''
    const sbBase = (strip(fs.readFileSync(base, 'utf8')).match(/\.sidebar\s*\{([^}]*)\}/) || [])[1] || ''
    if (sbCand !== sbBase) errors.push('.sidebar rule was touched — a sibling must NOT shift; scope the fix to .hero only')
  }
  if (/\.layout\s*\{/.test(src)) {
    const laCand = (src.match(/\.layout\s*\{([^}]*)\}/) || [])[1] || ''
    const laBase = (strip(fs.readFileSync(base, 'utf8')).match(/\.layout\s*\{([^}]*)\}/) || [])[1] || ''
    if (laCand !== laBase) errors.push('.layout (shared parent) was touched — edits there shift the sibling .sidebar; scope to .hero')
  }

  // (3) objective compare on a correct re-capture: target delta + guard clean.
  run('compare-evidence good', [compareJs, before, afterGood, '--target', 'css:.hero',
    '--expect', 'padding-top=16px', '--expect', 'padding-bottom=16px'], true)

  // (4) FAILABLE: the WRONG fix passes adherence (every value a token) — run
  // adherence on wrong.styles.scss and expect GREEN, to show adherence ALONE
  // cannot catch a sibling shift. Then run the compare on the regression
  // re-capture and expect RED — the regression guard catches what adherence
  // can't. This pair is the teaching point of the slice.
  run('check-adherence on wrong (tokens only — must be GREEN)', [adhereJs, wrong, '--baseline', base, '--system', 'vuetify-scss', '--tokens', tokens, '--target-selector', '.hero'], true)
  run('compare-evidence on regression re-capture (must be RED)', [compareJs, before, afterBad, '--target', 'css:.hero',
    '--expect', 'padding-top=16px', '--expect', 'padding-bottom=16px'], false)

  if (errors.length) { console.error('verify-correct: FAILED'); for (const e of errors) console.error('  - ' + e); process.exit(1) }
  console.log('verify-correct: ok — regression-guard')
  console.log('  .hero padding -> $spacing-md; .sidebar + .layout untouched')
  console.log('  compare closed on correct re-capture (target delta + guard clean)')
  console.log('  teaching point: wrong fix passes adherence but the regression guard REJECTS it')
  console.log('  DEFERRED: real re-capture against the live component harness (no browser in harness)')
  process.exit(0)
}
main()