#!/usr/bin/env node
// Real-browser e2e is DEFERRED in this harness (no browser available).
// The structural verifier (`npm run test` -> scripts/verify-spec.js) is
// the objective check here; real-browser red-on-broken is the deferred
// validation (documented in evals.json notes). In the real project this
// script is `playwright test`.
console.error('e2e: DEFERRED — real-browser execution is not available in this harness.')
console.error('     Run `npm run test` for the structural spec verifier.')
console.error('     Real-browser validation (red-on-broken across the journey) is a deferred eval — see evals.json notes.')
process.exit(0)
