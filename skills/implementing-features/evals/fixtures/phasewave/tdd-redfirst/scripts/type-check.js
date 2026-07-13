#!/usr/bin/env node
// Project verify script: type-check. Exits non-zero when the planned
// module is missing its required export or has obvious syntax drift.
const fs = require('fs')
const path = require('path')

const repoRoot = path.join(__dirname, '..')
const errors = []

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

// 1. Required module: src/lib/session-score.js must exist and export
//    scoreSession (the plan's Files-to-Modify module).
const scoreFile = path.join(repoRoot, 'src', 'lib', 'session-score.js')
if (!fs.existsSync(scoreFile)) {
  errors.push('src/lib/session-score.js not found — session-score module missing')
} else {
  const src = fs.readFileSync(scoreFile, 'utf8')
  if (!/(?:export\s+(?:function|const)\s+scoreSession\b|exports\.scoreSession\s*=|module\.exports\s*=\s*\{[^}]*\bscoreSession\b)/.test(src)) {
    errors.push('src/lib/session-score.js must export `scoreSession` (ESM `export` or CommonJS `module.exports`)')
  }
}

// 2. The store must expose a `score` derived through scoreSession (plan
//    Files-to-Modify #2).
const storeFile = path.join(repoRoot, 'src', 'stores', 'focus-timer.js')
if (!fs.existsSync(storeFile)) {
  errors.push('src/stores/focus-timer.js not found')
} else {
  const src = fs.readFileSync(storeFile, 'utf8')
  if (!/scoreSession\b/.test(src)) {
    errors.push("src/stores/focus-timer.js must call scoreSession(...) to derive the session's score")
  }
}

// 3. Brace-balance sanity on every .js under src/.
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