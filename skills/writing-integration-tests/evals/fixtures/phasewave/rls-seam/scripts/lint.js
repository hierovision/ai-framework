#!/usr/bin/env node
// Project verify script: lint. Stub for the real ESLint; enforces house
// rules: no `as any`, no leftover TBD/FIXME markers in src/ or tests/.
const fs = require('fs')
const path = require('path')

const repoRoot = path.join(__dirname, '..')

function walkJs(dir) {
  const out = []
  if (!fs.existsSync(dir)) return out
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.name === 'node_modules') continue
    const p = path.join(dir, e.name)
    if (e.isDirectory()) out.push(...walkJs(p))
    else if (e.name.endsWith('.js')) out.push(p)
  }
  return out
}

const errors = []
for (const f of walkJs(path.join(repoRoot, 'src')).concat(walkJs(path.join(repoRoot, 'tests')))) {
  const s = fs.readFileSync(f, 'utf8')
  if (/\bas\s+any\b/.test(s)) {
    errors.push(`${f}: \`as any\` defeats type-checking — narrow the type instead`)
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
