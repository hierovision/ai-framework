// Thin fake of the Playwright + CDP surface, with canned CDP/DOM data that
// reflects harness/index.html (the deferred real-run target). The objective
// self-check (verify-capture.js) injects this fake chromium into runCapture
// so the schema-emission / curation / matched-styles logic can be unit-checked
// WITHOUT a real browser install. Real screenshot + real computed-CSS capture
// is a DEFERRED validation — documented in evals.json notes, not silently
// skipped.
//
// This fake implements exactly the surface capture.mjs uses:
//   chromium.launch -> browser -> context(newContext opts) -> page(client)
//   context.addInitScript(fn,arg), context.newCDPSession(page)
//   page.emulateMedia / setViewportSize / goto / url / evaluate / waitForFunction
//        / screenshot / getByRole / getByLabelText / getByTestId / getByText / locator
//   locator.elementHandle() -> handle(._objectId, boundingBox, screenshot)
//   client.on('CSS.styleSheetAdded',cb) + client.send(method,params)

import { writeFileSync } from 'node:fs'

// Minimal valid 1px PNG so screenshot files exist (placeholder only — real
// pixels are a deferred real-browser validation).
const PNG_1PX = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/ZIgAAAAAElFTkSuQmCC',
  'base64'
)

// --- Canned stylesheet headers (emitted on CSS.enable) ----------------------
const SHEETS = [
  { styleSheetId: 'S1', sourceURL: 'styles.css', origin: 'regular', isInline: false, startLine: 0, startColumn: 0 },
  { styleSheetId: 'S2', sourceURL: '', origin: 'regular', isInline: true, startLine: 8, startColumn: 4 },
  { styleSheetId: 'UA', sourceURL: '', origin: 'user-agent', isInline: false, startLine: 0, startColumn: 0 },
]

// --- Canned matched rules for the single target node N1 (the isolated button)
// padding: .btn in the density <style> block (S2, source-order later) wins over
// .btn in the linked styles.css (S1, same specificity, earlier source) over UA.
// color/background/border-radius/font-size: .btn (S1). No inline style attribute.
// border-*-style / border-*-width / position / box-sizing: UA defaults.
const MATCHED_RULES_N1 = [
  {
    matchingSelectors: [0],
    rule: {
      origin: 'regular', styleSheetId: 'S1',
      selectorList: { text: '.btn', selectors: [{ text: '.btn', specificity: { a: 0, b: 1, c: 0 } }] },
      style: {
        range: { startLine: 3, startColumn: 7, endLine: 7, endColumn: 1 },
        cssProperties: [
          { name: 'padding', value: '16px 24px', important: false, range: { startLine: 3, startColumn: 2, endLine: 3, endColumn: 22 } },
          // Real-CDP quirk #1: Chrome also emits the expanded longhands; deduped.
          { name: 'padding-top', value: '16px', important: false, range: { startLine: 3, startColumn: 2, endLine: 3, endColumn: 16 } },
          { name: 'padding-right', value: '24px', important: false, range: { startLine: 3, startColumn: 2, endLine: 3, endColumn: 16 } },
          { name: 'padding-bottom', value: '16px', important: false, range: { startLine: 3, startColumn: 2, endLine: 3, endColumn: 16 } },
          { name: 'padding-left', value: '24px', important: false, range: { startLine: 3, startColumn: 2, endLine: 3, endColumn: 16 } },
          { name: 'color', value: '#ffffff', important: false, range: { startLine: 4, startColumn: 2, endLine: 4, endColumn: 18 } },
          // Real-CDP quirk #2: range-less computed-form echo; deduped (ranged kept).
          { name: 'color', value: 'rgb(255, 255, 255)', important: false, range: null },
          { name: 'background-color', value: '#1976d2', important: false, range: { startLine: 5, startColumn: 2, endLine: 5, endColumn: 28 } },
          { name: 'border-radius', value: '4px', important: false, range: { startLine: 6, startColumn: 2, endLine: 6, endColumn: 19 } },
          { name: 'font-size', value: '14px', important: false, range: { startLine: 6, startColumn: 2, endLine: 6, endColumn: 17 } },
        ],
      },
    },
  },
  {
    matchingSelectors: [0],
    rule: {
      origin: 'regular', styleSheetId: 'S2',
      selectorList: { text: '.btn', selectors: [{ text: '.btn', specificity: { a: 0, b: 1, c: 0 } }] },
      style: {
        range: { startLine: 0, startColumn: 4, endLine: 0, endColumn: 32 },
        cssProperties: [
          { name: 'padding', value: '8px 16px', important: false, range: { startLine: 0, startColumn: 12, endLine: 0, endColumn: 24 } },
        ],
      },
    },
  },
  {
    matchingSelectors: [0],
    rule: {
      origin: 'user-agent', styleSheetId: 'UA',
      selectorList: { text: 'button', selectors: [{ text: 'button', specificity: { a: 0, b: 0, c: 1 } }] },
      style: {
        range: null,
        cssProperties: [
          { name: 'padding', value: '2px 6px', important: false, range: null },
          { name: 'margin-top', value: '0px', important: false, range: null },
          { name: 'margin-right', value: '0px', important: false, range: null },
          { name: 'margin-bottom', value: '0px', important: false, range: null },
          { name: 'margin-left', value: '0px', important: false, range: null },
          { name: 'border-top-style', value: 'outset', important: false, range: null },
          { name: 'border-right-style', value: 'outset', important: false, range: null },
          { name: 'border-bottom-style', value: 'outset', important: false, range: null },
          { name: 'border-left-style', value: 'outset', important: false, range: null },
          { name: 'border-top-width', value: '2px', important: false, range: null },
          { name: 'border-right-width', value: '2px', important: false, range: null },
          { name: 'border-bottom-width', value: '2px', important: false, range: null },
          { name: 'border-left-width', value: '2px', important: false, range: null },
          { name: 'position', value: 'relative', important: false, range: null },
          { name: 'box-sizing', value: 'border-box', important: false, range: null },
          { name: 'color', value: 'buttontext', important: false, range: null },
          { name: 'font-size', value: '13px', important: false, range: null },
        ],
      },
    },
  },
]

