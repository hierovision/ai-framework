#!/usr/bin/env node
// Project verify script: type-check. Exits non-zero when the planned
// module is missing its required export OR honors a project rule that
// the ACs DON'T name (the AGENTS convention: numeric lib inputs that
// are negative are programmer errors -> RangeError, never silent). The
// plan's ACs name only the under/over-budget happy paths; this pass's
// acceptance criteria intentionally leave the negative branch
// unmentioned so the coverage gate can reveal it as a real gap.
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

const clipFile = path.join(repoRoot, 'src', 'lib', 'clip-duration.js')
if (!fs.existsSync(clipFile)) {
  errors.push('src/lib/clip-duration.js not found — clip-duration module missing')
} else {
  const src = fs.readFileSync(clipFile, 'utf8')
  if (!/(?:export\s+(?:function|const)\s+clipDuration\b|exports\.clipDuration\s*=|module\.exports\s*=\s*\{[^}]*\bclipDuration\b)/.test(src)) {
    errors.push('src/lib/clip-duration.js must export `clipDuration` (ESM `export` or CommonJS `module.exports`)')
  }
  // AGENTS convention enforced: negative numeric lib input throws RangeError.
  if (!/RangeError/.test(src) || !/<\s*0/.test(src)) {
    errors.push('src/lib/clip-duration.js must throw RangeError on negative totalSeconds per the project rules (numeric lib inputs that are negative are programmer errors, never silent)')
  }
}

const storeFile = path.join(repoRoot, 'src', 'stores', 'clip.js')
if (!fs.existsSync(storeFile)) {
  errors.push('src/stores/clip.js not found')
} else {
  const src = fs.readFileSync(storeFile, 'utf8')
  if (!/clipDuration\b/.test(src)) {
    errors.push("src/stores/clip.js must call clipDuration(...) to derive the clip's remaining")
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