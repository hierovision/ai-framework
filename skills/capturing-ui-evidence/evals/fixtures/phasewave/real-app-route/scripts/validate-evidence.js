#!/usr/bin/env node
// validate-evidence.js — schema validator for the evidence artifact written
// by capture.mjs. This is CONSUMER-FACING: correcting-ui consumes a
// schema-valid artifact; this script makes that contract failable now (the
// objective check). It does NOT require a browser.
//
//   node scripts/validate-evidence.js <path-to-evidence.json>
//
// Failable: exits non-zero when the artifact is
//   - not valid JSON / missing schema_version / missing entries,
//   - computed block is uncurated (a curated-profile artifact with >MAX keys
//     — i.e. capture regressed to dumping ~300 longhands instead of curating),
//   - the matched-styles map is blank or missing source locations (the whole
//     point of the harness — without source locations correcting-ui guesses),
//   - bbox / screenshots / viewport fields are absent.
//
// MAX_COMPUTED_KEYS: a curated profile is ~80 named properties (see the
// sibling references/evidence-schema.md for the curated list). 100 is the
// ceiling — anything above it is not a curation, it is a dump. (A full
// profile artifact — --profile full — is exempt, but that is the rare case.)
const fs = require('fs')

const MAX_COMPUTED_KEYS = 100
const SCHEMA_VERSION = '1.0'
const REQUIRED_ENTRY_FIELDS = ['selector_spec', 'target_kind', 'fragile', 'viewport', 'bbox', 'screenshots', 'computed', 'matched_styles']

const path = process.argv[2]
if (!path) { console.error('usage: validate-evidence.js <evidence.json>'); process.exit(2) }

let raw, art
try { raw = fs.readFileSync(path, 'utf8') } catch (e) { fail(`cannot read ${path}: ${e.message}`) }
try { art = JSON.parse(raw) } catch (e) { fail(`invalid JSON: ${e.message}`) }

const errors = []
if (!art || typeof art !== 'object') errors.push('artifact is not an object')
if (!art.schema_version) errors.push('missing top-level schema_version')
else if (art.schema_version !== SCHEMA_VERSION) errors.push(`schema_version '${art.schema_version}' != expected '${SCHEMA_VERSION}' (drift — consumer must adapt)`)
if (!art.capture_meta) errors.push('missing capture_meta block')

const entries = art && art.entries
if (!Array.isArray(entries) || !entries.length) errors.push('entries is absent or empty — no capture was recorded')

let winnersWithSourceLine = 0
for (let i = 0; Array.isArray(entries) && i < entries.length; i++) {
  const e = entries[i]
  const tag = `entry[${i}] (${e.selector_spec || '?'})`
  for (const f of REQUIRED_ENTRY_FIELDS) {
    if (!(f in e)) errors.push(`${tag}: missing field '${f}'`)
  }
  if (e.viewport && (typeof e.viewport.width !== 'number' || typeof e.viewport.height !== 'number')) {
    errors.push(`${tag}: viewport must have numeric width/height`)
  }
  if (e.bbox && ['x', 'y', 'width', 'height'].some((k) => typeof e.bbox[k] !== 'number')) {
    errors.push(`${tag}: bbox must have numeric x/y/width/height`)
  }
  if (e.screenshots && (!e.screenshots.full || !e.screenshots.clip)) {
    errors.push(`${tag}: screenshots.{full,clip} must both be present`)
  }
  if (typeof e.target_kind === 'string' && e.target_kind === 'css' && e.fragile !== true) {
    errors.push(`${tag}: target_kind is 'css' (bare CSS) but fragile is not true — bare-CSS targets must be flagged`)
  }
  // curation
  const computed = e.computed || {}
  const computedKeys = Object.keys(computed).length
  const profile = (e.profile || (art.capture_meta && art.capture_meta.profile) || 'curated')
  if (profile === 'curated' && computedKeys > MAX_COMPUTED_KEYS) {
    errors.push(`${tag}: computed has ${computedKeys} keys (curated ceiling ${MAX_COMPUTED_KEYS}) — capture regressed to dumping longhands instead of curating`)
  }
  if (computedKeys === 0) errors.push(`${tag}: computed is empty`)

  // matched-styles map: must be populated, and at least one winner must carry an
  // authored source location (line + source_url) — that is the value of the
  // whole harness; without it the fixer guesses CSS from prose.
  const ms = e.matched_styles || {}
  const msKeys = Object.keys(ms)
  if (msKeys.length === 0) errors.push(`${tag}: matched_styles is blank — every captured property needs a winner/overridden entry`)
  // computed keys must be a SUBSET of matched_styles keys: the browser's
  // computed array may omit some curated names (logical/longhand variants),
  // but every property it DID compute must have a matched-styles entry.
  // (matched_styles always covers the full curated set; missing computed keys
  // are populated with winner:null + inherited_or_initial.)
  if (profile === 'curated') {
    const missing = Object.keys(computed).filter((k) => !Object.prototype.hasOwnProperty.call(ms, k))
    if (missing.length) errors.push(`${tag}: ${missing.length} computed prop(s) have no matched_styles entry (e.g. ${missing.slice(0, 3).join(', ')}) — they must cover the same set`)
  }
  let anyWinner = 0
  for (const prop of msKeys) {
    const v = ms[prop]
    if (!v || typeof v !== 'object') { errors.push(`${tag}.${prop}: matched_styles entry is not an object`); continue }
    if (!('winner' in v) || !('overridden' in v)) { errors.push(`${tag}.${prop}: matched_styles entry needs winner + overridden`); continue }
    if (v.winner && typeof v.winner === 'object') {
      anyWinner++
      if (!v.winner.selector) errors.push(`${tag}.${prop}: winner missing selector`)
      if (!v.winner.source_url) errors.push(`${tag}.${prop}: winner missing source_url`)
      if (!(v.winner.line == null || typeof v.winner.line === 'number')) errors.push(`${tag}.${prop}: winner.line is not numeric|null`)
      if (typeof v.winner.origin !== 'string') errors.push(`${tag}.${prop}: winner missing origin`)
    }
    if (!Array.isArray(v.overridden)) errors.push(`${tag}.${prop}: overridden must be an array`)
  }
  if (anyWinner === 0) errors.push(`${tag}: no winner carries an authored declaration — matched_styles is not populated with source rules`)
  if (anyWinner > 0 && !Object.values(ms).some((v) => v.winner && typeof v.winner.line === 'number')) {
    errors.push(`${tag}: no winner carries a numeric source line — source locations are absent, the fixer cannot map symptom to rule`)
  } else if (anyWinner > 0) winnersWithSourceLine++
}

if (errors.length) {
  console.error(`validate-evidence: FAILED (${path})`)
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log(`validate-evidence: ok — ${path} — ${entries.length} entr(ies), ${winnersWithSourceLine} with authored source locations, schema ${SCHEMA_VERSION}`)
process.exit(0)

function fail(msg) {
  console.error('validate-evidence: FAILED — ' + msg)
  process.exit(1)
}