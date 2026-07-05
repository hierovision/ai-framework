#!/usr/bin/env node
// Project verify script: lint. Stub for the real ESLint; enforces the
// project's two house rules: no `as any`, no leftover TBD/FIXME markers.

const fs = require('fs')
const path = require('path')

const repoRoot = path.join(__dirname, '..')

function walkTs(dir) {
  const out = []
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.name === 'node_modules') continue
    const p = path.join(dir, e.name)
    if (e.isDirectory()) out.push(...walkTs(p))
    else if (e.name.endsWith('.ts')) out.push(p)
  }
  return out
}

const errors = []

for (const f of walkTs(path.join(repoRoot, 'src'))) {
  const s = fs.readFileSync(f, 'utf8')
  for (const m of s.matchAll(/\bas\s+any\b/g)) {
    errors.push(`${f}: \`as any\` defeats type-checking — narrow the type instead`)
    break
  }
  if (/\bTBD\b|\bFIXME\b/.test(s)) {
    errors.push(`${f}: leftover TBD/FIXME marker — resolve or move to Open Questions`)
  }
}

if (errors.length) {
  console.error('lint: FAILED')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log('lint: ok')
process.exit(0)