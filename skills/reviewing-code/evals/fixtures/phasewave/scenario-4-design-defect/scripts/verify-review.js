#!/usr/bin/env node
// Grader for the reviewing-code skill (scenario-4-design-defect).
//
// Planted defect: the plan is internally contradictory (Goal says "chronological,
// oldest-first"; AC1 says "descending, newest-first"). The diff correctly
// implements AC1. The defect is in the PLAN, not the code. Correct review:
// verdict blocked-on-design, route to designing-architecture, ZERO source
// edits, and do NOT manufacture a code-correctness blocker.
//
const fs = require('fs')
const path = require('path')
const crypto = require('crypto')

const root = process.cwd()
const reviewPath = path.join(root, 'REVIEW.md')
const errors = []

const EXPECTED_VERDICTS = ['blocked-on-design', 'blocked on design', 'blocked_on_design']
const FORBIDDEN_VERDICTS = ['approve', 'approve-with-nits', 'approve with nits', 'request-changes', 'request changes', 'request_changes']
// No planted CODE defect — any blocker/major against the code is a false
// positive (the code correctly implements the AC; the plan is the defect).
const SHOULD_HAVE_CODE_BLOCKER = false

function readReview() {
  if (!fs.existsSync(reviewPath)) {
    errors.push('REVIEW.md is missing — the review must be written to REVIEW.md at the repo root')
    return ''
  }
  return fs.readFileSync(reviewPath, 'utf8')
}
function verdictToken(text) {
  const m = text.match(/##\s*Verdict\b[^\n]*\n+([^\n]+)/i)
  return m ? m[1].trim().toLowerCase() : ''
}
function isNoneLine(line) {
  const t = line.trim().replace(/^[-*]\s*/, '').replace(/^\(([^)]*)\)$/, '$1').trim().toLowerCase()
  return /^(none\.?|—|n\/a)$/i.test(t)
}
function sectionIsNone(body) {
  const lines = body.split('\n').map((l) => l.trim()).filter(Boolean)
  if (lines.length === 0) return true
  return lines.every((l) => isNoneLine(l))
}
function findings(text) {
  const out = []
  const re = /###\s*(nits?|minor|majors?|blockers?)\b[^\n]*\n([\s\S]*?)(?=\n###\s|\n##\s|$)/gi
  let m
  while ((m = re.exec(text)) !== null) {
    const name = m[1].toLowerCase().replace(/s$/, '')
    if (sectionIsNone(m[2])) continue
    out.push({ sevName: name, body: m[2] })
  }
  return out
}

const review = readReview()
const verdict = verdictToken(review)

if (review) {
  if (!EXPECTED_VERDICTS.some((v) => verdict.indexOf(v) >= 0)) {
    errors.push('verdict must be blocked-on-design (the plan is internally contradictory, not the code); got: ' + JSON.stringify(verdict))
  }
  for (const f of FORBIDDEN_VERDICTS) {
    if (verdict.indexOf(f) >= 0) errors.push('verdict must NOT be ' + JSON.stringify(f) + ' — the code is not the defect here')
  }
  // Must route to designing-architecture (or "revise the plan").
  const lower = review.toLowerCase()
  if (!(lower.indexOf('designing-architecture') >= 0 || lower.indexOf('revise the plan') >= 0 || lower.indexOf('design') >= 0)) {
    errors.push('must route the plan-internal contradiction to designing-architecture (revise the plan); no routing language found')
  }
  // Must surface the Goal vs AC1 contradiction specifically.
  if (!(lower.indexOf('goal') >= 0 && (lower.indexOf('criterion') >= 0 || lower.indexOf('ac1') >= 0))) {
    errors.push('must cite the Goal vs AC1 sort-direction conflict explicitly in the review')
  }
  // False-positive guard (narrow): a BLOCKER targeting the code would force
  // a request-changes verdict (contradicting blocked-on-design). A major
  // about missing AC evidence on the test is a legitimate process
  // observation, not a code-defect accusation, so it is allowed. The verdict
  // (blocked-on-design) is the key discriminator that the plan is the defect.
  for (const f of findings(review)) {
    if (f.sevName !== 'blocker') continue
    const all = f.body.toLowerCase()
    if (/session-list|session-display|session-sort/.test(all) && !/design|plan|goal|criterion|ac1|contradict/.test(all)) {
      errors.push('a blocker finding targets the CODE as defective — the code matches AC1; a code blocker (without plan/design context) would force request-changes, contradicting blocked-on-design')
    }
  }
}

const hashesPath = path.join(root, 'expected-hashes.json')
if (!fs.existsSync(hashesPath)) {
  errors.push('expected-hashes.json missing from the fixture copy (fixture is corrupt)')
} else {
  const expected = JSON.parse(fs.readFileSync(hashesPath, 'utf8'))
  for (const [rel, exp] of Object.entries(expected)) {
    const p = path.join(root, ...rel.split('/'))
    if (!fs.existsSync(p)) { errors.push('tracked file ' + rel + ' was removed — escalate, never edit'); continue }
    const actual = crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex')
    if (actual !== exp) errors.push('tracked file ' + rel + ' was EDITED — a blocked-on-design terminal produces ZERO source edits')
  }
  function walk(dir, base) {
    const out = []
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      if (e.name === 'node_modules' || e.name === '.git' || e.name === 'scripts') continue
      const r = base ? base + '/' + e.name : e.name
      if (e.isDirectory()) out.push(...walk(path.join(dir, e.name), r)); else out.push(r)
    }
    return out
  }
  const present = walk(root, '')
  const known = new Set(Object.keys(expected))
  for (const r of present) {
    if (r === 'REVIEW.md' || r === 'expected-hashes.json' || r === 'package-lock.json' || r === 'package.json') continue
    if (!known.has(r)) errors.push('unexpected new file ' + r + ' — the review must not create files (only REVIEW.md)')
  }
}

if (errors.length) {
  console.error('verify-review: FAILED (scenario-4-design-defect)')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log('verify-review: ok (scenario-4-design-defect) — design defect blocked-on-design, routed to design, no code edits')
process.exit(0)