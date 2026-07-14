#!/usr/bin/env node
// Grader for the validating-against-official-docs skill (docs-adherence scenario).
//
// Run AFTER the agent stops, from a WRITABLE COPY of the fixture (never from
// evals/fixtures/). Expects ADHERENCE.md at the repo root. Failable: the
// seeded artifact (.github/workflows/deploy.yml) violates three rules stated
// in official-docs.md (no pull_request preview trigger; token in vars; no
// skip_app_build). A correct report flags all three gaps and cites the doc;
// a "looks fine" report with no Gaps section (or missing planted gaps) FAILS.
const fs = require('fs')
const path = require('path')

const root = process.cwd()
const reportPath = path.join(root, 'ADHERENCE.md')
const errors = []

if (!fs.existsSync(reportPath)) {
  console.error('verify-adherence: FAILED — ADHERENCE.md missing (the validation must emit a cited report)')
  process.exit(1)
}
const report = fs.readFileSync(reportPath, 'utf8')

// Must have both an Adheres section and a Gaps (or Non-compliant/Findings) section.
const hasAdheres = /##\s*Adheres/i.test(report)
const gapsMatch = report.match(/##\s*(Gaps|Non-?compliant|Findings)\b[^\n]*\n([\s\S]*?)(?=\n##\s|$)/i)
if (!hasAdheres) errors.push('ADHERENCE.md has no `## Adheres` section — a validation reports what adheres too, not just gaps')
if (!gapsMatch) {
  errors.push('ADHERENCE.md has no `## Gaps` (or Non-compliant/Findings) section — gaps must be named explicitly')
} else {
  const gapsBody = gapsMatch[2].toLowerCase()
  // Three planted rules the artifact violates (from official-docs.md):
  const planted = [
    { kw: 'pull_request', label: 'no preview-per-PR trigger (pull_request missing)' },
    { kw: 'vars', label: 'deployment token in vars (not secrets)' },
    { kw: 'skip_app_build', label: 'skip_app_build not set (Oryx would misbuild Vite)' },
  ]
  for (const p of planted) {
    if (!gapsBody.includes(p.kw.toLowerCase())) {
      errors.push('planted gap not flagged in Gaps section: ' + p.label)
    }
  }
}

// Must cite the doc (reference the frozen doc, a URL, or "docs"/"retrieved").
const citesDoc = /official-docs\.md|https?:\/\/|per the doc|docs\.|retrieved/i.test(report)
if (!citesDoc) errors.push('ADHERENCE.md does not cite the authoritative doc (URL / official-docs.md / retrieval date) — an uncited finding is an opinion, not a validation')

if (errors.length) {
  console.error('verify-adherence: FAILED (docs-adherence)')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log('verify-adherence: ok — adheres + gaps (3 planted) + doc citation all present')
process.exit(0)
