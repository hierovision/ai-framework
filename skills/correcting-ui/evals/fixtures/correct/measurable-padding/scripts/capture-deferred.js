#!/usr/bin/env node
// capture-deferred.js — real-browser re-capture is DEFERRED in this harness
// (no Playwright/chromium runtime). The objective closure is the bundled
// verify-correct.js (source adherence + canned re-capture compare). Documented
// here honestly, not silently skipped (writing-e2e-tests real-browser-deferral
// precedent). Where a chromium IS reachable, the loop realizes the deferred
// run via CAPTURE_CHROMIUM_EXECUTABLE through capturing-ui-evidence's harness.
console.log('capture: DEFERRED — no browser in this harness. Objective closure: npm run test.');
console.log('To realize: set CAPTURE_CHROMIUM_EXECUTABLE and invoke capturing-ui-evidence scripts/capture.mjs.');
process.exit(0);