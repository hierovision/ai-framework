#!/usr/bin/env node
// Red-first type-check: brace-balance only (does NOT require the
// planned module to exist — the module is intentionally absent in the
// red-first state; requiring it would mask the test's natural failure).
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
for (const f of walkJs(path.join(repoRoot, 'src'))) {
  const s = fs.readFileSync(f, 'utf8')
  let depth = 0
  for (let i = 0; i < s.length; i++) {
    const c = s[i]
    if (c === '{') depth++
    else if (c === '}') depth--
    if (depth < 0) { errors.push(`${f}: unbalanced '}'`); break }
  }
  if (depth !== 0 && !errors.some((e) => e.startsWith(f))) {
    errors.push(`${f}: unbalanced braces`)
  }
}

if (errors.length) {
  console.error('type-check: FAILED')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log('type-check: ok')
process.exit(0)