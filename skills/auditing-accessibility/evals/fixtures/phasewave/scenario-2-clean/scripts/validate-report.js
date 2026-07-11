#!/usr/bin/env node
// validate-report.js — schema validator for the report.json written by
// audit.mjs. FAILABLE: exits non-zero when the report is not valid JSON / not
// schema-valid / missing severity rollup / missing manual_checklist (the
// automation-ceiling honesty) / carrying a verdict that contradicts the
// rollup. It does NOT require a browser.
//
//   node scripts/validate-report.js <path-to-report.json>
const fs = require('fs')

const SCHEMA_VERSION = '1.0'
const REQUIRED_VIOLATION_FIELDS = ['rule_id', 'wcag_sc', 'impact', 'severity', 'node', 'reason', 'fix_pointer', 'route', 'viewport', 'accepted']
const SEVERITIES = ['blocker', 'major', 'minor', 'nit']
const IMPACTS = ['critical', 'serious', 'moderate', 'minor', null]

const path = process.argv[2]
if (!path) { console.error('usage: validate-report.js <report.json>'); process.exit(2) }

let raw, rep
try { raw = fs.readFileSync(path, 'utf8') } catch (e) { fail(`cannot read ${path}: ${e.message}`) }
try { rep = JSON.parse(raw) } catch (e) { fail(`invalid JSON: ${e.message}`) }

const errors = []
if (!rep || typeof rep !== 'object') errors.push('report is not an object')
if (rep.schema_version !== SCHEMA_VERSION) errors.push(`schema_version '${rep.schema_version}' != expected '${SCHEMA_VERSION}' (drift — consumer must adapt)`)
if (!rep.audit_meta) errors.push('missing audit_meta block')
if (!Array.isArray(rep.violations)) errors.push('violations is not an array')
if (!Array.isArray(rep.needs_manual_verification)) errors.push('needs_manual_verification is not an array')
if (!Array.isArray(rep.manual_checklist) || !rep.manual_checklist.length) {
  errors.push('manual_checklist missing/empty — the beyond-axe list must ALWAYS be emitted (honesty about automation\'s ceiling)')
}
if (!Array.isArray(rep.accepted_risks)) errors.push('accepted_risks is not an array')
if (typeof rep.automation_ceiling_note !== 'string' || !rep.automation_ceiling_note) {
  errors.push('automation_ceiling_note missing — a pass verdict must not discharge manual verification')
}
if (!rep.severity_rollup || SEVERITIES.some((s) => typeof rep.severity_rollup[s] !== 'number')) {
  errors.push('severity_rollup must count blocker/major/minor/nit as numbers')
}
if (rep.verdict !== 'pass' && rep.verdict !== 'violations-found') errors.push(`bad verdict '${rep.verdict}'`)
// verdict must follow the rollup MECHANICALLY
const hasViolation = Array.isArray(rep.violations) && rep.violations.length > 0
if (hasViolation && rep.verdict !== 'violations-found') errors.push(`verdict '${rep.verdict}' contradicts ${rep.violations.length} violation(s) — must be 'violations-found'`)
if (!hasViolation && rep.verdict !== 'pass') errors.push(`verdict '${rep.verdict}' but no violations — must be 'pass'`)

for (let i = 0; Array.isArray(rep.violations) && i < rep.violations.length; i++) {
  const v = rep.violations[i]
  const tag = `violations[${i}] (${v.rule_id || '?'})`
  for (const f of REQUIRED_VIOLATION_FIELDS) { if (!(f in v)) errors.push(`${tag}: missing '{f}'`.replace('{f}', f)) }
  if (!SEVERITIES.includes(v.severity)) errors.push(`${tag}: bad severity '${v.severity}'`)
  if (v.impact != null && !['critical', 'serious', 'moderate', 'minor'].includes(v.impact)) errors.push(`${tag}: bad impact '${v.impact}'`)
  if (v.impact && IMPACT_TO_SEVERITY_OK(v.impact) !== v.severity) errors.push(`${tag}: impact '${v.impact}' must map to '${IMPACT_TO_SEVERITY_OK(v.impact)}' not '${v.severity}' (mechanical mapping, no vibe)`)
  if (!Array.isArray(v.wcag_sc)) errors.push(`${tag}: wcag_sc must be an array`)
  if (!v.node || typeof v.node !== 'object') errors.push(`${tag}: missing node`)
  else if (typeof v.node.target !== 'string' || !v.node.target) errors.push(`${tag}: node.target must be a non-empty selector`)
  if (typeof v.reason !== 'string' || !v.reason) errors.push(`${tag}: reason must be concrete (axe help + failureSummary), not empty`)
  if (typeof v.fix_pointer !== 'string' || !v.fix_pointer) errors.push(`${tag}: fix_pointer must name the rule + guidance`)
  if (!['correcting-ui', 'implementing-features', 'designing-architecture'].includes(v.route)) errors.push(`${tag}: bad route '${v.route}'`)
  if (!(v.viewport && typeof v.viewport.width === 'number')) errors.push(`${tag}: viewport must be numeric`)
  // accepted markers
  if (v.accepted === true && !(v.accepted_record && v.accepted_record.date && v.accepted_record.justification)) {
    errors.push(`${tag}: accepted=true requires a dated accepted_record (date + justification)`)
  }
}
// rollup must match the actual severities
if (rep.violations && rep.severity_rollup) {
  const recomputed = { blocker: 0, major: 0, minor: 0, nit: 0 }
  for (const v of rep.violations) if (recomputed[v.severity] != null) recomputed[v.severity]++
  for (const s of SEVERITIES) if (recomputed[s] !== rep.severity_rollup[s]) errors.push(`severity_rollup.${s}=${rep.severity_rollup[s]} but recomputed ${recomputed[s]}`)
}

if (errors.length) {
  console.error(`validate-report: FAILED (${path})`)
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log(`validate-report: ok — ${path} — ${rep.violations.length} violations, verdict ${rep.verdict}, rollup ${JSON.stringify(rep.severity_rollup)}, ${rep.manual_checklist.length} manual checks, schema ${SCHEMA_VERSION}`)
process.exit(0)

function IMPACT_TO_SEVERITY_OK(impact) {
  return { critical: 'blocker', serious: 'major', moderate: 'minor', minor: 'nit' }[impact] || 'minor'
}
function fail(msg) { console.error('validate-report: FAILED — ' + msg); process.exit(1) }