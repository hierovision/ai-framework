#!/usr/bin/env node
// Grader for the deploying-with-supabase skill (supabase-ci scenario).
//
// Run AFTER the agent stops, from a WRITABLE COPY of the fixture (never from
// evals/fixtures/). Expects a corrected .github/workflows/deploy.yml at the
// repo root. Failable: the seeded broken workflow runs `supabase db push`
// inside a matrixed deploy job with no concurrency (parallel pushes), and
// deploy has no migrate prerequisite — fails every check; a serialized
// migrate job (concurrency group, no matrix) that deploy `needs` PASSES.
//
// Planted defects in the seed file:
//   1. `supabase db push` runs inside the `deploy` job which has a `matrix`
//      (parallel pushes across regions) — corrupts migration history.
//   2. No `concurrency` serializing the push (two merges push at once).
//   3. No separate migrate job; `deploy` does not `needs` a migrate step
//      (migrate-before-deploy violated).
const fs = require('fs')
const path = require('path')

const root = process.cwd()
const wfPath = path.join(root, '.github', 'workflows', 'deploy.yml')
const errors = []

if (!fs.existsSync(wfPath)) {
  console.error('verify-supabase: FAILED — .github/workflows/deploy.yml missing (the deploy must emit a workflow)')
  process.exit(1)
}
const lines = fs.readFileSync(wfPath, 'utf8').split('\n')

const jobStarts = []
lines.forEach((l, i) => {
  const m = l.match(/^  ([A-Za-z0-9_-]+):\s*$/)
  if (m) jobStarts.push({ name: m[1], line: i })
})
function jobBlock(name) {
  const idx = jobStarts.findIndex((j) => j.name === name)
  if (idx < 0) return []
  const end = idx + 1 < jobStarts.length ? jobStarts[idx + 1].line : lines.length
  return lines.slice(jobStarts[idx].line, end)
}
function jobNeeds(name) {
  const block = jobBlock(name)
  for (let i = 0; i < block.length; i++) {
    const m = block[i].match(/^\s+needs:\s*(.+)$/)
    if (m) {
      const val = m[1].trim()
      if (val.startsWith('[')) return val.replace(/[[\]]/g, '').split(',').map((s) => s.trim())
      const items = []
      let j = i + 1
      while (j < block.length && /^\s+-\s+/.test(block[j])) {
        items.push(block[j].match(/-\s+(.+)/)[1].trim())
        j++
      }
      return items
    }
  }
  return []
}

// The migrate job = the job whose block runs `supabase db push`.
let migrateJob = null
for (const j of jobStarts) {
  if (jobBlock(j.name).some((l) => /supabase\s+db\s+push/.test(l))) {
    migrateJob = j.name
    break
  }
}
if (!migrateJob) {
  errors.push('no job runs `supabase db push` — the migration step is missing')
} else {
  const mb = jobBlock(migrateJob)
  // Serialized: a concurrency block with group:, and NO matrix/strategy.
  const hasConcurrencyGroup = mb.some((l) => /concurrency:/.test(l)) &&
    mb.some((l) => /group:/.test(l))
  if (!hasConcurrencyGroup) {
    errors.push('the migrate job has no `concurrency.group` — two db pushes can run at once and corrupt migration history')
  }
  const hasMatrix = mb.some((l) => /^\s+(strategy|matrix):/.test(l))
  if (hasMatrix) {
    errors.push('the migrate job uses a `matrix` — parallel db pushes corrupt migration history; serialize it')
  }
}

// deploy must need the migrate job (migrate-before-deploy).
const hasDeploy = jobStarts.some((j) => j.name === 'deploy')
if (!hasDeploy) {
  errors.push('no `deploy` job — the serve/deploy step is missing')
} else if (migrateJob && !jobNeeds('deploy').map((n) => n.toLowerCase()).includes(migrateJob.toLowerCase())) {
  errors.push('`deploy` does not `needs` the migrate job — migrate-before-deploy violated')
}

if (errors.length) {
  console.error('verify-supabase: FAILED (supabase-ci)')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log('verify-supabase: ok — db push serialized (concurrency, no matrix) + migrate-before-deploy')
process.exit(0)
