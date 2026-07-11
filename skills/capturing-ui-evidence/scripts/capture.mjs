#!/usr/bin/env node
// capture.mjs — deterministic UI evidence capture harness (Playwright + CDP).
//
// Run (execute — do not reimplement): the agent INVOKES this script to
// capture a structured evidence artifact for correcting-ui to consume.
// It is the UI loop's "reproduce" step: it makes the visual state
// observable and machine-comparable. It does NOT diagnose or edit.
//
//   node scripts/capture.mjs \
//     --mode app --target http://localhost:5173 --route /dashboard \
//     --selectors "role:button[Submit],testid:submit-btn" \
//     --viewports 375x667,1280x720 \
//     --out ./evidence --auth-fixture e2e/fixtures/auth.mjs
//
//   node scripts/capture.mjs \
//     --mode component --target ./harness/index.html \
//     --selectors "role:button[Submit]" \
//     --viewports 375x667,1280x720 --out ./evidence
//
// EVIDENCE ARTIFACT (per run, written to <out>):
//   - <name>-full-<W>x<H>.png         full-page screenshot, one per viewport
//   - <name>-clip-<slug>-<W>x<H>.png  element-clipped screenshot, per (selector x viewport)
//   - evidence.json                   schema-versioned structured evidence (see
//                                    references/evidence-schema.md — the contract
//                                    correcting-ui consumes; do not duplicate here)
//
// Selected, documented, justified curated CSS properties (NOT all ~300
// longhands) live in CURATED_PROPERTIES below and in references/evidence-schema.md.
// Pass --profile full only when the curated set misses the property under
// investigation (it is verbose and rarely needed).
//
// DETERMINISM (load-bearing — a nondeterministic capture poisons the
// downstream diff): animations + transitions are disabled, fonts + load
// are awaited, a layout-stability condition is polled (never a fixed
// timeout), and viewport + device scale factor are pinned.

// ---------------------------------------------------------------------------
// Curated CSS profile — the named, documented set. See
// references/evidence-schema.md for the one-line "why" per group.  Keep this
// array and that document in agreement; the validator cross-checks counts.
// ---------------------------------------------------------------------------
const CURATED_PROPERTIES = [
  // box model — geometry the layout critique measures against
  'width', 'height', 'box-sizing',
  'min-width', 'min-height', 'max-width', 'max-height',
  'margin-top', 'margin-right', 'margin-bottom', 'margin-left',
  'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
  'border-top-width', 'border-right-width', 'border-bottom-width', 'border-left-width',
  // layout (flex / grid) — how the box participates in its container
  'display', 'flex-direction', 'flex-wrap', 'justify-content', 'align-items',
  'align-content', 'align-self', 'flex-grow', 'flex-shrink', 'flex-basis',
  'gap', 'row-gap', 'column-gap',
  'grid-template-columns', 'grid-template-rows', 'grid-column', 'grid-row',
  'grid-area', 'order',
  // positioning — where the box sits / stacks
  'position', 'inset', 'top', 'right', 'bottom', 'left', 'z-index', 'float', 'clear',
  // typography — text metrics + flow the critique reads for legibility/overflow
  'font-family', 'font-size', 'font-weight', 'font-style', 'line-height',
  'letter-spacing', 'text-align', 'text-decoration', 'text-transform',
  'text-overflow', 'white-space', 'word-break', 'overflow-wrap',
  // color / background — theme-token usage + contrast
  'color', 'background-color', 'background-image', 'background-size',
  'background-position', 'opacity',
  // borders — shape + rounding + token adherence
  'border-style', 'border-top-style', 'border-right-style',
  'border-bottom-style', 'border-left-style',
  'border-color', 'border-top-color', 'border-right-color',
  'border-bottom-color', 'border-left-color',
  'border-radius', 'border-top-left-radius', 'border-top-right-radius',
  'border-bottom-right-radius', 'border-bottom-left-radius',
]

const SCHEMA_VERSION = '1.0'

// Determinism: injected once per context to freeze transient motion so the
// same input yields the same computed values across runs.
const FREEZE_CSS = `
  *:not(svg *) {
    animation: none !important;
    transition: none !important;
    scroll-behavior: auto !important;
    caret-color: transparent !important;
  }
`

