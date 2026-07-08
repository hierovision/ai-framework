#!/usr/bin/env node
// Project verify script: type-check. Stub for `vue-tsc --noEmit`;
// checks required modules/exports exist and braces balance in src/ and
// tests/.
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

function mustExport(file, re, label) {
  if (!fs.existsSync(file)) {
    errors.push(label + ' not found')
    return
  }
  const src = fs.readFileSync(file, 'utf8')
  if (!re.test(src)) errors.push(label + ' must export the expected symbol')
}

mustExport(path.join(repoRoot, 'src', 'stores', 'focus-timer-store.js'),
  /module\.exports.*createFocusTimerStore|exports\.createFocusTimerStore/, 'src/stores/focus-timer-store.js')
mustExport(path.join(repoRoot, 'src', 'supabase', 'fake-client.js'),
  /module\.exports.*createClient|exports\.createClient/, 'src/supabase/fake-client.js')
mustExport(path.join(repoRoot, 'db', 'policies.js'),
  /module\.exports.*focusSessionsPolicy|exports\.focusSessionsPolicy/, 'db/policies.js')

for (const f of walkJs(path.join(repoRoot, 'src')).concat(walkJs(path.join(repoRoot, 'tests')))) {
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
