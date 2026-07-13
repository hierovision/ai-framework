#!/usr/bin/env node
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
// `as any` is a TS type-cast and only lives under src/ (project rule: no
// `as any` in src/). tests/ are plain CommonJS .js with no TS, so `as
// any` there is always a comment (the AC->test mapping note) — scope the
// TS-cast check to src/ so authoring-comment reds are not false flags.
for (const f of walkJs(path.join(repoRoot, 'src'))) {
  const s = fs.readFileSync(f, 'utf8')
  if (/\bas\s+any\b/.test(s)) errors.push(f + ': `as any` — narrow the type instead')
  if (/\bTBD\b|\bFIXME\b/.test(s)) errors.push(f + ': leftover TBD/FIXME marker')
}
for (const f of walkJs(path.join(repoRoot, 'tests'))) {
  const s = fs.readFileSync(f, 'utf8')
  if (/\bTBD\b|\bFIXME\b/.test(s)) errors.push(f + ': leftover TBD/FIXME marker')
}
if (errors.length) {
  console.error('lint: FAILED')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log('lint: ok')
process.exit(0)