const INLINE_STYLE_N1 = { cssProperties: [] }

// Full computed longhands (~90). pickComputed filters to the curated set for
// the default profile; the objective check asserts the EMITTED computed is
// curated (<<300), not this full dump.
function computedLonghands() {
  const base = {
    width: '100px', height: '36px', 'box-sizing': 'border-box',
    'min-width': '0px', 'min-height': '0px', 'max-width': 'none', 'max-height': 'none',
    'margin-top': '0px', 'margin-right': '0px', 'margin-bottom': '0px', 'margin-left': '0px',
    'padding-top': '8px', 'padding-right': '16px', 'padding-bottom': '8px', 'padding-left': '16px',
    'border-top-width': '2px', 'border-right-width': '2px', 'border-bottom-width': '2px', 'border-left-width': '2px',
    display: 'inline-block',
    'flex-direction': 'row', 'flex-wrap': 'nowrap', 'justify-content': 'normal', 'align-items': 'normal',
    'align-content': 'normal', 'align-self': 'auto', 'flex-grow': '0', 'flex-shrink': '1', 'flex-basis': 'auto',
    gap: 'normal', 'row-gap': 'normal', 'column-gap': 'normal',
    'grid-template-columns': 'none', 'grid-template-rows': 'none', 'grid-column': 'auto', 'grid-row': 'auto', 'grid-area': 'auto / auto / auto / auto', order: '0',
    position: 'relative', inset: 'auto', top: 'auto', right: 'auto', bottom: 'auto', left: 'auto', 'z-index': 'auto', float: 'none', clear: 'none',
    'font-family': 'Roboto, sans-serif', 'font-size': '14px', 'font-weight': '500', 'font-style': 'normal', 'line-height': '1.5',
    'letter-spacing': 'normal', 'text-align': 'center', 'text-decoration': 'none', 'text-transform': 'none',
    'text-overflow': 'clip', 'white-space': 'normal', 'word-break': 'normal', 'overflow-wrap': 'normal',
    color: '#ffffff', 'background-color': '#1976d2', 'background-image': 'none', 'background-size': 'auto', 'background-position': '0% 0%', opacity: '1',
    'border-style': 'outset', 'border-top-style': 'outset', 'border-right-style': 'outset', 'border-bottom-style': 'outset', 'border-left-style': 'outset',
    'border-color': 'currentColor', 'border-top-color': 'currentColor', 'border-right-color': 'currentColor', 'border-bottom-color': 'currentColor', 'border-left-color': 'currentColor',
    'border-radius': '4px', 'border-top-left-radius': '4px', 'border-top-right-radius': '4px', 'border-bottom-right-radius': '4px', 'border-bottom-left-radius': '4px',
  }
  // a handful of extra non-curated longhands so the full computed list (>curated)
  // is clearly larger than the curated emitted set:
  const extras = {
    'cursor': 'pointer', 'outline-style': 'none', 'outline-width': '2px', 'box-shadow': 'none',
    'overflow-x': 'visible', 'overflow-y': 'visible', 'resize': 'none', 'unicode-bidi': 'plaintext',
    'tab-size': '8', 'user-select': 'none', 'word-spacing': 'normal', 'orphans': '2', 'widows': '2',
    'clip-path': 'none', 'mask-image': 'none', 'mix-blend-mode': 'normal', 'isolation': 'auto',
  }
  return { ...base, ...extras }
}

