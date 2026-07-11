#!/usr/bin/env node
// verify-audit.js — objective self-check for the audit harness (scenario 1
// violations-present). Real-browser axe is DEFERRED (no browser in this
// harness); THIS is the objective check. It imports runAudit from the skill's
// audit.mjs, feeds it the bundled CANNED axe-results fixture (an exact
// representation of what axe WOULD return on harness/index.html), builds the
// report.json, validates it against the schema validator, and asserts the
// produced report caught every planted violation at the right severity +
// WCAG SC, issued verdict violations-found, routed each fix to the right
// sibling, made ZERO source edits, and emitted the beyond-axe manual
// checklist (automation-ceiling honesty).
//
// Failable: exits non-zero when audit.mjs cannot be imported / runAudit
// throws, the report fails the schema validator, a planted violation is
// missed or mis-classified (severity/WCAG SC/route), the verdict contradicts
// the rollup, the manual_checklist is absent, the demonstrated negative
// (evil-report.json) wrongly validates GREEN, OR any harness source file was
// edited (the auditor is read-only on the code).
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
  const mod = await import(AUDIT_URL)
  const { runAudit, SCHEMA_VERSION } = mod
  const canned = JSON.parse(fs.readFileSync(path.join(FIX, 'axe-results.json'), 'utf8'))
  const key = JSON.parse(fs.readFileSync(path.join(FIX, 'answer-key.json'), 'utf8'))

  const out = fs.mkdtempSync(path.join(os.tmpdir(), 'audit-report-'))
  const res = await runAudit({
    mode: 'app', target: 'http://localhost:5173', route: '/dashboard',
    viewports: ['375x667', '1280x720'], out, level: 'AA', name: 'self-check-1',
    axeResults: canned,
  }).catch((e) => ({ _err: e }))
  if (res._err) { console.error('verify-audit: runAudit threw:', res._err.stack || res._err); process.exit(1) }

  const reportPath = res.reportPath || path.join(out, 'report.json')
  if (!fs.existsSync(reportPath)) { console.error('verify-audit: report.json missing'); process.exit(1) }
  const rep = JSON.parse(fs.readFileSync(reportPath, 'utf8'))

  // schema validator on the captured artifact — must be GREEN
  const val = spawnSync('node', [path.join(HERE, 'validate-report.js'), reportPath], { encoding: 'utf8' })
  if (val.status !== 0) errors.push(`validate-report.js exited ${val.status}\n${val.stderr || val.stdout}`)

  // provenance: this was a canned self-check, so axe_run=false (honest), axes version recorded
  expect(rep.audit_meta.axe_run, '===', false, 'canned self-check recorded axe_run=false (honest)', rep.audit_meta && rep.audit_meta.axe_run)
  expect(rep.audit_meta.mode, '===', 'app', 'app-mode recorded', rep.audit_meta.mode)
  expect(rep.schema_version, '===', SCHEMA_VERSION, 'schema_version matches', rep.schema_version)

  // verdict + rollup
  expect(rep.verdict, '===', key.verdict, `verdict ${key.verdict}`, rep.verdict)
  expect(rep.severity_rollup.blocker, '===', key.severity_rollup.blocker, 'blocker rollup', rep.severity_rollup.blocker)
  expect(rep.severity_rollup.major, '===', key.severity_rollup.major, 'major rollup', rep.severity_rollup.major)
  expect(rep.severity_rollup.minor, '===', key.severity_rollup.minor, 'minor rollup', rep.severity_rollup.minor)

  // each expected violation present at the right severity + WCAG SC + route; the
  // report expands per viewport, so a 1-node planted violation -> 2 entries.
  for (const ex of key.violations_expected) {
    const matching = rep.violations.filter((v) => v.rule_id === ex.rule_id)
    if (matching.length === 0) { errors.push(`expected violation ${ex.rule_id} MISSING from report`); continue }
    const badSev = matching.find((v) => v.severity !== ex.severity)
    if (badSev) errors.push(`${ex.rule_id}: severity expected ${ex.severity}, got ${badSev.severity}`)
    const first = matching[0]
    for (const sc of ex.wcag_sc) {
      if (!first.wcag_sc.includes(sc)) errors.push(`${ex.rule_id}: missing WCAG SC ${sc} (got ${JSON.stringify(first.wcag_sc)})`)
    }
    expect(first.route, '===', ex.route, `${ex.rule_id} route -> ${ex.route}`, first.route)
    if (typeof first.reason !== 'string' || !first.reason) errors.push(`${ex.rule_id}: reason must be concrete, not empty`)
    if (typeof first.fix_pointer !== 'string' || !first.fix_pointer) errors.push(`${ex.rule_id}: fix_pointer must name the rule + guidance`)
  }
  // NO manufactured violations beyond the expected set (false-positive discipline)
  const expectedRuleIds = new Set(key.violations_expected.map((v) => v.rule_id))
  const extra = rep.violations.filter((v) => !expectedRuleIds.has(v.rule_id)).map((v) => v.rule_id)
  if (extra.length) errors.push(`manufactured violations (false-positive discipline): ${JSON.stringify(extra)}`)

  // manual checklist ALWAYS emitted (automation-ceiling honesty even when violations found)
  expect(rep.manual_checklist.length, '>=', key.manual_checklist_min, `>=${key.manual_checklist_min} manual checks`, rep.manual_checklist.length)
  if (!rep.manual_checklist.some((m) => /keyboard trap/i.test(m.check))) errors.push('manual_checklist missing keyboard-trap item')
  if (!rep.automation_ceiling_note) errors.push('automation_ceiling_note missing')

  // source_location present for the contrast rule (the matched-styles idea)
  if (key.source_location_present_for.length) {
    for (const rid of key.source_location_present_for) {
      const v = rep.violations.find((x) => x.rule_id === rid)
      if (!v || !v.source_location) errors.push(`${rid}: source_location should be present (computed color rule)`)
      else if (!v.source_location.computed || !v.source_location.computed.color) errors.push(`${rid}: source_location.computed.color missing`)
    }
  }

  // negative: bundled validator MUST fail on an intentionally-evil report (failable)
  const evilPath = path.join(HERE, 'evil-report.json')
  if (fs.existsSync(evilPath)) {
    const bad = spawnSync('node', [path.join(HERE, 'validate-report.js'), evilPath], { encoding: 'utf8' })
    if (bad.status === 0) errors.push(`validate-report.js wrongly accepted evil-report.json (the failable verifier must exit non-zero on a malformed/contradictory report)`)
  }

  // ZERO source edits: every file under harness/ must be byte-equal to the
  // shipped fixture hashes (the auditor is read-only on the code).
  const hashes = JSON.parse(fs.readFileSync(path.join(FIX, 'expected-hashes.json'), 'utf8'))
  for (const [rel, expected] of Object.entries(hashes)) {
    const p = path.join(FIX, rel)
    const actual = sha256(fs.readFileSync(p))
    if (actual !== expected) errors.push(`source edit detected in ${rel}: the auditor must NOT edit source`)
  }

  if (errs() > 0) return
  console.log(`verify-audit: ok — scenario 1 (violations-present)`)
  console.log(`  report: ${reportPath}`)
  console.log(`  verdict: ${rep.verdict}; rollup ${JSON.stringify(rep.severity_rollup)}; violations ${rep.violations.length}`)
  console.log(`  manual checks: ${rep.manual_checklist.length} (automation-ceiling honesty); needs-manual-verification: ${rep.needs_manual_verification.length}`)
  console.log(`  validator green on captured report; validator red on evil-report (failable); zero source edits confirmed`)
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

function sha256(buf) {
  const crypto = require('crypto')
  return crypto.createHash('sha256').update(buf).digest('hex')
}

main().catch((e) => { console.error('verify-audit: crashed:', e.stack || e); process.exit(1) })