// ---------------------------------------------------------------------------
// Exports (importable by the objective self-check stub, which injects a fake
// Playwright + CDP surface so the run never requires a real browser install).
// ---------------------------------------------------------------------------
export { runCapture, parseSelectorSpec, resolveTarget, CURATED_PROPERTIES, SCHEMA_VERSION }

// ---------------------------------------------------------------------------
// Selector-spec parsing — target-resolution discipline (role > accessible
// name / label > testid > text > css). A bare-css spec is flagged fragile so
// the downstream fixer knows the target was a last-resort address.
// ---------------------------------------------------------------------------
function parseSelectorSpec(spec) {
  const s = String(spec).trim()
  const m =
    /^role:([a-z][a-z-]*)\[(.+?)\](?:\/exact)?$/i.exec(s) ||
    /^label:(.+)$/i.exec(s) ||
    /^testid:(.+)$/i.exec(s) ||
    /^text:(.+)$/i.exec(s) ||
    /^css:(.+)$/i.exec(s)
  if (m && /^role:/.test(s)) {
    return { kind: 'role', role: m[1].toLowerCase(), name: m[2], exact: /\/exact$/.test(s), fragile: false }
  }
  if (m && /^label:/.test(s)) return { kind: 'label', name: m[1], fragile: false }
  if (m && /^testid:/.test(s)) return { kind: 'testid', id: m[1], fragile: false }
  if (m && /^text:/.test(s)) return { kind: 'text', text: m[1], fragile: false }
  if (m && /^css:/.test(s)) return { kind: 'css', css: m[1], fragile: true }
  // Unprefixed → treat as bare CSS (last resort, flagged).
  return { kind: 'css', css: s, fragile: true }
}

function resolveTarget(page, spec) {
  const p = typeof spec === 'string' ? parseSelectorSpec(spec) : spec
  switch (p.kind) {
    case 'role':
      return page.getByRole(p.role, { name: p.name, exact: !!p.exact })
    case 'label':
      return page.getByLabelText(p.name)
    case 'testid':
      return page.getByTestId(p.id)
    case 'text':
      return page.getByText(p.text)
    case 'css':
      return page.locator(p.css)
  }
  throw new Error('unreachable selector kind: ' + p.kind)
}

// ---------------------------------------------------------------------------
// Cascade precedence — produce a comparable tuple so the winning authored
// declaration (and what it overrode) can be identified deterministically.
// Derived from CSS Cascading 4: tier = origin x importance; specificity then
// source order then break ties. Inline declarations carry an effective
// (pseudo-1e9) specificity so they out-rank any author selector without
// !important, exactly as the spec specifies.
// ---------------------------------------------------------------------------
function originTier(origin, important, isInline) {
  const author = isInline || origin === 'regular' || origin === undefined || origin === 'inspector'
  if (author) return important ? 6 : 5
  if (origin === 'user') return important ? 4 : 3
  // user-agent (UA) sheet
  return important ? 2 : 1
}

function precedence({ origin, important, specificity, isInline, absLine, absColumn }) {
  const sp = specificity || { a: 0, b: 0, c: 0 }
  const a = isInline ? 1e9 : sp.a
  const b = isInline ? 0 : sp.b
  const c = isInline ? 0 : sp.c
  return [originTier(origin, important, isInline), a, b, c, absLine || 0, absColumn || 0]
}

function norm(v) {
  return String(v == null ? '' : v).trim().toLowerCase().replace(/\s+/g, ' ')
}

