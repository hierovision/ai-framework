#!/usr/bin/env node
// Project verify script: test. Stub for the real Vitest; asserts the
// behaviour feat-offline-queue plans: focus-timer's start() must route
// its insert through queueSession() rather than a direct supabase insert.
// Exits non-zero when the routing is missing or wrong.

const fs = require('fs')
const path = require('path')

const repoRoot = path.join(__dirname, '..')
const storeFile = path.join(repoRoot, 'src', 'stores', 'focus-timer.ts')

if (!fs.existsSync(storeFile)) {
  console.error('test: FAILED — src/stores/focus-timer.ts not found')
  process.exit(1)
}

const src = fs.readFileSync(storeFile, 'utf8')

function extractActionBody(src, name) {
  const re = new RegExp(`(?:async\\s+)?${name}\\s*\\([^)]*\\)\\s*{`)
  const m = re.exec(src)
  if (!m) return null
  let depth = 0
  let i = m.index + m[0].length - 1 // at the opening {
  const start = i + 1
  let inStr = null
  let inLineComment = false
  let inBlockComment = false
  for (; i < src.length; i++) {
    const c = src[i]
    const next = src[i + 1]
    if (inLineComment) { if (c === '\n') inLineComment = false; continue }
    if (inBlockComment) { if (c === '*' && next === '/') { inBlockComment = false; i++ } continue }
    if (inStr) { if (c === '\\') { i++; continue } if (c === inStr) inStr = null; continue }
    if (c === '/' && next === '/') { inLineComment = true; i++; continue }
    if (c === '/' && next === '*') { inBlockComment = true; i++; continue }
    if (c === "'" || c === '"' || c === '`') { inStr = c; continue }
    if (c === '{') depth++
    else if (c === '}') { depth--; if (depth === 0) return src.slice(start, i) }
  }
  return null
}

const errors = []

const startBody = extractActionBody(src, 'start')
if (!startBody) {
  errors.push('could not find start(...) action body in focus-timer.ts')
} else {
  // Routing discipline: start() must call queueSession(...) before/at the
  // point where the session is created — direct supabase insert bypasses
  // the offline queue and fails the queueing criterion.
  if (!/queueSession\s*\(/.test(startBody)) {
    errors.push('start() does not call queueSession(...) — the offline queue is bypassed; feature absent')
  }
  // Direct-write regression guard: the store must NOT keep the bare
  // `supabase.from(\'focus_sessions\').insert(...)` call in start() — that
  // path is what the plan replaces.
  if (/supabase\.from\([^)]*focus_sessions[^)]*\)\s*\.insert\(/.test(startBody)) {
    errors.push('start() still calls supabase.from(\'focus_sessions\').insert(...) directly — the offline queue is not the mutation path')
  }
}

if (errors.length) {
  console.error('test: FAILED')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log('test: ok')
process.exit(0)