// Per-viewport canned bounding boxes for N1 (mobile vs desktop differ —
// the artifact records geometry per (selector x viewport)).
function bboxFor(viewport) {
  if (viewport.width <= 480) return { x: 16, y: 120, width: 100, height: 36 }
  return { x: 80, y: 160, width: 120, height: 40 }
}

// ---------------------------------------------------------------------------
// Fake engine
// ---------------------------------------------------------------------------
export function createChromium() {
  const state = { listeners: {}, currentViewport: { width: 0, height: 0 }, pageUrl: 'http://localhost:5173/dashboard' }

  function echoHandle(objectId) {
    return {
      _objectId: objectId,
      async boundingBox() { return bboxFor(state.currentViewport) },
      async screenshot({ path }) { writeFileSync(path, PNG_1PX); return path },
      async evaluate() { return true },
    }
  }
  function locator(kind, key) {
    return {
      async elementHandle() {
        // All resolutions in this scenario converge on the single button node N1.
        return echoHandle('N1')
      },
    }
  }

  const page = {
    async emulateMedia() {},
    async setViewportSize(v) { state.currentViewport = v },
    async goto(url, opts) { state.pageUrl = url; return { ok: () => true } },
    url() { return state.pageUrl },
    async evaluate() { return null },
    async waitForFunction(fn, arg, opts) { return true },
    async screenshot({ path, fullPage }) { writeFileSync(path, PNG_1PX); return path },
    getByRole(role, opts) { return locator('role', role) },
    getByLabelText(name) { return locator('label', name) },
    getByTestId(id) { return locator('testid', id) },
    getByText(t) { return locator('text', t) },
    locator(css) { return locator('css', css) },
  }

  const client = {
    on(event, cb) {
      ;(state.listeners[event] = state.listeners[event] || []).push(cb)
    },
    async send(method, params) {
      switch (method) {
        case 'DOM.enable': return {}
        case 'CSS.enable':
          // Fire the stylesheet-added events for every canned header.
          for (const h of SHEETS) {
            for (const cb of (state.listeners['CSS.styleSheetAdded'] || [])) cb(h)
          }
          return {}
        case 'DOM.getDocument': return { root: { nodeId: 1 } }
        case 'DOM.querySelectorAll': return { nodeIds: [1] }
        case 'DOM.removeAttribute': return {}
        case 'DOM.requestNode':
          return { node: { nodeId: params.objectId === 'N1' ? 1 : 0 } }
        case 'CSS.getComputedStyleForNode':
          return { computedStyle: { cssProperties: Object.entries(computedLonghands()).map(([name, value]) => ({ name, value })) } }
        case 'CSS.getMatchedStylesForNode':
          return { matchedCSSRules: MATCHED_RULES_N1, pseudoElements: [], inherited: [], cssKeyframesRules: [] }
        case 'CSS.getInlineStylesForNode':
          return { inlineStyle: INLINE_STYLE_N1, attributesStyle: null }
        default: return {}
      }
    },
  }

  const context = {
    _opts: null,
    wait: null,
    async addInitScript(fn, arg) { /* recorded; fake applies nothing */ },
    newPage() { return page },
    newCDPSession() { return client },
  }

  const browser = {
    async newContext(opts) { context._opts = opts; state.currentViewport = opts && opts.viewport ? opts.viewport : state.currentViewport; return context },
    async close() {},
  }

  return { chromium: { async launch() { return browser } }, state }
}