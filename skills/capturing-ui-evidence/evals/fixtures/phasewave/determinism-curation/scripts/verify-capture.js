#!/usr/bin/env node
// verify-capture.js — objective self-check for the determinism/curation slice.
// Real-browser capture is DEFERRED; THIS is the objective check. It drives
// runCapture TWICE against the bundled fake chromium + canned CDP/DOM data and
// asserts the two artifacts are BYTE-EQUAL (determinism — the load-bearing
// property; a nondeterministic capture poisons the downstream diff), that the
// bare-CSS target is flagged fragile, that the computed profile is curated
// (<<300 longhands), and that the structural determinism grep is green.
//
// Failable: exits non-zero when runCapture throws, the two runs differ, a
// css target fails to flag fragile, computed regresses to >100 keys,
// matched_styles is blank, or the bundled validator wrongly accepts
// bad-evidence.json. The skill dir is resolved via env CAPTURE_SKILL_DIR.
const fs = require('fs')
const os = require('os')
const path = require('path')
const { spawnSync } = require('child_process')

const SCHEMES = [
  process.env.CAPTURE_SKILL_DIR,
  path.join(os.homedir(), '.config/opencode/skills/capturing-ui-evidence'),
  path.resolve(__dirname, '..', '..', '..', '..', '..', 'skills', 'capturing-ui-evidence'),
].filter(Boolean)
const SKILL_DIR = SCHEMES.find((d) => fs.existsSync(path.join(d, 'scripts', 'capture.mjs')))
if (!SKILL_DIR) { console.error('verify-capture: could not locate capture.mjs — set CAPTURE_SKILL_DIR'); process.exit(1) }
const CAPTURE_URL = 'file://' + path.join(SKILL_DIR, 'scripts', 'capture.mjs').replace(/\\/g, '/')
const HERE = __dirname
const errors = []

async function runOnce(mod, chromiumP, out) {
  const { createChromium } = await import(chromiumP)
  const { chromium } = createChromium()
  return mod.runCapture({
    mode: 'component',
    target: path.resolve(HERE, '..', 'harness', 'index.html'),
    selectors: ['css:.legacy-action'],
    viewports: ['375x667', '1280x720'],
    out, profile: 'curated', name: 'stable',
    now: () => 0, // deterministic clock — metadata only, kept out of the diff
    chromium,
  })
}

