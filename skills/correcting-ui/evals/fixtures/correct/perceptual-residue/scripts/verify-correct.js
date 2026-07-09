#!/usr/bin/env node
// verify-correct.js — objective closure for the perceptual-residue scenario.
// Real re-capture + vision-critic pass are DEFERRED; this is the objective
// check. It proves the skill decomposed a perceptual complaint ("feels
// cramped") into MEASURABLE proxies (gap, padding, line-height) and closed on
// them within the system (snapped to $spacing-md / $line-comfortable tokens),
// while the genuinely perceptual residue ("does it breathe?") is honestly
// DEFERRED to the vision-critic-fast role — never self-signed-off.
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
  const after = path.join(ROOT, 'evidence', 'after-good-evidence.json')
  const residue = path.join(ROOT, 'vision-residue.txt')

  // (1) candidate source adheres (tokens, no magic px, no new !important).
  run('check-adherence on candidate', [adhereJs, cand, '--baseline', base, '--system', 'vuetify-scss', '--tokens', tokens, '--target-selector', '.summary-list'], true)

  // (2) source-level: the measurable proxies snapped up one scale step.
  const src = strip(fs.readFileSync(cand, 'utf8'))
  const list = src.match(/\.summary-list\s*\{([^}]*)\}/)
  if (!list) errors.push('.summary-list rule not found after edit')
  else {
    const gap = list[1].match(/gap\s*:\s*([^;]+)/)
    const pad = list[1].match(/padding\s*:\s*([^;]+)/)
    const lh = list[1].match(/line-height\s*:\s*([^;]+)/)
    if (!gap || gap[1].trim() !== '$spacing-md') errors.push(`gap proxy = '${gap ? gap[1].trim() : '?'}' but the eased token is $spacing-md`)
    if (!pad || pad[1].trim() !== '$spacing-md') errors.push(`padding proxy = '${pad ? pad[1].trim() : '?'}' but the eased token is $spacing-md`)
    if (!lh || lh[1].trim() !== '$line-comfortable') errors.push(`line-height proxy = '${lh ? lh[1].trim() : '?'}' but the eased token is $line-comfortable`)
  }

  // (3) objective compare closed on the proxies (gap/padding/line-height).
  run('compare-evidence good', [compareJs, before, after, '--target', 'css:.summary-list',
    '--expect', 'gap=16px', '--expect', 'padding-top=16px',
    '--expect', 'line-height=1.7'], true)

  // (4) FAILABLE: a magic-px "fix" on the proxies is REJECTED by adherence.
  run('check-adherence on magic-px bait (must be REJECTED)', [adhereJs, wrong, '--baseline', base, '--system', 'vuetify-scss', '--tokens', tokens, '--target-selector', '.summary-list'], false)

  // (5) the perceptual RESIDUE is honestly DEFERRED to vision-critic-fast, not
  // self-signed-off. The skill writes a one-line residue note the verifier
  // reads; a missing note = silent self-sign-off (a FAIL). The note must name
  // the vision-critic role (role, not model ID) and a deferral when no vision
  // model is available.
  let note = ''
  try { note = fs.readFileSync(residue, 'utf8').trim() } catch (e) { errors.push('vision-residue.txt missing — the perceptual residue was not handed to the vision-critic role (silent self-sign-off)') }
  if (note && !/vision-critic|deferred/i.test(note)) errors.push(`vision-residue.txt is '${note}' — expected the residue handed to the vision-critic role + a deferral where no vision model is available`)

  if (errors.length) { console.error('verify-correct: FAILED'); for (const e of errors) console.error('  - ' + e); process.exit(1) }
  console.log('verify-correct: ok — perceptual-residue')
  console.log('  proxies snapped: gap/padding -> $spacing-md, line-height -> $line-comfortable')
  console.log('  compare closed on the measurable proxies; magic-px bait REJECTED')
  console.log('  perceptual residue -> vision-critic-fast (DEFERRED where no vision model)')
  console.log('  DEFERRED: real re-capture + vision-critic pass (no browser / no vision model in harness)')
  process.exit(0)
}
main()