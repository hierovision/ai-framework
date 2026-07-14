#!/usr/bin/env node
// Grader for the deploying-to-azure-swa skill (azure-swa scenario).
//
// Run AFTER the agent stops, from a WRITABLE COPY of the fixture (never from
// evals/fixtures/). Expects a corrected .github/workflows/deploy.yml at the
// repo root. Failable: the seeded broken workflow deploys on push-to-main
// only (no preview-per-PR), puts the SWA token in `vars`, and omits
// `skip_app_build` — fails every check; a workflow with a pull_request
// trigger (preview), push-to-main promotion, skip_app_build: true, and the
// token from secrets PASSES.
//
// Planted defects in the seed file:
//   1. No `pull_request` trigger — no preview environment per PR.
//   2. `azure_static_web_apps_api_token` sourced from `vars.SWA_TOKEN` (leak).
//   3. No `skip_app_build: true` (Vite app would be misbuilt by Oryx).
const fs = require('fs')
const path = require('path')

const root = process.cwd()
const wfPath = path.join(root, '.github', 'workflows', 'deploy.yml')
const errors = []

if (!fs.existsSync(wfPath)) {
  console.error('verify-swa: FAILED — .github/workflows/deploy.yml missing (the deploy must emit a workflow)')
  process.exit(1)
}
const text = fs.readFileSync(wfPath, 'utf8')

// 1. Preview-per-PR: a pull_request trigger must exist.
if (!/\bpull_request\b/.test(text)) {
  errors.push('no `pull_request` trigger — SWA cannot create a preview environment per PR')
}

// 2. Production promotion on push to main (must have a push trigger too).
if (!/\bpush\b/.test(text)) {
  errors.push('no `push` trigger — production promotion on merge to main is missing')
}

// 3. Uses the Azure SWA action.
if (!/Azure\/static-web-apps-deploy/.test(text)) {
  errors.push('does not use the Azure/static-web-apps-deploy action')
}

// 4. skip_app_build: true (Vite/own-build app must not be Oryx-built).
if (!/skip_app_build:\s*true/.test(text)) {
  errors.push('`skip_app_build: true` missing — a Vite app would be misbuilt by Oryx')
}

// 5. Token from secrets, not vars.
const tokenLine = text.match(/azure_static_web_apps_api_token:\s*(.+)/)
if (!tokenLine) {
  errors.push('`azure_static_web_apps_api_token` not set')
} else if (/vars\.|secrets\.GITHUB_TOKEN/.test(tokenLine[1]) && !/secrets\./.test(tokenLine[1])) {
  errors.push('SWA deployment token sourced from `vars` (leak) — must come from `secrets`')
} else if (!/secrets\./.test(tokenLine[1])) {
  errors.push('SWA deployment token must come from `secrets`')
}

if (errors.length) {
  console.error('verify-swa: FAILED (azure-swa)')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log('verify-swa: ok — preview-per-PR + push-promotion + skip_app_build + token-from-secrets')
process.exit(0)