// ---------------------------------------------------------------------------
// runCapture — the core entry. Accepts an injected `chromium` surface so the
// objective self-check can feed canned CDP/DOM data; the CLI main() supplies
// the real Playwright chromium.
// ---------------------------------------------------------------------------
async function runCapture(opts) {
  const {
    mode = 'app',      // 'app' | 'component'
    target,            // app: dev-server URL (http://localhost:5173); component: harness HTML path
    route = '',        // app mode: route appended to target (e.g. /dashboard)
    selectors = [],    // array of selector-spec strings
    viewports = [],    // array of 'WxH'
    out,               // output directory
    profile = 'curated', // 'curated' | 'full'
    name = 'capture',
    authFixturePath,   // app mode: optional path to an auth-fixture .mjs (default export setup(context))
    chromium,          // injected Playwright chromium (or fake) — required
    chromiumLaunchOptions = {}, // optional chromium.launch() opts — reuse a host chromium via executablePath
    now = () => 0,     // deterministic clock (metadata only; kept out of the diff)
  } = opts

  if (!chromium) throw new Error('runCapture requires a `chromium` surface (real Playwright or a fake)')
  if (!target) throw new Error('--target is required')
  if (!out) throw new Error('--out is required')
  if (!selectors.length) throw new Error('at least one --selectors spec is required')
  if (!viewports.length) throw new Error('at least one --viewport is required')

  const fs = await import('node:fs/promises')
  const path = await import('node:path')
  const urlMod = await import('node:url')

  await fs.mkdir(out, { recursive: true })
  const parsedSelectors = selectors.map(parseSelectorSpec)
  const viewportSpecs = viewports.map(parseViewport)
  const wantFull = profile === 'full'

  const browser = await chromium.launch(chromiumLaunchOptions)
  const context = await browser.newContext({
    viewport: { width: viewportSpecs[0].width, height: viewportSpecs[0].height },
    deviceScaleFactor: 1, // pinned — device scale would perturb computed values + screenshots
    isMobile: false,
    hasTouch: false,
  })
  // Inject the freeze CSS as a <style> (addInitScript evaluates JS, not CSS —
  // a bare CSS string would throw a JS syntax error before the page loads).
  await context.addInitScript((css) => {
    const el = document.createElement('style')
    el.setAttribute('data-capture-freeze', 'true')
    el.textContent = css
    ;(document.documentElement || document.head || document.body).appendChild(el)
  }, FREEZE_CSS)
  const page = await context.newPage()
  await page.emulateMedia({ reducedMotion: 'reduce' }) // freeze transient motion at the UA level

  // app mode: optional auth fixture (the e2e auth-fixture pattern) before goto.
  let authUsed = false
  if (mode === 'app' && authFixturePath) {
    const authMod = await import(urlMod.pathToFileURL(path.resolve(authFixturePath)).href)
    const setup = authMod.default
    if (typeof setup !== 'function') throw new Error('--auth-fixture must default-export setup(context)')
    await setup(context)
    authUsed = true
  }

  // CDP session + stylesheet-header collection (enabled once for the page).
  const client = await context.newCDPSession(page)
  const sheets = {}
  client.on('CSS.styleSheetAdded', (h) => { sheets[h.styleSheetId] = h })
  await client.send('DOM.enable')
  await client.send('CSS.enable')

  const entries = []
  let pageUrl
  let markerCounter = 0

  for (const vp of viewportSpecs) {
    await page.setViewportSize({ width: vp.width, height: vp.height })

    // Navigate. Condition waits only, never waitForTimeout.
    if (mode === 'component') {
      const fileUrl = urlMod.pathToFileURL(path.resolve(target)).href
      await page.goto(fileUrl, { waitUntil: 'networkidle' })
      pageUrl = fileUrl
    } else {
      await page.goto(joinUrl(target, route), { waitUntil: 'networkidle' })
      pageUrl = page.url()
    }

    await page.evaluate(() => document.fonts ? document.fonts.ready : null)
    await page.waitForFunction(() => document.readyState === 'complete')
    await waitForStableLayout(page)

    const fullPng = path.join(out, `${name}-full-${vp.width}x${vp.height}.png`)
    await page.screenshot({ path: fullPng, fullPage: true })

    for (const spec of parsedSelectors) {
      const locator = resolveTarget(page, spec)
      const handle = await locator.elementHandle()
      if (!handle) throw new Error(`target not found: ${specRaw(spec)}`)

      const bbox = await handle.boundingBox()
      // Resolve the CDP nodeId WITHOUT relying on a private ElementHandle field
      // (the field name varies across Playwright versions and may be absent).
      // Stamp a unique attribute on the resolved element, then query the DOM
      // for it via CDP — version-robust and works against a fake chromium.
      const marker = `cap-target-${++markerCounter}`
      await handle.evaluate((el, m) => el.setAttribute('data-capture-target', m), marker)
      const { root } = await client.send('DOM.getDocument', { depth: -1, pierce: true })
      const { nodeIds } = await client.send('DOM.querySelectorAll', {
        nodeId: root.nodeId, selector: `[data-capture-target="${marker}"]`,
      })
      const nodeId = nodeIds && nodeIds[0]
      if (!nodeId) throw new Error(`could not resolve a CDP nodeId for: ${specRaw(spec)}`)
      await client.send('DOM.removeAttribute', { nodeId, name: 'data-capture-target' }).catch(() => {})

      const { computedStyle } = await client.send('CSS.getComputedStyleForNode', { nodeId })
      const matched = await client.send('CSS.getMatchedStylesForNode', { nodeId })
      const inlineRes = await client.send('CSS.getInlineStylesForNode', { nodeId }).catch(() => ({ inlineStyle: null }))

      const computed = pickComputed(computedStyle, wantFull)
      const matchedStyles = buildMatchedStyles({
        matched, inlineStyle: inlineRes.inlineStyle, sheets, pageUrl,
        curated: wantFull ? null : new Set(CURATED_PROPERTIES),
      })

      const slug = sanitize(specRaw(spec))
      const clipPng = path.join(out, `${name}-clip-${slug}-${vp.width}x${vp.height}.png`)
      await handle.screenshot({ path: clipPng })

      entries.push({
        selector_spec: specRaw(spec),
        target_kind: spec.kind,
        fragile: !!spec.fragile,
        viewport: { width: vp.width, height: vp.height },
        bbox: bbox ? roundBox(bbox) : null,
        screenshots: { full: path.basename(fullPng), clip: path.basename(clipPng) },
        profile: wantFull ? 'full' : 'curated',
        computed,
        matched_styles: matchedStyles,
      })
    }
  }

  const capture_meta = {
    schema_version: SCHEMA_VERSION,
    mode,
    target,
    route: mode === 'app' ? route : null,
    viewports: viewports.slice(),
    selectors: selectors.slice(),
    profile: wantFull ? 'full' : 'curated',
    name,
    auth_fixture_used: authUsed,
    device_scale_factor: 1,
    animations_disabled: true,
    capture_clock: typeof now === 'function' ? now() : now, // metadata only — excluded from diffs
    inventory: `screenshots=${entries.length * 2}, entries=${entries.length}, selectors=${parsedSelectors.length}, viewports=${viewportSpecs.length}, profile=${wantFull ? 'full' : 'curated'}`,
  }

  const artifact = {
    schema_version: SCHEMA_VERSION,
    capture_meta,
    entries,
  }
  const artifactPath = path.join(out, 'evidence.json')
  await fs.writeFile(artifactPath, JSON.stringify(artifact, null, 2) + '\n', 'utf8')
  await browser.close()

  return { artifactPath, inventory: capture_meta.inventory, entries: entries.length }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function parseViewport(v) {
  const m = /^(\d+)x(\d+)$/.exec(String(v).trim())
  if (!m) throw new Error(`bad viewport '${v}' — expected WxH (e.g. 375x667)`)
  return { width: +m[1], height: +m[2] }
}

function specRaw(spec) {
  if (typeof spec === 'string') return spec
  switch (spec.kind) {
    case 'role': return `role:${spec.role}[${spec.name}]`
    case 'label': return `label:${spec.name}`
    case 'testid': return `testid:${spec.id}`
    case 'text': return `text:${spec.text}`
    case 'css': return `css:${spec.css}`
  }
  return JSON.stringify(spec)
}

function sanitize(s) {
  return String(s).replace(/[^a-z0-9._-]+/gi, '_').slice(0, 40)
}

function joinUrl(base, route) {
  return String(base).replace(/\/$/, '') + (route || '')
}

// Resolve the CDP nodeId for a Playwright ElementHandle via a stamped DOM
// attribute + DOM.querySelectorAll (see runCapture). Kept here only for
// reference; the inline impl in runCapture is what runs. The previous
// private-field approach (`handle._objectId`) broke across Playwright versions
// where the field is absent — the marker-query is version-robust.

function roundBox(b) {
  return {
    x: round(b.x), y: round(b.y),
    width: round(b.width), height: round(b.height),
  }
}
function round(n) { return Math.round((n + Number.EPSILON) * 100) / 100 }

function pickComputed(computedStyle, wantFull) {
  // CDP's getComputedStyleForNode return shape varies by Chrome version:
  // some return { computedStyle: { cssProperties: [...] } }, others return
  // { computedStyle: [ {name, value}, ... ] } (a flat array). Accept either.
  const props = computedStyle
    ? (Array.isArray(computedStyle) ? computedStyle
       : (Array.isArray(computedStyle.cssProperties) ? computedStyle.cssProperties : []))
    : []
  const all = {}
  for (const p of props) {
    if (p && p.name && p.value != null) all[p.name] = p.value
  }
  if (wantFull) return all
  const out = {}
  for (const k of CURATED_PROPERTIES) if (k in all) out[k] = all[k]
  return out
}

// Build the per-property matched-styles map: for each (curated or all)
// property, the winning authored declaration + the overridden set, each
// carrying selector + source URL + line/column so correcting-ui can map a
// visual symptom to the exact source rule instead of guessing.
// Authored shorthand → curated longhands. CDP's CSS.getMatchedStylesForNode
// returns declarations *as authored* (`padding: 16px 24px` stays a single
// shorthand entry), while getComputedStyleForNode yields only longhands. To
// keep the matched-styles map keyed on the SAME longhand names the computed
// block uses (so a winner exists for every captured longhand), expand an
// authored shorthand into its constituent longhands, carrying the same source
// range and marking `shorthand` so the fixer knows the declaration it must
// edit is the shorthand, not each longhand.
const SHORTHAND_TO_LONGHANDS = {
  padding: ['padding-top', 'padding-right', 'padding-bottom', 'padding-left'],
  margin: ['margin-top', 'margin-right', 'margin-bottom', 'margin-left'],
  'border-width': ['border-top-width', 'border-right-width', 'border-bottom-width', 'border-left-width'],
  'border-style': ['border-top-style', 'border-right-style', 'border-bottom-style', 'border-left-style'],
  'border-color': ['border-top-color', 'border-right-color', 'border-bottom-color', 'border-left-color'],
  border: [
    'border-top-width', 'border-right-width', 'border-bottom-width', 'border-left-width',
    'border-top-style', 'border-right-style', 'border-bottom-style', 'border-left-style',
    'border-top-color', 'border-right-color', 'border-bottom-color', 'border-left-color',
  ],
  'border-radius': [
    'border-top-left-radius', 'border-top-right-radius',
    'border-bottom-right-radius', 'border-bottom-left-radius',
  ],
  gap: ['row-gap', 'column-gap'],
  flex: ['flex-grow', 'flex-shrink', 'flex-basis'],
}

// Side order for box quadruplets (top,right,bottom,left) used by value parsing.
const SIDE_ORDER = { padding: 1, margin: 1, 'border-width': 1, 'border-style': 1, 'border-color': 1, border: 1 }

// Parse 1-4 box shorthand tokens into per-longhand values (top,right,bottom,left).
// Geometry from CSS box value parsing: 1 -> all; 2 -> [t,r,b,r]; 3 -> [t,r,b,r];
// actually [t,r,b,l]? Standard: 2 = TBLR where TB=v1, RL=v2 (so top=v1,bottom=v1,
// right=v2,left=v2). 3 = t r b r (top=v1, right=v2, bottom=v3, left=v2). 4 = t r b l.
function sideValues(value, longhandOrder) {
  const toks = String(value == null ? '' : value).trim().split(/\s+/)
  const map = { top: toks[0], right: toks[1], bottom: toks[2], left: toks[3] }
  if (toks.length === 1) { map.right = map.left = map.bottom = map.top = toks[0] }
  else if (toks.length === 2) { map.bottom = toks[0]; map.left = toks[1] }
  else if (toks.length === 3) { map.left = toks[1] }
  // 4 -> identity
  const sideOf = {
    'padding-top': 'top', 'padding-right': 'right', 'padding-bottom': 'bottom', 'padding-left': 'left',
    'margin-top': 'top', 'margin-right': 'right', 'margin-bottom': 'bottom', 'margin-left': 'left',
    'border-top-width': 'top', 'border-right-width': 'right', 'border-bottom-width': 'bottom', 'border-left-width': 'left',
    'border-top-style': 'top', 'border-right-style': 'right', 'border-bottom-style': 'bottom', 'border-left-style': 'left',
    'border-top-color': 'top', 'border-right-color': 'right', 'border-bottom-color': 'bottom', 'border-left-color': 'left',
  }
  return (lh) => (sideOf[lh] ? map[sideOf[lh]] : value)
}

// Expand one authored cssProperty into one or more longhand decl descriptors
// (name, value, shorthand marker). Unsupported shorthands fall through as a
// single decl under the authored name. `value` is parsed for box quadruplets
// so each longhand carries its own resolved value; other shorthands (gap,
// flex, border-radius corners) keep the authored value as-is.
function expandDecl(cp) {
  const lhs = SHORTHAND_TO_LONGHANDS[cp.name]
  if (!lhs) return [{ name: cp.name, value: cp.value, shorthand: null }]
  if (SIDE_ORDER[cp.name]) {
    const sv = sideValues(cp.value, lhs)
    return lhs.map((lh) => ({ name: lh, value: sv(lh), shorthand: cp.name }))
  }
  // gap / flex / border-radius: keep the authored value on each longhand
  return lhs.map((lh) => ({ name: lh, value: cp.value, shorthand: cp.name }))
}

// Filter a rule's cssProperties against two real-CDP quirks that, unchecked,
// pollute the matched-styles map:
//  (1) Chrome emits BOTH the authored shorthand (`padding: 16px 24px`) AND
//      its already-expanded longhands (`padding-top: 16px`, ...) in the same
//      rule. Expanding the shorthand ourselves (expandDecl) AND keeping the
//      native longhands would double-count — so DROP native longhands a
//      present shorthand in THIS rule covers (the shorthand's expansion is
//      the sole source for that longhand from this rule).
//  (2) Chrome appends a range-less computed-form echo next to the authored
//      declaration (e.g. `color: rgb(255,255,255)` beside `color:
//      #ffffff@line6`). When a name has multiple entries, keep the RANGED
//      authored one and drop the range-less echo (the source line must be the
//      real authored line, not a phantom).
// UA-sheet rules lack ranges entirely; rule 2 never drops all entries for a
// name (we keep the first when none has a range).
function filterRuleProps(cssProperties) {
  const props = (cssProperties || []).filter((cp) => cp && cp.name)
  if (!props.length) return []
  const byName = new Map()
  for (const cp of props) { const a = byName.get(cp.name) || []; a.push(cp); byName.set(cp.name, a) }
  // shorthands present in this rule cover these longhands (rule 1 dedup).
  const longhandCoveredBy = new Map()
  for (const cp of props) {
    if (SHORTHAND_TO_LONGHANDS[cp.name]) {
      for (const lh of SHORTHAND_TO_LONGHANDS[cp.name]) longhandCoveredBy.set(lh, cp.name)
    }
  }
  const keep = []
  for (const cp of props) {
    // rule 1: drop a native longhand a present shorthand already covers
    if (!SHORTHAND_TO_LONGHANDS[cp.name] && longhandCoveredBy.has(cp.name)) continue
    // rule 2: when a name repeats (authored + computed echo), keep the ranged authored entry
    const sameName = byName.get(cp.name)
    if (sameName.length > 1) {
      const rep = sameName.find((c) => c.range) || sameName[0]
      if (cp !== rep) continue
    }
    keep.push(cp)
  }
  return keep
}

function buildMatchedStyles({ matched, inlineStyle, sheets, pageUrl, curated }) {
  const declsByProp = new Map() // property -> [decl]
  const add = (name, decl) => { declsByProp.set(name, push(declsByProp.get(name), decl)) }

  const ruleMatched = (matched && matched.matchedCSSRules) || []
  ruleMatched.forEach((rm) => {
    const rule = rm && rm.rule
    if (!rule || !rule.style) return
    const selectors = (rule.selectorList && rule.selectorList.selectors) || []
    const header = rule.styleSheetId ? sheets[rule.styleSheetId] : null
    const sourceUrl = resolveSourceUrl(header, pageUrl)
    const baseLine = header ? header.startLine || 0 : 0
    const baseCol = header ? header.startColumn || 0 : 0

    // specificity = max among matching sub-selectors
    let spec = { a: 0, b: 0, c: 0 }
    if (Array.isArray(rm.matchingSelectors) && rm.matchingSelectors.length && selectors.length) {
      for (const i of rm.matchingSelectors) {
        const s = selectors[i]
        if (s && s.specificity) spec = maxSpec(spec, normSpec(s.specificity))
      }
    } else if (selectors.length) {
      const s = selectors[0]
      if (s && s.specificity) spec = normSpec(s.specificity)
    }

    for (const cp of filterRuleProps(rule.style.cssProperties || [])) {
      if (!cp.name) continue
      const { line, column } = absRange(cp.range, rule.style.range, baseLine, baseCol, header)
      for (const ex of expandDecl(cp)) {
        if (curated && !curated.has(ex.name)) continue
        add(ex.name, {
          selector: rule.selectorList ? rule.selectorList.text : '',
          source_url: sourceUrl,
          line, column,
          value: ex.value,
          important: !!cp.important,
          origin: mapOrigin(rule.origin),
          specificity: spec,
          isInline: false,
          shorthand: ex.shorthand || null,
        })
      }
    }
  })

  // inline style attribute (style="..."). Chrome echoes both the authored
  // shorthand AND its expanded longhands for inline too, so dedupe via the
  // same filter as authored rules.
  if (inlineStyle && inlineStyle.cssProperties) {
    for (const cp of filterRuleProps(inlineStyle.cssProperties)) {
      if (!cp.name) continue
      for (const ex of expandDecl(cp)) {
        if (curated && !curated.has(ex.name)) continue
        add(ex.name, {
          selector: '@inline style attribute',
          source_url: pageUrl,
          line: null, column: null,
          value: ex.value,
          important: !!cp.important,
          origin: 'author',
          specificity: { a: 1e9, b: 0, c: 0 },
          isInline: true,
          shorthand: ex.shorthand || null,
        })
      }
    }
  }

  const out = {}
  const propNames = curated ? [...curated] : [...declsByProp.keys()]
  for (const prop of propNames) {
    const decls = declsByProp.get(prop) || []
    if (!decls.length) {
      // no authored rule on this node for this property — record populated-but-empty
      // so the consumer sees the property was inspected, not omitted.
      out[prop] = { winner: null, overridden: [], inherited_or_initial: true }
      continue
    }
    const ranked = decls
      .map((d) => ({ d, key: precedence(d) }))
      .sort((a, b) => compareArr(a.key, b.key))
    const winner = ranked[ranked.length - 1].d
    const overridden = ranked.slice(0, -1).map((r) => r.d)
    out[prop] = {
      winner: trimDecl(winner),
      overridden: overridden.map(trimDecl),
    }
  }
  return out
}

function resolveSourceUrl(header, pageUrl) {
  if (!header) return pageUrl
  if (header.sourceURL) return header.sourceURL
  return pageUrl // inline <style> blocks (isInline) report the document URL
}

function absRange(propRange, styleRange, baseLine, baseCol, header) {
  const range = propRange || styleRange
  if (!range) return { line: null, column: null }
  // For inline <style> blocks, header.startLine/mark the block offset within the
  // HTML document; for linked sheets baseLine/baseCol are 0.
  const line = (baseLine + (range.startLine || 0))
  const col = (range.startLine === 0 ? baseCol : 0) + (range.startColumn || 0)
  return { line, column: col }
}

function mapOrigin(o) {
  if (!o) return 'author'
  if (o === 'user-agent' || o === 'ua') return 'ua'
  if (o === 'user') return 'user'
  return 'author' // regular / inspector / implicit
}

function maxSpec(a, b) {
  return [a, b].sort((x, y) => y.a - x.a || y.b - x.b || y.c - x.c)[0]
}

function push(arr, item) { return (arr || []).concat(item) }

function trimDecl(d) {
  const out = {
    selector: d.selector,
    source_url: d.source_url,
    line: d.line, column: d.column,
    value: d.value,
    important: d.important,
    origin: d.origin,
  }
  if (d.shorthand) out.shorthand = d.shorthand
  if (d.isInline) out.inline = true
  return out
}

function normSpec(s) { return { a: (s && s.a) || 0, b: (s && s.b) || 0, c: (s && s.c) || 0 } }

function compareArr(a, b) {
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1
  }
  return 0
}

