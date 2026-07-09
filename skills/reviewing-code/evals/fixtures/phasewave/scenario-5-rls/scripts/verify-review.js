#!/usr/bin/env node
// Grader for the reviewing-code skill (scenario-5-rls).
//
// Planted defect: the RLS SELECT policy uses `USING (true)`, granting all
// authenticated users read access to every shared_sessions row — a cross-
// user data leak. Correct review: BLOCKER (security hole) or MAJOR at
// minimum, verdict request-changes, route back to implementing-features
// (tighten the policy). The reviewer does NOT edit schema.sql itself.
//
const fs = require('fs')
const path = require('path')
const crypto = require('crypto')

const root = process.cwd()
const reviewPath = path.join(root, 'REVIEW.md')
const errors = []

const EXPECTED_VERDICTS = ['request-changes', 'request changes', 'request_changes']
const FORBIDDEN_VERDICTS = ['approve', 'approve-with-nits', 'approve with nits', 'blocked-on-design', 'blocked on design']
// Planted: a security blocker referencing schema.sql + the policy / RLS / USING.
const PLANTED = [{ sevIndex: 2, fileSubstr: 'schema.sql', keyword: '' }] // blocker or major
const SEV = { nit: 0, minor: 1, major: 2, blocker: 3 }
const SEV_NAMES = ['nit', 'minor', 'major', 'blocker']
const ALLOWED_BLOCKER_MAJOR_FILES = ['schema.sql']

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
    out.push({ sevName: name, sevIndex: SEV[name], body: m[2] })
  }
  return out
}

const review = readReview()
const verdict = verdictToken(review)

if (review) {
  if (!EXPECTED_VERDICTS.some((v) => verdict.indexOf(v) >= 0)) {
    errors.push('verdict must be request-changes (a security blocker/major is present); got: ' + JSON.stringify(verdict))
  }
  for (const f of FORBIDDEN_VERDICTS) {
    if (verdict.indexOf(f) >= 0) errors.push('verdict must NOT be ' + JSON.stringify(f) + ' for a security hole')
  }
  for (const p of PLANTED) {
    const atOrAbove = findings(review).filter((f) => f.sevIndex >= p.sevIndex)
    const hit = atOrAbove.some((f) => f.body.toLowerCase().indexOf(p.fileSubstr.toLowerCase()) >= 0)
    if (!hit) {
      errors.push('planted defect missed/under-classified: expected a major-or-blocker finding referencing ' + JSON.stringify(p.fileSubstr) + ' (RLS USING(true) widens visibility)')
    }
  }
  // Reference to RLS / policy / leak in the finding body.
  const savedBody = findings(review).filter((f) => f.sevIndex >= 2).map((f) => f.body.toLowerCase()).join('\n')
  if (!savedBody) {
    errors.push('no blocker/major finding body present — the RLS widening must be described')
  } else if (!/using\s*\(\s*true|rls|policy|leak|cross-|every|all authenticated/i.test(savedBody)) {
    errors.push('the blocker/major finding must name the leak mechanism (USING(true) / RLS / cross-user leak)')
  }
  // No false-positive guard: a good review may find ADDITIONAL real defects
  // beyond the planted RLS widening (e.g. an owner_id NOT NULL insert bug).
  // Those are legitimate, not manufactured. Verdict + planted-defect + leak-
  // mechanism + zero-edits are the failable checks.
}

const hashesPath = path.join(root, 'expected-hashes.json')
if (!fs.existsSync(hashesPath)) {
  errors.push('expected-hashes.json missing from the fixture copy (fixture is corrupt)')
} else {
  const expected = JSON.parse(fs.readFileSync(hashesPath, 'utf8'))
  for (const [rel, exp] of Object.entries(expected)) {
    const p = path.join(root, ...rel.split('/'))
    if (!fs.existsSync(p)) { errors.push('tracked file ' + rel + ' was removed — the review must not edit or remove source files'); continue }
    const actual = crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex')
    if (actual !== exp) errors.push('tracked file ' + rel + ' was EDITED — the review is read-only on the code (diagnose, never patch)')
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
  console.error('verify-review: FAILED (scenario-5-rls)')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log('verify-review: ok (scenario-5-rls) — RLS widening flagged blocker/major + request-changes, no source edits')
process.exit(0)