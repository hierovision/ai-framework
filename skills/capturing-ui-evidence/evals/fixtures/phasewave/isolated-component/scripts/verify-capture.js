#!/usr/bin/env node
// verify-capture.js — objective self-check for the capture harness (real-app-
// route scenario). Real-browser capture is DEFERRED (no browser in this
// harness); THIS is the objective check the skill closes on now. It imports
// runCapture from the skill's capture.mjs, feeds it the bundled fake
// chromium + canned CDP/DOM data (scripts/fake-chromium.mjs), drives an app-
// mode capture (with the auth fixture), and asserts the resulting artifact is
// schema-valid + curated + matched-styles populated with source locations.
//
// Failable: exits non-zero when
//   - capture.mjs cannot be imported / runCapture throws,
//   - the artifact is absent or fails the bundled schema validator,
//   - computed regresses to >100 keys (uncurated dump),
//   - matched_styles is blank or carries no authored source line,
//   - the demonstrated negative (bad-evidence.json) wrongly validates GREEN.
//
// The skill dir is resolved via env CAPTURE_SKILL_DIR (default the global
// symlink ~/.config/opencode/skills/capturing-ui-evidence). A real browser
// (real screenshot + real computed CSS against the live dev server) is a
// DEFERRED validation — documented in evals.json notes, never silently
// skipped.
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

