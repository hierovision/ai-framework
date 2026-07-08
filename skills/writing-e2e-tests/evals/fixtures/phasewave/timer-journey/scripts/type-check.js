#!/usr/bin/env node
// Project verify script: type-check (stub). Confirms the e2e spec and
// auth fixture exist and braces/parens balance. Real type-check is
// `vue-tsc --noEmit` in the full project.
const fs = require('fs')
const path = require('path')

const repoRoot = path.join(__dirname, '..')
const errors = []

const specDir = path.join(repoRoot, 'e2e')
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

const files = walkTs(specDir)
const specFiles = files.filter((f) => f.endsWith('.spec.ts'))
if (specFiles.length === 0) {
  errors.push('no e2e/*.spec.ts found — author the journey spec')
}

for (const f of files) {
  const s = fs.readFileSync(f, 'utf8')
  let depth = 0
  let inStr = null
  let inLineComment = false
  for (let i = 0; i < s.length; i++) {
    const c = s[i]
    const next = s[i + 1]
    if (inLineComment) { if (c === '\n') inLineComment = false; continue }
    if (inStr) { if (c === '\\') { i++; continue } if (c === inStr) inStr = null; continue }
    if (c === '/' && next === '/') { inLineComment = true; i++; continue }
    if (c === "'" || c === '"' || c === '`') { inStr = c; continue }
    if (c === '{') depth++
    else if (c === '}') depth--
    if (depth < 0) { errors.push(`${path.relative(repoRoot, f)}: unbalanced '}'`); break }
  }
  if (depth !== 0 && !errors.some((e) => e.endsWith('unbalanced \'}\'') && e.startsWith(path.relative(repoRoot, f)))) {
    errors.push(`${path.relative(repoRoot, f)}: unbalanced braces (depth ${depth} at EOF)`)
  }
}

if (errors.length) {
  console.error('type-check: FAILED')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log('type-check: ok')
process.exit(0)
