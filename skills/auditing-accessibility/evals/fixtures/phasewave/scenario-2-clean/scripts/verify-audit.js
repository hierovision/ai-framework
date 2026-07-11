#!/usr/bin/env node
// verify-audit.js — objective self-check (scenario 2 clean-page / false-positive
// discipline). Feeds a CANNED axe-results fixture representing a GENUINELY
// accessible page (axe finds NOTHING) into runAudit, builds the report, and
// asserts: verdict pass, ZERO violations, ZERO severity, the manual_checklist
// STILL emitted (automation-ceiling honesty — a pass does NOT discharge
// manual verification), AND zero manufactured violations (false-positive
// discipline — a skill that invents a blocker to seem thorough FAILS).
// Real-browser axe is DEFERRED; real source edits are forbidden (read-only).
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
  const { runAudit, SCHEMA_VERSION } = await import(AUDIT_URL)
  const canned = JSON.parse(fs.readFileSync(path.join(FIX, 'axe-results.json'), 'utf8'))
  const key = JSON.parse(fs.readFileSync(path.join(FIX, 'answer-key.json'), 'utf8'))

  const out = fs.mkdtempSync(path.join(os.tmpdir(), 'audit-report-'))
  const res = await runAudit({
    mode: 'app', target: 'http://localhost:5173', route: '/dashboard',
    viewports: ['375x667', '1280x720'], out, level: 'AA', name: 'self-check-2',
    axeResults: canned,
  }).catch((e) => ({ _err: e }))
  if (res._err) { console.error('verify-audit: runAudit threw:', res._err.stack || res._err); process.exit(1) }
  const reportPath = res.reportPath || path.join(out, 'report.json')
  const rep = JSON.parse(fs.readFileSync(reportPath, 'utf8'))

  const val = spawnSync('node', [path.join(HERE, 'validate-report.js'), reportPath], { encoding: 'utf8' })
  if (val.status !== 0) errors.push(`validate-report.js exited ${val.status}\n${val.stderr || val.stdout}`)
  expect(rep.schema_version, '===', SCHEMA_VERSION, 'schema_version', rep.schema_version)

  // FALSE-POSITIVE DISCIPLINE: a genuinely accessible page -> clean report
  expect(rep.verdict, '===', 'pass', 'verdict pass on a clean page', rep.verdict)
  expect(rep.violations.length, '===', 0, 'ZERO violations on a clean page', rep.violations.length)
  expect(rep.severity_rollup.blocker, '===', 0, 'zero blocker severity', rep.severity_rollup.blocker)
  expect(rep.severity_rollup.major, '===', 0, 'zero major severity', rep.severity_rollup.major)
  expect(rep.severity_rollup.minor, '===', 0, 'zero minor severity', rep.severity_rollup.minor)
  expect(rep.severity_rollup.nit, '===', 0, 'zero nit severity', rep.severity_rollup.nit)

  // automation-ceiling honesty: a pass does NOT discharge manual verification
  expect(rep.manual_checklist.length, '>=', key.manual_checklist_min, `>=${key.manual_checklist_min} manual checks (honesty)`, rep.manual_checklist.length)
  if (!rep.automation_ceiling_note) errors.push('automation_ceiling_note missing — pass must NOT claim full conformance from automation')

  // NO false manual-verification inflation: a clean page has no axe incomplete
  expect(rep.needs_manual_verification.length, '===', key.needs_manual_verification_count, `needs_manual_verification ${key.needs_manual_verification_count}`, rep.needs_manual_verification.length)

  // ZERO source edits
  const hashes = JSON.parse(fs.readFileSync(path.join(FIX, 'expected-hashes.json'), 'utf8'))
  for (const [rel, expected] of Object.entries(hashes)) {
    const actual = sha256(fs.readFileSync(path.join(FIX, rel)), rel)
    if (actual !== expected) errors.push(`source edit detected in ${rel}: the auditor must NOT edit source`)
  }

  if (errs() > 0) return
  console.log(`verify-audit: ok — scenario 2 (clean page / false-positive discipline)`)
  console.log(`  report: ${reportPath}`)
  console.log(`  verdict: ${rep.verdict}; violations ${rep.violations.length}; rollup ${JSON.stringify(rep.severity_rollup)}`)
  console.log(`  manual checks: ${rep.manual_checklist.length} (pass does NOT discharge manual verification)`)
  console.log(`  validator green; zero source edits; NO manufactured violations`)
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