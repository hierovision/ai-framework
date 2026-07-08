#!/usr/bin/env node
// Project verify script: lint. Stub for the real ESLint; enforces house
// rules: no `as any`, no leftover TBD/FIXME markers, no `waitForTimeout`
// in e2e/.
const fs = require('fs')
const path = require('path')

const repoRoot = path.join(__dirname, '..')

function walkTs(dir) {
  const out = []
  if (!fs.existsSync(dir)) return out
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name)
    if (e.isDirectory()) out.push(...walkTs(p))
    else if (e.name.endsWith('.ts')) out.push(p)
  }
  return out
}

const errors = []
for (const f of walkTs(path.join(repoRoot, 'e2e'))) {
  const s = fs.readFileSync(f, 'utf8')
  if (/\bas\s+any\b/.test(s)) {
    errors.push(`${path.relative(repoRoot, f)}: \`as any\` defeats type-checking — narrow the type instead`)
  }
  if (/\bTBD\b|\bFIXME\b/.test(s)) {
    errors.push(`${path.relative(repoRoot, f)}: leftover TBD/FIXME marker — resolve or move to Open Questions`)
  }
  if (/waitForTimeout\s*\(/.test(s)) {
    errors.push(`${path.relative(repoRoot, f)}: waitForTimeout is a sleep, not a condition wait — use expect(...).toBeVisible() / getByRole(...).click()`)
  }
}

if (errors.length) {
  console.error('lint: FAILED')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log('lint: ok')
process.exit(0)
