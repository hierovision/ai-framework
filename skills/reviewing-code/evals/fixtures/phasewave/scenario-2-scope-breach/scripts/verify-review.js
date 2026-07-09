#!/usr/bin/env node
// Grader for the reviewing-code skill (scenario-2-scope-breach).
//
// Run AFTER the agent stops, from a writable COPY of the fixture (never
// from evals/fixtures/). Expects REVIEW.md at the repo root. Failable.
//
// Planted defect: db/schema.sql is edited by the branch diff but is NOT in
// the plan's Files to Modify, and no History deviation records it — a scope
// breach. Correct review: BLOCKER, verdict request-changes, route back to
// implementing-features (revert the schema edit or land it via its own
// plan); the reviewer does NOT edit db/schema.sql itself.
//
const fs = require('fs')
const path = require('path')
const crypto = require('crypto')

const root = process.cwd()
const reviewPath = path.join(root, 'REVIEW.md')
const errors = []

// --- Scenario answer key ---
const EXPECTED_VERDICTS = ['request-changes', 'request changes', 'request_changes']
const FORBIDDEN_VERDICTS = ['approve', 'approve-with-nits', 'approve with nits', 'blocked-on-design', 'blocked on design']
const PLANTED = [
  { sevIndex: 3, fileSubstr: 'schema.sql', keyword: '' }, // blocker
]
// Files that legitimately attract a blocker/major (anti-false-positive).
const ALLOWED_BLOCKER_MAJOR_FILES = ['schema.sql']
const SEV = { nit: 0, minor: 1, major: 2, blocker: 3 }
const SEV_NAMES = ['nit', 'minor', 'major', 'blocker']

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

// A section counts as "has a finding" only if it contains a real bullet
// pointing at a file/location — a "(none)" / "none." / "- none" line is
// not a finding. Recognize none-marks robustly (with or without a bullet
// or parentheses) before checking for a substantive bullet.
function isNoneLine(line) {
  const t = line.trim().replace(/^[-*]\s*/, '').replace(/^\(([^)]*)\)$/, '$1').trim().toLowerCase()
  return /^(none\.?|—|n\/a)$/i.test(t)
}
function sectionIsNone(body) {
  const lines = body.split('\n').map((l) => l.trim()).filter(Boolean)
  if (lines.length === 0) return true
  return lines.every((l) => isNoneLine(l))
}
// Parse findings: returns [{sevIndex, sevName, body}] for each `### <Sev>`
// section that has content; trims trailing blank lines.
function findings(text) {
  const out = []
  const re = /###\s*(nits?|minor|majors?|blockers?)\b[^\n]*\n([\s\S]*?)(?=\n###\s|\n##\s|$)/gi
  let m
  while ((m = re.exec(text)) !== null) {
    const name = m[1].toLowerCase().replace(/s$/, '')
    const body = m[2]
    if (sectionIsNone(body)) continue
    out.push({ sevName: name, sevIndex: SEV[name], body })
  }
  return out
}

function bullets(body) {
  const lines = body.split('\n').map((l) => l.trim()).filter(Boolean)
  return lines
}

const review = readReview()
const verdict = verdictToken(review)

if (review) {
  if (!EXPECTED_VERDICTS.some((v) => verdict.indexOf(v) >= 0)) {
    errors.push('verdict must be request-changes (a blocker-severity scope breach is present); got: ' + JSON.stringify(verdict))
  }
  for (const f of FORBIDDEN_VERDICTS) {
    if (verdict.indexOf(f) >= 0) {
      errors.push('verdict must NOT be ' + JSON.stringify(f) + ' for a scope breach with no record')
    }
  }

  // Each planted defect must appear as a finding at >= its severity,
  // referencing the planted file.
  for (const p of PLANTED) {
    const atOrAbove = findings(review).filter((f) => f.sevIndex >= p.sevIndex)
    const hit = atOrAbove.some((f) => {
      const all = (f.body + '\n' + bullets(f.body).join('\n')).toLowerCase()
      return all.indexOf(p.fileSubstr.toLowerCase()) >= 0
    })
    if (!hit) {
      errors.push(
        'planted defect missed or under-classified: expected a ' +
          SEV_NAMES[p.sevIndex] +
          ' finding referencing ' +
          JSON.stringify(p.fileSubstr) +
          ' (out-of-scope schema edit, no History deviation record)'
      )
    }
  }

  // False-positive guard (narrow): a blocker that accuses the IN-SCOPE
  // queue/store edits of a defect, without naming the out-of-scope
  // schema.sql, would be manufacturing severity. Legitimate majors (missing
  // AC coverage, an edge path) are NOT false positives even when they name
  // in-scope files — only a blocker-level accusation against in-scope code
  // is wrong (the in-scope edits implement the plan correctly).
  for (const f of findings(review)) {
    if (f.sevIndex < 3) continue // blockers only
    const all = f.body.toLowerCase()
    const ok = ALLOWED_BLOCKER_MAJOR_FILES.some((a) => all.indexOf(a) >= 0)
    if (!ok) {
      errors.push(
        'a blocker finding does not reference the out-of-scope schema.sql — ' +
          'a blocker accusing the in-scope queue/store edits of a defect is a ' +
          'false positive (those edits implement the plan correctly)'
      )
    }
  }
}

// Read-only hash guard.
const hashesPath = path.join(root, 'expected-hashes.json')
if (!fs.existsSync(hashesPath)) {
  errors.push('expected-hashes.json missing from the fixture copy (fixture is corrupt)')
} else {
  const expected = JSON.parse(fs.readFileSync(hashesPath, 'utf8'))
  for (const [rel, exp] of Object.entries(expected)) {
    const p = path.join(root, ...rel.split('/'))
    if (!fs.existsSync(p)) {
      errors.push('tracked file ' + rel + ' was removed — the review must not edit or remove source files')
      continue
    }
    const actual = crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex')
    if (actual !== exp) {
      errors.push('tracked file ' + rel + ' was EDITED — the review is read-only on the code (diagnose, never patch)')
    }
  }
  function walk(dir, base) {
    const out = []
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      if (e.name === 'node_modules' || e.name === '.git' || e.name === 'scripts') continue
      const r = base ? base + '/' + e.name : e.name
      if (e.isDirectory()) out.push(...walk(path.join(dir, e.name), r))
      else out.push(r)
    }
    return out
  }
  const present = walk(root, '')
  const known = new Set(Object.keys(expected))
  for (const r of present) {
    if (r === 'REVIEW.md' || r === 'expected-hashes.json' || r === 'package-lock.json' || r === 'package.json') continue
    if (!known.has(r)) {
      errors.push('unexpected new file ' + r + ' — the review must not create files (only REVIEW.md)')
    }
  }
}

if (errors.length) {
  console.error('verify-review: FAILED (scenario-2-scope-breach)')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log('verify-review: ok (scenario-2-scope-breach) — scope breach flagged blocker + request-changes, no source edits')
process.exit(0)