async function main() {
  const mod = await import(CAPTURE_URL)
  const { runCapture } = mod
  const chromiumP = 'file://' + path.join(HERE, 'fake-chromium.mjs').replace(/\\/g, '/')

  const outA = fs.mkdtempSync(path.join(os.tmpdir(), 'cap-det-a-'))
  const outB = fs.mkdtempSync(path.join(os.tmpdir(), 'cap-det-b-'))
  const resA = await runOnce(mod, chromiumP, outA).catch((e) => ({ _err: e }))
  const resB = await runOnce(mod, chromiumP, outB).catch((e) => ({ _err: e }))
  if (resA._err) { console.error('verify-capture: run A threw:', resA._err.stack || resA._err); process.exit(1) }
  if (resB._err) { console.error('verify-capture: run B threw:', resB._err.stack || resB._err); process.exit(1) }

  const artA = fs.readFileSync(path.join(outA, 'evidence.json'), 'utf8')
  const artB = fs.readFileSync(path.join(outB, 'evidence.json'), 'utf8')
  if (artA !== artB) errors.push('determinism BROKEN: the two runs produced different evidence.json (capture is not reproducible — the downstream diff is poisoned)')

  const art = JSON.parse(artA)
  expect(art.schema_version, '===', '1.0', 'schema_version present', art.schema_version)
  expect(art.capture_meta.mode, '===', 'component', 'component-mode recorded', art.capture_meta.mode)
  expect(art.capture_meta.animations_disabled, '===', true, 'animations disabled flag', art.capture_meta.animations_disabled)
  expect(art.capture_meta.device_scale_factor, '===', 1, 'device scale pinned', art.capture_meta.device_scale_factor)
  expect(art.entries.length, '===', 2, '2 entries (1 selector x 2 viewports)', art.entries.length)

  for (const e of art.entries) {
    expect(e.target_kind, '===', 'css', 'bare-CSS target marked target_kind css', e.target_kind)
    expect(e.fragile, '===', true, 'bare-CSS target MUST be flagged fragile (so the fixer knows the target was a last-resort address)', e.fragile)
    const cKeys = Object.keys(e.computed).length
    if (cKeys > 100) errors.push(`${e.selector_spec}: computed has ${cKeys} keys (curated ceiling 100) — uncurated`)
    if (cKeys < 30) errors.push(`${e.selector_spec}: computed suspiciously small (${cKeys} keys)`)
    expect(Object.keys(e.matched_styles).length, '>', 0, 'matched_styles populated', Object.keys(e.matched_styles).length)
    const winnerWithLine = Object.values(e.matched_styles).find((v) => v.winner && typeof v.winner.line === 'number' && v.winner.selector && v.winner.source_url)
    if (!winnerWithLine) errors.push(`${e.selector_spec}: no winner with authored source line + selector + source_url`)
    const pad = e.matched_styles['padding-top']
    if (!pad || !pad.winner || pad.winner.selector !== '.legacy-action' || pad.winner.value !== '16px') {
      errors.push(`${e.selector_spec}: padding-top winner expected '.legacy-action' / '16px', got ${JSON.stringify(pad && pad.winner)}`)
    }
    // [fix-verified] real-CDP quirk dedup: shorthand + expanded longhands not
    // double-counted; range-less computed echo dropped (ranged authored kept).
    const laPad16 = ((pad.winner ? [pad.winner] : []).concat(pad.overridden || [])).filter((d) => d.selector === '.legacy-action' && d.value === '16px').length
    if (laPad16 !== 1) errors.push(`${e.selector_spec}: padding-top .legacy-action 16px should appear once (got ${laPad16}) — shorthand/longhand not deduped`)
    const color = e.matched_styles.color
    if (!color || !color.winner || color.winner.value !== '#ffffff' || typeof color.winner.line !== 'number') errors.push(`${e.selector_spec}: color winner expected ranged '#ffffff' from .legacy-action`)
    if ((color.overridden || []).some((d) => /^rgb\(/i.test(d.value || ''))) errors.push(`${e.selector_spec}: color overridden has a range-less rgb(...) echo — not deduped`)
  }

  const artPath = path.join(outA, 'evidence.json')
  const val = spawnSync('node', [path.join(HERE, 'validate-evidence.js'), artPath], { encoding: 'utf8' })
  if (val.status !== 0) errors.push(`validate-evidence.js on captured artifact exited ${val.status}\n${val.stderr || val.stdout}`)
  const bad = spawnSync('node', [path.join(HERE, 'validate-evidence.js'), path.join(HERE, 'bad-evidence.json')], { encoding: 'utf8' })
  if (bad.status === 0) errors.push(`validate-evidence.js wrongly accepted bad-evidence.json (failable verifier must exit non-zero)\n${bad.stdout}`)

  // structural determinism grep on the skill's capture.mjs (no live browser):
  const det = spawnSync('node', [path.join(HERE, 'check-determinism.js')], { encoding: 'utf8' })
  if (det.status !== 0) errors.push(`check-determinism.js exited ${det.status}\n${det.stderr || det.stdout}`)

  if (errors.length) { console.error('verify-capture: FAILED'); for (const e of errors) console.error('  - ' + e); process.exit(1) }
  console.log('verify-capture: ok — determinism/curation')
  console.log(`  two runs byte-equal; artifact: ${artPath}`)
  console.log(`  inventory: ${resA.inventory}`)
  console.log(`  entries: ${art.entries.length}; css target flagged fragile; curated computed <=100 keys`)
  console.log(`  validator green on captured; validator red on bad-evidence.json; check-determinism green`)
  console.log(`  DEFERRED: real screenshot + real computed CSS against the live harness/index.html (no browser in harness)`)
  process.exit(0)

  function expect(actual, op, want, label, got) {
    let ok = false
    if (op === '===') ok = actual === want
    else if (op === 'in') ok = Array.isArray(want) && want.includes(actual)
    else if (op === '>=') ok = typeof actual === 'number' && actual >= want
    else if (op === '>') ok = typeof actual === 'number' && actual > want
    if (!ok) errors.push(`expected ${label} ${want}, got ${JSON.stringify(got)}`)
  }
}
main().catch((e) => { console.error('verify-capture: crashed:', e.stack || e); process.exit(1) })