// Stable-layout condition: read the body scroll height + the first target's
// rect across two frames; settle only when consecutive reads are equal. This
// is a POLL ON A CONDITION, not a fixed timeout — it converges when the
// layout stops moving (fonts swapped in, reflow settled) and never sleeps
// a blind interval.
async function waitForStableLayout(page) {
  await page.waitForFunction(
    () => {
      const sel = (window.__cap_lastRects__ ? '' : '')
      const r = document.documentElement.getBoundingClientRect()
      const snap = [document.body ? document.body.scrollHeight : 0, r.width, r.height]
      if (window.__cap_prevSnap__ && String(window.__cap_prevSnap__) === String(snap)) {
        window.__cap_prevSnap__ = null
        return true
      }
      window.__cap_prevSnap__ = snap
      return false
    },
    undefined,
    { polling: 'raf', timeout: 8000 }
  )
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------
async function main() {
  const argv = process.argv.slice(2)
  const o = parseArgs(argv)
  if (o.help || !o.target || !o.selectors.length || !o.viewports.length || !o.out) {
    process.stderr.write(helpText())
    process.exit(o.help ? 0 : 1)
  }
  const { default: pw } = await import('playwright')
  // Reuse a host chromium (e.g. a cached build) when playwright's pinned
  // build is not installed — set via env CAPTURE_CHROMIUM_EXECUTABLE.
  const chromiumLaunchOptions = process.env.CAPTURE_CHROMIUM_EXECUTABLE
    ? { executablePath: process.env.CAPTURE_CHROMIUM_EXECUTABLE, headless: true }
    : { headless: true }
  const res = await runCapture({
    mode: o.mode, target: o.target, route: o.route,
    selectors: o.selectors.split(','), viewports: o.viewports.split(','),
    out: o.out, profile: o.profile, name: o.name,
    authFixturePath: o.authFixture, chromium: pw.chromium,
    chromiumLaunchOptions,
    // default deterministic clock (runCapture now default = 0) so two CLI
    // invocations with the same input produce a BYTE-EQUAL artifact — a wall
    // clock here would break determinism. capture_clock is metadata only.
  })
  process.stdout.write(`captured -> ${res.artifactPath}\n${res.inventory}\n`)
}

function parseArgs(argv) {
  const o = { mode: 'app', route: '', profile: 'curated', name: 'capture', selectors: [], viewports: [] }
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    switch (a) {
      case '--mode': o.mode = argv[++i]; break
      case '--target': o.target = argv[++i]; break
      case '--route': o.route = argv[++i]; break
      case '--selectors': o.selectors = argv[++i]; break
      case '--viewports': o.viewports = argv[++i]; break
      case '--out': o.out = argv[++i]; break
      case '--profile': o.profile = argv[++i]; break
      case '--name': o.name = argv[++i]; break
      case '--auth-fixture': o.authFixture = argv[++i]; break
      case '-h': case '--help': o.help = true; break
      default: if (a.startsWith('--')) { o.help = false } break
    }
  }
  return o
}

