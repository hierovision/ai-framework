#!/usr/bin/env node
// Grader for the securing-ci skill (ci-hardening scenario).
//
// Run AFTER the agent stops, from a WRITABLE COPY of the fixture (never from
// evals/fixtures/). Expects a corrected .github/workflows/ci.yml at the repo
// root. Failable: the seeded broken workflow has `permissions: write-all`,
// echoes a secret, and pins third-party actions to floating refs (@main /
// @master) — fails every check; a hardened workflow (minimal permissions, no
// secret echo, SHA/major-pinned actions) PASSES.
//
// Planted defects in the seed file:
//   1. `permissions: write-all` — blanket grant.
//   2. `echo "deploy token is ${{ secrets.DEPLOY_TOKEN }}"` — cleartext leak.
//   3. `actions/checkout@main` and `azure/login@master` — floating refs.
const fs = require('fs')
const path = require('path')

const root = process.cwd()
const wfPath = path.join(root, '.github', 'workflows', 'ci.yml')
const errors = []

if (!fs.existsSync(wfPath)) {
  console.error('verify-ci-security: FAILED — .github/workflows/ci.yml missing (the hardening must emit a workflow)')
  process.exit(1)
}
const text = fs.readFileSync(wfPath, 'utf8')

// 1. No blanket permissions grant.
if (/permissions:\s*write-all/.test(text)) {
  errors.push('`permissions: write-all` is a blanket grant a compromised step can abuse — set a minimal explicit block')
}

// 2. No echo of a secret value.
if (/\becho\b[\s\S]*?secrets\./i.test(text) || /secrets\.[\s\S]*?\becho\b/i.test(text)) {
  errors.push('workflow echoes a `secrets.*` value — cleartext leak; GitHub redacts only when used as a value, not when echoed')
}

// 3. No third-party action pinned to a floating ref (@main/@master/@latest).
const floating = []
const usesRe = /uses:\s*([^\s@]+)@(main|master|latest|head)\b/g
let m
while ((m = usesRe.exec(text)) !== null) floating.push(m[1] + '@' + m[2])
if (floating.length) {
  errors.push('third-party action(s) pinned to a floating ref (supply-chain risk): ' + floating.join(', ') + ' — pin to a commit SHA or at least a major tag')
}

if (errors.length) {
  console.error('verify-ci-security: FAILED (ci-hardening)')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log('verify-ci-security: ok — minimal permissions + no secret echo + pinned actions')
process.exit(0)
