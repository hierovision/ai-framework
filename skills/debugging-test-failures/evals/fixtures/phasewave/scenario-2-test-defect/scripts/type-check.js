#!/usr/bin/env node
// Project verify script: type-check. Stub for `vue-tsc --noEmit`;
// checks required modules/exports exist and braces balance in src/.
const fs = require('fs')
const path = require('path')

const repoRoot = path.join(__dirname, '..')

function walkJs(dir) {
  const out = []
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.name === 'node_modules') continue
    const p = path.join(dir, e.name)
    if (e.isDirectory()) out.push(...walkJs(p))
    else if (e.name.endsWith('.js')) out.push(p)
  }
  return out
}

const errors = []

const listFile = path.join(repoRoot, 'src', 'lib', 'session-list.js')
if (!fs.existsSync(listFile)) {
  errors.push('src/lib/session-list.js not found — session-list module missing')
} else {
  const src = fs.readFileSync(listFile, 'utf8')
  if (!/module\.exports.*getTodaySessions|exports\.getTodaySessions/.test(src)) {
    errors.push('src/lib/session-list.js must export `getTodaySessions`')
  }
}

const displayFile = path.join(repoRoot, 'src', 'lib', 'session-display.js')
if (!fs.existsSync(displayFile)) {
  errors.push('src/lib/session-display.js not found — session-display module missing')
} else {
  const src = fs.readFileSync(displayFile, 'utf8')
  if (!/module\.exports.*formatSessionList|exports\.formatSessionList/.test(src)) {
    errors.push('src/lib/session-display.js must export `formatSessionList`')
  }
}

for (const f of walkJs(path.join(repoRoot, 'src'))) {
  const s = fs.readFileSync(f, 'utf8')
  let depth = 0
  let inStr = null
  let inLineComment = false
  let inBlockComment = false
  for (let i = 0; i < s.length; i++) {
    const c = s[i]
    const next = s[i + 1]
    if (inLineComment) { if (c === '\n') inLineComment = false; continue }
    if (inBlockComment) { if (c === '*' && next === '/') { inBlockComment = false; i++ } continue }
    if (inStr) { if (c === '\\') { i++; continue } if (c === inStr) inStr = null; continue }
    if (c === '/' && next === '/') { inLineComment = true; i++; continue }
    if (c === '/' && next === '*') { inBlockComment = true; i++; continue }
    if (c === "'" || c === '"' || c === '`') { inStr = c; continue }
    if (c === '{') depth++
    else if (c === '}') depth--
    if (depth < 0) { errors.push(`${f}: unbalanced '}'`); break }
  }
  if (depth !== 0 && !errors.some((e) => e.startsWith(f))) {
    errors.push(`${f}: unbalanced braces (depth ${depth} at EOF)`)
  }
}

if (errors.length) {
  console.error('type-check: FAILED')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log('type-check: ok')
process.exit(0)
