// Thin fake of the Playwright + CDP surface, with canned CDP/DOM data that
// reflects harness/index.html for the determinism/curation slice. The
// objective self-check (verify-capture.js) injects this fake chromium into
// runCapture and additionally RUNS THE CAPTURE TWICE, asserting the two
// artifacts are byte-identical (determinism) AND that a bare-CSS target is
// flagged fragile. Real screenshot + real computed CSS capture is a DEFERRED
// validation — documented in evals.json notes, never silently skipped.
//
// This slice's harness has a single authored rule (.legacy-action) and no
// overrides / no inline style — a STABLE target — to foreground the
// determinism + curation + fragility checks rather than the override chain.

import { writeFileSync } from 'node:fs'

const PNG_1PX = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/ZIgAAAAAElFTkSuQmCC',
  'base64'
)

const SHEETS = [
  { styleSheetId: 'S1', sourceURL: 'styles.css', origin: 'regular', isInline: false, startLine: 0, startColumn: 0 },
  { styleSheetId: 'UA', sourceURL: '', origin: 'user-agent', isInline: false, startLine: 0, startColumn: 0 },
]

// Only one authored rule (no override, no inline) — the determinism/curation
// harness foregrounds stability + bare-css fragility, not the cascade chain.
const MATCHED_RULES_N1 = [
  {
    matchingSelectors: [0],
    rule: {
      origin: 'regular', styleSheetId: 'S1',
      selectorList: { text: '.legacy-action', selectors: [{ text: '.legacy-action', specificity: { a: 0, b: 1, c: 0 } }] },
      style: {
        range: { startLine: 0, startColumn: 16, endLine: 5, endColumn: 1 },
        cssProperties: [
          { name: 'padding', value: '16px 24px', important: false, range: { startLine: 1, startColumn: 2, endLine: 1, endColumn: 22 } },
          // Real-CDP quirk #1: Chrome also emits the expanded longhands; deduped.
          { name: 'padding-top', value: '16px', important: false, range: { startLine: 1, startColumn: 2, endLine: 1, endColumn: 16 } },
          { name: 'padding-right', value: '24px', important: false, range: { startLine: 1, startColumn: 2, endLine: 1, endColumn: 16 } },
          { name: 'padding-bottom', value: '16px', important: false, range: { startLine: 1, startColumn: 2, endLine: 1, endColumn: 16 } },
          { name: 'padding-left', value: '24px', important: false, range: { startLine: 1, startColumn: 2, endLine: 1, endColumn: 16 } },
          { name: 'color', value: '#ffffff', important: false, range: { startLine: 2, startColumn: 2, endLine: 2, endColumn: 18 } },
          // Real-CDP quirk #2: range-less computed-form echo; deduped (ranged kept).
          { name: 'color', value: 'rgb(255, 255, 255)', important: false, range: null },
          { name: 'background-color', value: '#1976d2', important: false, range: { startLine: 3, startColumn: 2, endLine: 3, endColumn: 28 } },
          { name: 'border-radius', value: '4px', important: false, range: { startLine: 4, startColumn: 2, endLine: 4, endColumn: 19 } },
          { name: 'font-size', value: '14px', important: false, range: { startLine: 5, startColumn: 2, endLine: 5, endColumn: 17 } },
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

function computedLonghands() {
  const base = {
    width: '120px', height: '40px', 'box-sizing': 'border-box',
    'min-width': '0px', 'min-height': '0px', 'max-width': 'none', 'max-height': 'none',
    'margin-top': '0px', 'margin-right': '0px', 'margin-bottom': '0px', 'margin-left': '0px',
    'padding-top': '16px', 'padding-right': '24px', 'padding-bottom': '16px', 'padding-left': '24px',
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
  const extras = {
    'cursor': 'pointer', 'outline-style': 'none', 'outline-width': '2px', 'box-shadow': 'none',
    'overflow-x': 'visible', 'overflow-y': 'visible', 'resize': 'none', 'unicode-bidi': 'plaintext',
    'tab-size': '8', 'user-select': 'none', 'word-spacing': 'normal', 'orphans': '2', 'widows': '2',
    'clip-path': 'none', 'mask-image': 'none', 'mix-blend-mode': 'normal', 'isolation': 'auto',
  }
  return { ...base, ...extras }
}

function bboxFor(viewport) {
  if (viewport.width <= 480) return { x: 16, y: 80, width: 120, height: 40 }
  return { x: 80, y: 120, width: 140, height: 44 }
}

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
  function locator() { return { async elementHandle() { return echoHandle('N1') } } }

  const page = {
    async emulateMedia() {},
    async setViewportSize(v) { state.currentViewport = v },
    async goto(url) { state.pageUrl = url; return { ok: () => true } },
    url() { return state.pageUrl },
    async evaluate() { return null },
    async waitForFunction() { return true },
    async screenshot({ path }) { writeFileSync(path, PNG_1PX); return path },
    getByRole() { return locator() }, getByLabelText() { return locator() },
    getByTestId() { return locator() }, getByText() { return locator() },
    locator() { return locator() },
  }
  const client = {
    on(event, cb) { (state.listeners[event] = state.listeners[event] || []).push(cb) },
    async send(method, params) {
      switch (method) {
        case 'DOM.enable': return {}
        case 'CSS.enable': for (const h of SHEETS) for (const cb of (state.listeners['CSS.styleSheetAdded'] || [])) cb(h); return {}
        case 'DOM.getDocument': return { root: { nodeId: 1 } }
        case 'DOM.querySelectorAll': return { nodeIds: [1] }
        case 'DOM.removeAttribute': return {}
        case 'DOM.requestNode': return { node: { nodeId: params.objectId === 'N1' ? 1 : 0 } }
        case 'CSS.getComputedStyleForNode': return { computedStyle: { cssProperties: Object.entries(computedLonghands()).map(([name, value]) => ({ name, value })) } }
        case 'CSS.getMatchedStylesForNode': return { matchedCSSRules: MATCHED_RULES_N1, pseudoElements: [], inherited: [], cssKeyframesRules: [] }
        case 'CSS.getInlineStylesForNode': return { inlineStyle: INLINE_STYLE_N1, attributesStyle: null }
        default: return {}
      }
    },
  }
  const context = {
    async addInitScript() {},
    newPage() { return page },
    newCDPSession() { return client },
  }
  const browser = {
    async newContext(opts) { state.currentViewport = opts && opts.viewport ? opts.viewport : state.currentViewport; return context },
    async close() {},
  }
  return { chromium: { async launch() { return browser } }, state }
}