#!/usr/bin/env node
// Grader for the designing-cicd skill (cicd-migrate scenario). Run with:
//   node scripts/verify-cicd.cjs
//
// Run AFTER the agent stops, from a WRITABLE COPY of the fixture (never from
// evals/fixtures/). Expects a corrected .github/workflows/ci.yml at the repo
// root. Failable: the seeded broken workflow FAILS every check below; a
// topology that applies migrate-before-deploy + prod concurrency + a gated
// environment PASSES.
//
// Planted defects in the seed file:
//   1. deploy runs BEFORE migrate (migrate needs: [deploy]) — the
//      migrate-before-deploy cardinal violation.
//   2. No `concurrency` on the deploy path — two merges can ship at once.
//   3. No `environment: production` gate — prod is ungated.
const fs = require('fs')
const path = require('path')

const root = process.cwd()
const wfPath = path.join(root, '.github', 'workflows', 'ci.yml')
const errors = []

if (!fs.existsSync(wfPath)) {
  console.error('verify-cicd: FAILED — .github/workflows/ci.yml missing (the design must emit a workflow)')
  process.exit(1)
}
const lines = fs.readFileSync(wfPath, 'utf8').split('\n')

// Job blocks: 2-space-indented "name:" lines at the jobs level.
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

// 1. migrate-before-deploy: a migrate job exists and deploy needs it.
const hasMigrate = jobStarts.some((j) => j.name === 'migrate')
if (!hasMigrate) errors.push('no `migrate` job — schema changes need an explicit migrate step before deploy')
const deployNeeds = jobNeeds('deploy')
if (!deployNeeds.map((n) => n.toLowerCase()).includes('migrate')) {
  errors.push('deploy does not `needs: [migrate]` — migrate-before-deploy violated (deploy can race/run before the migration)')
}

// 2. concurrency on the deploy path: a `concurrency:` block with `group:` and
//    NOT `cancel-in-progress: true` (prod must queue, not cancel mid-flight).
//    Tolerates both block form (`concurrency:` then indented `group:`) and
//    inline form (`concurrency: { group: x, "cancel-in-progress": false }`).
let hasGroup = false
let cancelsInFlight = false
for (let i = 0; i < lines.length; i++) {
  const m = lines[i].match(/^\s*concurrency:\s*(.*)$/)
  if (!m) continue
  const inline = m[1].trim()
  let region
  if (inline === '') {
    // block form: gather more-indented following lines
    const baseIndent = lines[i].match(/^(\s*)/)[1].length
    const blk = [lines[i]]
    let j = i + 1
    while (j < lines.length && /^(\s+)\S/.test(lines[j]) && lines[j].match(/^(\s*)\S/)[1].length > baseIndent) {
      blk.push(lines[j])
      j++
    }
    region = blk.join('\n')
  } else {
    region = lines[i] // inline map on one line
  }
  if (/group:/.test(region)) hasGroup = true
  if (/cancel-in-progress:\s*true/.test(region)) cancelsInFlight = true
}
if (!hasGroup) errors.push('no `concurrency.group` on the deploy path — two merges can ship concurrently and corrupt state')
if (cancelsInFlight) errors.push('`concurrency.cancel-in-progress: true` on a prod deploy — cancels an in-flight deploy and leaves a half-shipped environment; use false (queue)')

// 3. environment gate on deploy.
const deployBlock = jobBlock('deploy').join('\n')
if (!/environment:/.test(deployBlock)) {
  errors.push('deploy has no `environment:` — prod must be gated by a named environment with protection rules')
} else if (!/production/.test(deployBlock)) {
  errors.push('deploy `environment:` is not `production` — the prod environment gate is missing/unlabeled')
}

if (errors.length) {
  console.error('verify-cicd: FAILED (cicd-migrate)')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log('verify-cicd: ok — migrate-before-deploy + prod concurrency (queue) + gated environment all present')
process.exit(0)
