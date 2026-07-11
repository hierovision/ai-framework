#!/usr/bin/env node
// verify-audit.js — objective self-check (scenario 4 automation-ceiling). The
// page's real problem is keyboard-only (a modal with scripted focus management
// that may trap focus) which axe CANNOT fully catch — axe returns no violations
// but an `incomplete` for the focus-trap. This grader asserts the skill surfaces
// it in the manual-verification list rather than FALSELY reporting a clean
// pass with no caveat: verdict pass (no false violation INVENTED), but
// needs_manual_verification is NON-EMPTY (the focus-trap surfaces), the
// beyond-axe manual_checklist includes the keyboard/focus items, and the
// automation_ceiling_note flags manual verification OUSTANDING. Real axe run
// DEFERRED; zero source edits.
const fs = require('fs')
const os = require('os')
const path = require('path')
const { spawnSync } = require('child_process')

const SCHEMES = [
  process.env.AUDIT_SKILL_DIR,
  path.join(os.homedir(), '.config/opencode/skills/auditing-accessibility'),
  path.resolve(__dirname, '..', '..', '..', '..', '..'),
].filter(Boolean)
const SKILL_DIR = SCHEMES.find((d) => fs.existsSync(path.join(d, 'scripts', 'audit.mjs')))
if (!SKILL_DIR) { console.error('verify-audit: could not locate audit.mjs — set AUDIT_SKILL_DIR'); process.exit(1) }
const AUDIT_URL = 'file://' + path.join(SKILL_DIR, 'scripts', 'audit.mjs').replace(/\\/g, '/')
const HERE = __dirname
const FIX = path.resolve(HERE, '..')
const errors = []

async function main() {
  const { runAudit } = await import(AUDIT_URL)
  const canned = JSON.parse(fs.readFileSync(path.join(FIX, 'axe-results.json'), 'utf8'))
  const key = JSON.parse(fs.readFileSync(path.join(FIX, 'answer-key.json'), 'utf8'))

  const out = fs.mkdtempSync(path.join(os.tmpdir(), 'audit-ceiling-'))
  const res = await runAudit({
    mode: 'app', target: 'http://localhost:5173', route: '/',
    viewports: ['375x667', '1280x720'], out, level: 'AA', name: 'ceiling',
    axeResults: canned,
  }).catch((e) => ({ _err: e }))
  if (res._err) { console.error('verify-audit: runAudit threw:', res._err.stack || res._err); process.exit(1) }
  const reportPath = res.reportPath || path.join(out, 'report.json')
  const rep = JSON.parse(fs.readFileSync(reportPath, 'utf8'))

  const val = spawnSync('node', [path.join(HERE, 'validate-report.js'), reportPath], { encoding: 'utf8' })
  if (val.status !== 0) errors.push(`validate-report.js exited ${val.status}\n${val.stderr || val.stdout}`)

  // verdict pass (no axe violation) — but NOT a false "fully accessible" claim
  expect(rep.verdict, '===', key.verdict, `verdict ${key.verdict} (no false violation invented)`, rep.verdict)
  expect(rep.violations.length, '===', 0, 'ZERO axe violations invented (automation-ceiling honesty)', rep.violations.length)
  expect(rep.severity_rollup.blocker, '===', 0, 'zero blocker (no invention)', rep.severity_rollup.blocker)

  // the real problem SURFACES in needs_manual_verification, not silently dropped
  expect(rep.needs_manual_verification.some((m) => m.rule_id === key.needs_manual_verification_rule_id), '===', true, `needs_manual_verification surfaces ${key.needs_manual_verification_rule_id}`, rep.needs_manual_verification.map((m) => m.rule_id))
  if (!rep.needs_manual_verification.some((m) => /trap|focus/i.test(m.reason + m.what_to_verify))) errors.push('needs_manual_verification must describe the keyboard concern (not a silent pass)')

  // the beyond-axe manual_checklist flags keyboard/focus items (always emitted)
  for (const title of key.manual_checklist_must_include) {
    if (!rep.manual_checklist.some((m) => m.check === title)) errors.push(`manual_checklist missing '${title}'`)
  }
  expect(rep.manual_checklist.length, '>=', key.manual_checklist_min, `>=${key.manual_checklist_min} manual checks`, rep.manual_checklist.length)
  if (!rep.automation_ceiling_note) errors.push('automation_ceiling_note missing — pass must NOT claim full conformance from automation alone')

  // ZERO source edits (the read-only auditor does not fix the focus trap here)
  const hashes = JSON.parse(fs.readFileSync(path.join(FIX, 'expected-hashes.json'), 'utf8'))
  for (const [rel, expected] of Object.entries(hashes)) {
    const actual = sha256(fs.readFileSync(path.join(FIX, rel)))
    if (actual !== expected) errors.push(`source edit detected in ${rel}: the auditor must NOT edit source`)
  }

  if (errs() > 0) return
  console.log(`verify-audit: ok — scenario 4 (automation-ceiling)`)
  console.log(`  report: ${reportPath}`)
  console.log(`  verdict: ${rep.verdict} (NO false violation invented); violations ${rep.violations.length}`)
  console.log(`  needs_manual_verification: ${rep.needs_manual_verification.length} (surfaces ${key.needs_manual_verification_rule_id} instead of a silent pass)`)
  console.log(`  manual_checklist: ${rep.manual_checklist.length} items incl keyboard trap/focus (automation ceiling flagged)`)
  console.log(`  validator green; zero source edits`)
  console.log(`  DEFERRED: real axe run against the live dev server (no browser in harness)`)
  process.exit(0)

  function expect(actual, op, want, label, got) {
    let ok = false
    if (op === '===') ok = actual === want
    else if (op === '>=') ok = typeof actual === 'number' && actual >= want
    if (!ok) errors.push(`expected ${label}, got ${JSON.stringify(got)}`)
  }
  function errs() { if (errors.length) { console.error('verify-audit: FAILED'); for (const e of errors) console.error('  - ' + e); process.exit(1) }; return errors.length }
}
function sha256(buf) { const c = require('crypto'); return c.createHash('sha256').update(buf).digest('hex') }
main().catch((e) => { console.error('verify-audit: crashed:', e.stack || e); process.exit(1) })