function helpText() {
  return [
    'usage: capture.mjs --mode app|component --target <url|path> --selectors a,b',
    '                  --viewports WxH,WxH --out <dir> [options]',
    '',
    'options:',
    '  --route /path          app mode: route appended to --target',
    '  --profile curated|full curated (default) or all ~300 longhands',
    '  --name <slug>          run name (stable filenames)',
    '  --auth-fixture <p.mjs> app mode: default-exports setup(context)',
    '                         (the e2e auth-fixture pattern)',
    '',
    'selector specs (preference order; bare css is flagged fragile):',
    '  role:button[Submit]    by role + accessible name',
    '  label:Email            by accessible name (label)',
    '  testid:submit-btn      by data-testid',
    '  text:Submit            by visible text',
    '  css:.v-card            bare CSS (last resort)',
  ].join('\n') + '\n'
}

// run as a script only when invoked directly (not when imported by the stub).
// ESM-safe path resolution via node:url (no `require`). Compare on the REAL
// path of both sides so a symlinked install (the global skills dir) does NOT
// silently no-op: import.meta.url resolves to the real file URL, so realpath
// argv[1] (following the symlink) must match it when invoked directly. A bare
// `import.meta.url === pathToFileURL(process.argv[1])` MISSES when argv[1] is
// the symlink path, main() never ran, and the harness exited 0 writing no
// artifact — a silent no-op footgun uncovered while fixing audit.mjs.
import { pathToFileURL as _pathToFileURL } from 'node:url'
import { realpathSync as _realpath } from 'node:fs'
const invokedDirect = (() => {
  try {
    if (!process.argv[1]) return false
    const argvReal = _pathToFileURL(_realpath(process.argv[1])).href
    return import.meta.url === argvReal || import.meta.url === _pathToFileURL(process.argv[1]).href
  } catch { return false }
})()

if (invokedDirect) main().catch((e) => { process.stderr.write('capture: ' + (e && e.stack || e) + '\n'); process.exit(1) })