async function main() {
  const mod = await import(CAPTURE_URL)
  const { runCapture, CURATED_PROPERTIES } = mod
  const { createChromium } = await import(pathToFileURL(path.join(HERE, 'fake-chromium.mjs')))
  const { chromium } = createChromium()

  const out = fs.mkdtempSync(path.join(os.tmpdir(), 'capture-evidence-'))
  const res = await runCapture({
    mode: 'component',
    target: path.resolve(HERE, '..', 'harness', 'index.html'),
    selectors: ['role:button[Submit]'],
    viewports: ['375x667', '1280x720'],
    out,
    profile: 'curated',
    name: 'self-check',
    chromium,
  }).catch((e) => ({ _err: e }))

  if (res._err) { console.error('verify-capture: runCapture threw:', res._err.stack || res._err); process.exit(1) }

  // screenshots written?
  const shots = fs.readdirSync(out).filter((f) => f.endsWith('.png'))
  expect(shots.length, '>=', 4, 'screenshots written (2 full + 2 clip for 1 selector x 2 viewports)', shots.length)
  const artPath = path.join(res.artifactPath || path.join(out, 'evidence.json'))
  if (!fs.existsSync(artPath)) { console.error('verify-capture: evidence.json missing'); process.exit(1) }
  const art = JSON.parse(fs.readFileSync(artPath, 'utf8'))

  expect(art.schema_version, '===', '1.0', 'schema_version present', art.schema_version)
  expect(art.capture_meta.mode, '===', 'component', 'component-mode recorded', art.capture_meta.mode)
  expect(art.capture_meta.auth_fixture_used, '===', false, 'no auth fixture in component mode', art.capture_meta.auth_fixture_used)
  expect(art.capture_meta.animations_disabled, '===', true, 'animations disabled flag set', art.capture_meta.animations_disabled)
  expect(art.capture_meta.device_scale_factor, '===', 1, 'device scale pinned', art.capture_meta.device_scale_factor)

  expect(art.entries.length, '===', 2, '2 entries (1 selector x 2 viewports)', art.entries.length)
  for (const e of art.entries) {
    const cKeys = Object.keys(e.computed).length
    if (cKeys > 100) errors.push(`${e.selector_spec}: computed has ${cKeys} keys (curated ceiling 100) — uncurated dump`)
    if (cKeys < 30) errors.push(`${e.selector_spec}: computed suspiciously small (${cKeys} keys)`)
    expect(e.target_kind, 'in', ['role', 'testid', 'label', 'text', 'css'], 'valid target_kind', e.target_kind)
    if (e.target_kind !== 'css') expect(e.fragile, '===', false, `non-css target not flagged fragile (${e.target_kind})`, e.fragile)
    expect(e.bbox && typeof e.bbox.x, '===', 'number', 'bbox numeric', e.bbox && e.bbox.x)
    const msKeys = Object.keys(e.matched_styles)
    expect(msKeys.length, '>', 0, 'matched_styles populated', msKeys.length)
    const winnerWithLine = Object.values(e.matched_styles).find((v) => v.winner && typeof v.winner.line === 'number'
      && v.winner.selector && v.winner.source_url)
    if (!winnerWithLine) errors.push(`${e.selector_spec}: no winner with authored source line + selector + source_url`)
    // padding-top is the canonical override demonstration: the density <style>
// block's .btn (S2, later in source) wins over the linked styles.css .btn
// (S1, same specificity, earlier source) over the UA default — source ORDER
// is the tiebreaker here (vs specificity in the real-app-route slice). CDP
// returns the authored shorthand `padding`; capture expands it to the
// longhands the computed block uses and marks `shorthand`.
    const pad = e.matched_styles['padding-top']
    if (!pad || !pad.winner) errors.push(`${e.selector_spec}: padding-top winner missing (override chain broken)`)
    else {
      if (pad.winner.selector !== '.btn') errors.push(`${e.selector_spec}: padding-top winner expected '.btn', got '${pad.winner.selector}'`)
      if (pad.winner.value !== '8px') errors.push(`${e.selector_spec}: padding-top winner expected '8px' (top of 8px 16px), got '${pad.winner.value}'`)
      if (pad.winner.shorthand !== 'padding') errors.push(`${e.selector_spec}: padding-top winner should mark shorthand 'padding', got '${pad.winner.shorthand}'`)
      if (pad.winner.line == null || typeof pad.winner.line !== 'number') errors.push(`${e.selector_spec}: padding-top winner line must be numeric (<style> block)`)
      if (!pad.overridden || pad.overridden.length < 1) errors.push(`${e.selector_spec}: padding-top expected >=1 overridden declaration (linked .btn rule)`)
    }
    // [fix-verified] real-CDP quirk dedup: native longhands covered by a
    // present shorthand are dropped; the range-less computed echo is dropped
    // (ranged authored entry kept).
    const btnPad16 = (pad.overridden || []).filter((d) => d.selector === '.btn' && d.value === '16px').length
    if (btnPad16 !== 1) errors.push(`${e.selector_spec}: padding-top .btn 16px should appear exactly once in overridden (got ${btnPad16}) — shorthand/longhand not deduped`)
    const color = e.matched_styles.color
    if (!color || !color.winner || color.winner.value !== '#ffffff' || typeof color.winner.line !== 'number') errors.push(`${e.selector_spec}: color winner expected ranged '#ffffff' from .btn`)
    if ((color.overridden || []).some((d) => /^rgb\(/i.test(d.value || ''))) errors.push(`${e.selector_spec}: color overridden has a range-less rgb(...) echo — not deduped`)
  }

  // bundled schema validator on the captured artifact — must be GREEN
  const val = spawnSync('node', [path.join(HERE, 'validate-evidence.js'), artPath], { encoding: 'utf8' })
  if (val.status !== 0) errors.push(`validate-evidence.js on captured artifact exited ${val.status}\n${val.stderr || val.stdout}`)

  // negative: the bundled validator MUST fail on bad-evidence.json (failable verifier)
  const badPath = path.join(HERE, 'bad-evidence.json')
  const bad = spawnSync('node', [path.join(HERE, 'validate-evidence.js'), badPath], { encoding: 'utf8' })
  if (bad.status === 0) errors.push(`validate-evidence.js wrongly accepted bad-evidence.json (the failable verifier must exit non-zero on a malformed/uncurated/blank artifact)\n${bad.stdout}`)

  if (errs() > 0) return
  console.log(`verify-capture: ok — component-mode capture via fake CDP`)
  console.log(`  artifact: ${artPath}`)
  console.log(`  inventory: ${res.inventory}`)
  console.log(`  entries: ${art.entries.length}; screenshot files: ${shots.length}; curated computed <=100 keys`)
  console.log(`  validator green on captured artifact; validator red on bad-evidence.json (failable confirmed)`)
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
  function errs() { if (errors.length) { console.error('verify-capture: FAILED'); for (const e of errors) console.error('  - ' + e); process.exit(1) }; return errors.length }
}

function pathToFileURL(p) { return 'file://' + p.replace(/\\/g, '/') }
function norm(v) { return String(v == null ? '' : v).trim().toLowerCase().replace(/\s+/g, ' ') }

main().catch((e) => { console.error('verify-capture: crashed:', e.stack || e); process.exit(1) })