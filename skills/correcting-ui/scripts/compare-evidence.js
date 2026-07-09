#!/usr/bin/env node
// compare-evidence.js — the loop's closure instrument. It compares two
// evidence artifacts (a "before" baseline and an "after" re-capture, both
// written by capturing-ui-evidence's harness) and asserts the TWO objective
// closure conditions for a UI correction:
//
//   (1) TARGET DELTA — the targeted computed property / geometry actually
//       moved to the expected value (the fix did what was intended), AND
//   (2) REGRESSION GUARD — no OTHER captured element's bbox or computed
//       block changed (the fix did not shift the rest of the page). This is
//       the UI-loop analogue of "the full suite is still green".
//
// A correction closes on (1) AND (2) together; either failing is not done.
// Vision ("looks better") is NOT a closure signal here — it is the final
// perceptual residue only.
//
//   node compare-evidence.js <before.json> <after.json> \
//       --target <selector_spec> \
//       --expect <prop>=<value> [--expect <prop>=<value> ...] \
//       [--guard-exclude <selector_spec> ...]   # default: the target itself
//
// Exits 0 only when: both artifacts share the same schema_version (the
// consumer GATES on the contract and STOPS on drift — it never misparses),
// the target entry's expected computed values are present, each expected
// value differs from the before AND equals the after, and every non-excluded
// entry has byte-equal bbox + computed before→after.
//
// Failable: exits non-zero when the target delta is not achieved, when a
// sibling element shifted (regression!), when the schema versions disagree
// (drift), or when the artifacts are malformed. DO NOT weaken this checker
// to make a fix "pass" — that is the cardinal rule (never green by weakening
// the net); fix the source instead.
const fs = require('fs')

function fail(msg) { console.error('compare-evidence: FAILED — ' + msg); process.exit(1) }

function parseArgs(argv) {
  const [before, after] = argv
  if (!before || !after) { console.error('usage: compare-evidence.js <before.json> <after.json> --target <spec> --expect <prop>=<value> [--guard-exclude <spec>]'); process.exit(2) }
  const out = { before, after, target: null, expect: [], guardExclude: [] }
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i]
    if (a === '--target') out.target = argv[++i]
    else if (a === '--expect') out.expect.push(argv[++i])
    else if (a === '--guard-exclude') out.guardExclude.push(argv[++i])
    else { console.error('unknown arg: ' + a); process.exit(2) }
  }
  if (!out.target) fail('--target <selector_spec> is required (which entry the fix targeted)')
  if (!out.expect.length) fail('--expect <prop>=<value> is required (the objective delta to confirm)')
  return out
}

function load(p) {
  let raw
  try { raw = fs.readFileSync(p, 'utf8') } catch (e) { fail(`cannot read ${p}: ${e.message}`) }
  try { return JSON.parse(raw) } catch (e) { fail(`${p}: invalid JSON: ${e.message}`) }
}

function findEntry(art, spec, file) {
  const e = (art.entries || []).find((x) => x.selector_spec === spec)
  if (!e) fail(`${file}: no entry matches selector_spec '${spec}' (capture must have included the target)`)
  return e
}

const args = parseArgs(process.argv.slice(2))
const before = load(args.before)
const after = load(args.after)
const errors = []

// GATE on schema_version — the artifact is a CONTRACT. Drift is a STOP, not a
// guess. A consumer that reads a version it does not understand must surface
// the drift (evidence-schema.md → Versioning + drift).
const SV = '1.0'
if (before.schema_version !== SV) errors.push(`before.schema_version is '${before.schema_version}' != '${SV}' (drift — STOP, do not misparse)`)
if (after.schema_version !== SV) errors.push(`after.schema_version is '${after.schema_version}' != '${SV}' (drift — STOP, do not misparse)`)
if (!Array.isArray(before.entries) || !Array.isArray(after.entries)) errors.push('both artifacts need an entries[] array')

// (1) TARGET DELTA — each expected computed value must differ from the
// before AND equal the after (the objective measurement the intent named).
const bTarget = findEntry(before, args.target, 'before')
const aTarget = findEntry(after, args.target, 'after')
for (const spec of args.expect) {
  const eq = spec.indexOf('=')
  if (eq < 0) { errors.push(`bad --expect '${spec}' (need <prop>=<value>)`); continue }
  const prop = spec.slice(0, eq), want = spec.slice(eq + 1)
  const bVal = bTarget.computed && bTarget.computed[prop]
  const aVal = aTarget.computed && aTarget.computed[prop]
  if (bVal === want) errors.push(`target delta HOLD for ${prop}: before was already '${want}' (${args.target}) — not a fix, a no-op`)
  if (aVal !== want) errors.push(`target delta MISS for ${prop}: expected '${want}', after computed '${aVal}' (${args.target})`)
}

// (2) REGRESSION GUARD — every entry NOT excluded (default: the target
// itself) must have byte-equal bbox + computed before→after. A fix that hits
// the target but shifts a sibling is NOT done — it traded a regression.
const exclude = new Set([args.target, ...args.guardExclude])
const specs = new Set([...(before.entries || []).map((e) => e.selector_spec), ...(after.entries || []).map((e) => e.selector_spec)])
for (const spec of specs) {
  if (exclude.has(spec)) continue
  const b = (before.entries || []).find((e) => e.selector_spec === spec)
  const a = (after.entries || []).find((e) => e.selector_spec === spec)
  if (!b || !a) { errors.push(`regression guard cannot compare '${spec}' (missing from one artifact)`); continue }
  const bBbox = JSON.stringify(b.bbox || {}), aBbox = JSON.stringify(a.bbox || {})
  if (bBbox !== aBbox) errors.push(`regression GUARD TRIPPED on '${spec}' bbox changed\n  before ${bBbox}\n  after  ${aBbox}`)
  const bComp = JSON.stringify(b.computed || {}), aComp = JSON.stringify(a.computed || {})
  if (bComp !== aComp) errors.push(`regression GUARD TRIPPED on '${spec}' computed changed (the fix shifted a sibling's cascade)`)
}

if (errors.length) {
  console.error('compare-evidence: FAILED (closure NOT reached)')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log(`compare-evidence: ok — target '${args.target}' delta achieved (${args.expect.length} prop(s)); regression guard clean`)
process.exit(0)