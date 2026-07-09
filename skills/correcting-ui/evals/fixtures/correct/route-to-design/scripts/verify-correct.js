#!/usr/bin/env node
// verify-correct.js — objective closure for the route-to-design scenario.
// The correct response makes ZERO source edits: a "redesign the whole hero"
// request is multi-surface visual work that exceeds a single correction's
// scope and routes to designing-architecture. Closure here is NOT a green
// compare — it is "source byte-identical to pristine + a route-to-design
// handoff recorded". Any restyle edit is out-of-scope sprawl and FAILS.
const fs = require('fs')
const path = require('path')
const crypto = require('crypto')

const HERE = __dirname
const ROOT = path.join(HERE, '..')
const errors = []
const strip = (s) => s.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1').replace(/^[ \t]*@(use|forward|import)[^;]*;[ \t]*\n/gm, '').replace(/\s+/g, ' ').trim()
function norm(p) { return strip(fs.readFileSync(p, 'utf8')) }

function main() {
  const srcDir = path.join(ROOT, 'src')
  const sentinel = path.join(ROOT, 'route-to-design.txt')

  // (1) the editable styles.scss has NO rule edits vs its pristine baseline
  // (zero sprawl). Comments are stripped so header-text differences don't count.
  const stylesNorm = norm(path.join(srcDir, 'styles.scss'))
  const baseNorm = norm(path.join(srcDir, 'baseline.styles.scss'))
  if (stylesNorm !== baseNorm) errors.push('src/styles.scss was EDITED — a "redesign the whole hero" request is out of scope for correcting-ui; route to designing-architecture and make zero sprawl edits')

  // (2) a route-to-design handoff was produced. The skill writes a one-line
  // route marker to route-to-design.txt so the verifier can confirm the
  // response routed instead of restyling. FAILABLE: missing/wrong marker fails.
  let marker = ''
  try { marker = fs.readFileSync(sentinel, 'utf8').trim() } catch (e) { errors.push('route-to-design.txt missing — the skill edited source instead of routing to designing-architecture') }
  if (marker && !/route.*designing-architecture|designing-architecture.*route/i.test(marker)) {
    errors.push(`route-to-design.txt is '${marker}' — expected a route-to-designing-architecture handoff, not a restyle`)
  }

  if (errors.length) { console.error('verify-correct: FAILED'); for (const e of errors) console.error('  - ' + e); process.exit(1) }
  console.log('verify-correct: ok — route-to-design')
  console.log('  source unchanged (zero sprawl); request routed to designing-architecture')
  console.log(`  handoff: ${marker || '(marker file produced by the skill)'}`)
  console.log('  DEFERRED: real re-capture not applicable — no edit to verify (no browser in harness)')
  process.exit(0)
}
main()