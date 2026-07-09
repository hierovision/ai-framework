#!/usr/bin/env node
// Real-browser capture is DEFERRED in this harness (no Playwright/chromium
// runtime available). The objective check is `npm run test`
// (scripts/verify-capture.js) which drives the emitted artifact through a
// canned CDP/DOM fake and the bundled schema validator. Real screenshot +
// real computed CSS + real matched-styles against the live harness/index.html
// is a DEFERRED validation — documented in evals.json notes, not silently
// skipped. In the real project the skill invokes playwright directly:
//   node <skill>/scripts/capture.mjs --mode component --target ./harness/index.html ...
console.error('capture: DEFERRED — no real browser in this harness.')
console.error('     Run `npm run test` for the objective capture self-check (fake CDP).')
console.error('     Real screenshot + computed CSS capture is a deferred eval — see evals.json notes.')
process.exit(0)