#!/usr/bin/env node
// Project verify script: type-check. Exits non-zero when source is missing
// required exports or has obvious syntax drift. Real project would run
// `vue-tsc --noEmit`; this stub mirrors the gate without the install.

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

// 1. Required module: src/lib/offline-queue.ts must exist and export
//    queueSession. feat-offline-queue plan depends on it.
const queueFile = path.join(repoRoot, 'src', 'lib', 'offline-queue.ts')
if (!fs.existsSync(queueFile)) {
  errors.push('src/lib/offline-queue.ts not found — offline-queue module missing')
} else {
  const src = fs.readFileSync(queueFile, 'utf8')
  if (!/export\s+(function|const)\s+queueSession\b/.test(src)) {
    errors.push('src/lib/offline-queue.ts must export `queueSession`')
  }
  // 2. The queue must persist via a storage primitive (localStorage /
  //    IndexedDB) so sessions survive a reload — bare in-memory array is
  //    not a queue, it is a cache.
  if (!/localStorage|IndexedDB|indexedDB|idb/.test(src)) {
    errors.push('src/lib/offline-queue.ts must persist via localStorage or IndexedDB, not memory only')
  }
}

// 3. Brace-balance sanity on every .ts under src/ — catches obvious
//    truncation / dangling-token paste mistakes.
for (const f of walkTs(path.join(repoRoot, 'src'))) {
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