#!/usr/bin/env node
// Grader for the reviewing-code skill (scenario-1-clean).
//
// Run AFTER the agent stops, from a writable COPY of the fixture (never
// from evals/fixtures/). Expects the agent to have written REVIEW.md at the
// repo root. Failable: exits non-zero when the review is wrong.
//
// This scenario is the FALSE-POSITIVE DISCIPLINE check: the diff is clean
// (nits only, conforming to its approved plan). A correct review issues
// approve / approve-with-nits and invents NO blocker or major. Manufacturing
// a high-severity finding to seem thorough, or requesting changes, is a FAIL.
//
// Fail causes:
//   - REVIEW.md missing (no review written)
//   - verdict is not approve / approve-with-nits (not ready-to-fail a clean diff)
//   - a finding is classified Blocker or Major (no planted defect of that
//     severity exists — the review manufactured severity)
//   - verdict mentions request-changes / blocked-on-design
//   - any tracked source file was edited (review must be read-only on the)
//
const fs = require('fs')
const path = require('path')
const crypto = require('crypto')

const root = process.cwd()
const reviewPath = path.join(root, 'REVIEW.md')
const errors = []

// --- Scenario answer key ---
const EXPECTED_VERDICTS = ['approve', 'approve-with-nits', 'approve with nits']
const FORBIDDEN_VERDICTS = ['request-changes', 'blocked-on-design', 'request changes', 'request_changes']
// No planted defects -> any blocker/major finding is manufactured (a false
// positive) and must FAIL the scenario.
const SHOULD_HAVE_BLOCKER_OR_MAJOR = false

// Severity order for reference (unused for planted checks here).
const SEV = { nit: 0, minor: 1, major: 2, blocker: 3 }

function readReview() {
  if (!fs.existsSync(reviewPath)) {
    errors.push('REVIEW.md is missing — the review must be written to REVIEW.md at the repo root')
    return ''
  }
  return fs.readFileSync(reviewPath, 'utf8')
}

// Parse a `## Verdict` section; allow headings `## Verdict` or a first bold
// line. Return the verdict token matched against the known set.
function parseVerdict(text) {
  const m = text.match(/##\s*Verdict\b[^\n]*\n+([^\n]+)/i)
  const line = m ? m[1].trim().toLowerCase() : ''
  return line
}

// Pull the findings list for a severity (the lines under a `### <Sev>`
// heading until the next `### `/`## ` heading). Returns the body string.
function section(text, name) {
  const re = new RegExp('###\\s*' + name + '\\b[^\\n]*\\n([\\s\\S]*?)(?=\\n###\\s|\\n##\\s|$)', 'i')
  const m = text.match(re)
  return m ? m[1] : ''
}

const review = readReview()
const verdictLine = parseVerdict(review)

// 1. Verdict is an approve variant, not a request-changes / blocked.
if (!review) {
  // already errored
} else {
  const matched = EXPECTED_VERDICTS.some((v) => verdictLine.indexOf(v) >= 0)
  if (!matched) {
    errors.push(
      'verdict must be approve / approve-with-nits (clean diff, nits only); got: ' +
        JSON.stringify(verdictLine)
    )
  }
  for (const f of FORBIDDEN_VERDICTS) {
    if (review.toLowerCase().indexOf(f) >= 0 && verdictLine.indexOf(f.replace(/-/g, ' ')) >= 0) {
      errors.push('verdict mentions ' + JSON.stringify(f) + ' — a clean diff must not be failed')
    }
  }

  // 2. False-positive guard: no Blocker / Major findings may exist.
  const blockerBody = section(review, 'Blockers?')
  const majorBody = section(review, 'Majors?')
  // A section counts as "has a finding" only if it contains a real bullet
  // pointing at a file/location — a "(none)" / "none." / "- none" line is
  // not a finding. Recognize none-marks robustly (with or without a bullet
  // or parentheses) before checking for a substantive bullet.
  function isNoneLine(line) {
    const t = line.trim().replace(/^[-*]\s*/, '').replace(/^\(([^)]*)\)$/, '$1').trim().toLowerCase()
    return /^(none\.?|—|n\/a)$/i.test(t)
  }
  function hasFinding(body) {
    if (!body.trim()) return false
    const lines = body.split('\n').map((l) => l.trim()).filter(Boolean)
    const substantive = lines.filter((l) => !isNoneLine(l))
    if (substantive.length === 0) return false
    // A substantive line must point at a file/path or carry a real bullet.
    return substantive.some((l) => /^\s*[-*]\s*\S/.test(l) || /[A-Za-z_\/][^\n]*\.(js|ts|sql|md|test)/.test(l))
  }
  if (hasFinding(blockerBody)) {
    errors.push(
      'a Blocker finding is present, but this diff has no blocker-severity defect — the review manufactured severity (false-positive discipline failure)'
    )
  }
  if (hasFinding(majorBody)) {
    errors.push(
      'a Major finding is present, but this diff has no major-severity defect — the review manufactured severity (false-positive discipline failure)'
    )
  }
  if (SHOULD_HAVE_BLOCKER_OR_MAJOR && !hasFinding(blockerBody) && !hasFinding(majorBody)) {
    errors.push('expected at least one blocker/major finding; found none')
  }

  // 2b. Spot-check cross-reference: the plan `## History` carries the
  // implement pass's red evidence (red-first) + coverage-gate outcome
  // (rebalance / expand-no-gap). The reviewer reads those records as
  // evidence rather than re-deriving the meaningfulness check from zero.
  // Assert REVIEW.md references at least one of those record markers
  // (red evidence / red-first / coverage gate / rebalance / spot-check).
  const spotTokens = ['red evidence', 'red-first', 'red first', 'coverage gate', 'coverage-gate', 'rebalance', 'spot-check', 'spot check']
  const spotChecked = spotTokens.some((t) => review.toLowerCase().indexOf(t) >= 0)
  if (!spotChecked) {
    errors.push(
      'the plan History carries red-evidence + coverage-gate records (see feat-session-sort.md ## History 2026-07-11 entry) but REVIEW.md does not reference or spot-check any of them (red evidence / red-first / coverage gate / rebalance / spot-check) — review the records as evidence rather than re-deriving the meaningfulness check from zero'
    )
  }
}

// 3. Read-only guard: every tracked file's hash must match the snapshot.
const hashesPath = path.join(root, 'expected-hashes.json')
if (!fs.existsSync(hashesPath)) {
  errors.push('expected-hashes.json missing from the fixture copy (fixture is corrupt)')
} else {
  const expected = JSON.parse(fs.readFileSync(hashesPath, 'utf8'))
  for (const [rel, exp] of Object.entries(expected)) {
    const p = path.join(root, ...rel.split('/'))
    if (!fs.existsSync(p)) {
      // A tracked file removed by the agent = an edit (and a coroutine the
      // review must not perform).
      errors.push('tracked file ' + rel + ' was removed — the review must not edit or remove source files')
      continue
    }
    const actual = crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex')
    if (actual !== exp) {
      errors.push('tracked file ' + rel + ' was EDITED — the review is read-only on the code (diagnose, never patch)')
    }
  }
  // Detect new files beyond REVIEW.md: any file not in the snapshot and not
  // REVIEW.md is an unreviewed write.
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
  console.error('verify-review: FAILED (scenario-1-clean)')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log('verify-review: ok (scenario-1-clean) — clean diff approved, no manufactured severity, no source edits')
process.exit(0)