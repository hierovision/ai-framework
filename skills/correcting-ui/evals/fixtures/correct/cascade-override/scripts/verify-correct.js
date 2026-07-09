#!/usr/bin/env node
// verify-correct.js — objective closure for the cascade-override scenario.
// Real re-capture is DEFERRED; THIS is the objective check. It proves the
// candidate (a) targeted the matched-styles WINNING rule (.v-theme--light
// .qty-stepper in theme.scss, NOT the element's own overridden rule in
// styles.scss), (b) snapped the color to a token ($text-primary) and kept
// specificity flat, (c) closes the objective color delta on a correct
// re-capture, and (d) a naive fix at the OVERRIDDEN rule leaves the computed
// color UNCHANGED (compare RED) and an !important "win" is REJECTED.
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
  const candTheme = path.join(ROOT, 'src', 'theme.scss')
  const baseTheme = path.join(ROOT, 'src', 'baseline.theme.scss')
  const candStyles = path.join(ROOT, 'src', 'styles.scss')
  const baseStyles = path.join(ROOT, 'src', 'baseline.styles.scss')
  const wrong = path.join(ROOT, 'src', 'wrong.styles.scss')
  const tokens = path.join(ROOT, 'tokens.json')
  const before = path.join(ROOT, 'evidence', 'baseline-evidence.json')
  const afterGood = path.join(ROOT, 'evidence', 'after-good-evidence.json')
  const afterBad = path.join(ROOT, 'evidence', 'after-bad-evidence.json')

  // (1) adherence on the edited WINNER file (theme.scss), keeps specificity flat.
  run('check-adherence on winner (theme.scss)', [adhereJs, candTheme, '--baseline', baseTheme, '--system', 'vuetify-scss', '--tokens', tokens, '--target-selector', '.v-theme--light .qty-stepper'], true)

  // (2) source-level: the winner rule (theme.scss) was edited to the readable token.
  const themeSrc = fs.readFileSync(candTheme, 'utf8')
  const winMatch = themeSrc.match(/\.v-theme--light\s+\.qty-stepper\s*\{([^}]*)\}/)
  if (!winMatch) errors.push('theme.scss: the matched-styles WINNER (.v-theme--light .qty-stepper) was not the edit target — naive fix targeted the wrong rule')
  else {
    const color = winMatch[1].match(/color\s*:\s*([^;]+)/)
    if (!color || color[1].trim() !== '$text-primary') errors.push(`theme.scss winner color = '${color ? color[1].trim() : '?'}' but the intended readable token is $text-primary`)
  }

  // (3) source-level: the OVERRIDDEN component rule (styles.scss) was NOT the
  // edit site — editing it does nothing (computed unchanged). The dev who fell
  // for the screenshot instead edits here; the verifier rewards leaving it alone.
  const strip = (s) => s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1').trim()
  const stylesCand = strip(fs.readFileSync(candStyles, 'utf8'))
  const stylesBase = strip(fs.readFileSync(baseStyles, 'utf8'))
  if (stylesCand !== stylesBase) errors.push('src/styles.scss (the OVERRIDDEN rule) was modified — that edit cannot change the computed color; the fix target is the winner in theme.scss')

  // (4) objective compare closes on a correct re-capture (color -> #1f1f1f).
  run('compare-evidence good', [compareJs, before, afterGood, '--target', 'css:.qty-stepper', '--expect', 'color=#1f1f1f'], true)

  // (5) FAILABLE discriminator: a naive non-important edit to the OVERRIDDEN
  // rule leaves the computed color UNCHANGED (#6b6b6b) — compare MUST be RED.
  run('compare-evidence on naive-fix re-capture (must be RED)', [compareJs, before, afterBad, '--target', 'css:.qty-stepper', '--expect', 'color=#1f1f1f'], false)

  // (6) FAILABLE: an !important "win" on the overridden rule is REJECTED by the
  // adherence gate (the cardinal rule — never win the cascade by weakening).
  run('check-adherence on !important bait (must be REJECTED)', [adhereJs, wrong, '--baseline', baseStyles, '--system', 'vuetify-scss', '--tokens', tokens, '--target-selector', '.qty-stepper'], false)

  if (errors.length) { console.error('verify-correct: FAILED'); for (const e of errors) console.error('  - ' + e); process.exit(1) }
  console.log('verify-correct: ok — cascade-override')
  console.log('  fix targeted the matched-styles winner (theme.scss), not the overridden own rule')
  console.log('  winner color -> $text-primary; specificity flat; styles.scss untouched')
  console.log('  compare closed on correct re-capture; naive-fix re-capture RED; !important bait REJECTED')
  console.log('  DEFERRED: real re-capture against the live component harness (no browser in harness)')
  process.exit(0)
}
main()