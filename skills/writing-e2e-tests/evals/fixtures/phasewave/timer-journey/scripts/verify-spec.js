#!/usr/bin/env node
// Structural e2e spec verifier (real-browser execution is DEFERRED —
// see evals.json notes). Parses e2e/*.spec.ts and fails objectively on
// the e2e discipline violations that a real browser run would surface
// as flake or wrong-layer authoring. This is the failable objective
// check in the harness; real-browser red-on-broken is the deferred
// validation.
//
// Failable: exits non-zero when
//   - no e2e/*.spec.ts exists (no spec authored),
//   - the spec uses `waitForTimeout` (a sleep, not a condition wait),
//   - the spec uses bare CSS selectors instead of role/accessible-name/
//     testid selectors,
//   - a web-first assertion (`expect(locator).toBeVisible()` etc.) is
//     NOT awaited (a no-op flake),
//   - a page action (click/fill/press/goto/setOffline ...) is NOT awaited,
//   - the spec has <2 `// AC` mapping comments (no AC -> step mapping),
//   - the spec replays the login UI (fills a password field) instead of
//     using the auth fixture,
//   - the spec does not import/use the auth fixture (authedPage),
//   - the spec has !=1 `test(` journey (one journey per spec),
//   - the spec has <2 user-observable (web-first) assertions,
//   - trace is set to 'off' or absent in playwright.config.ts.
//
// Pass `--offline` to additionally require `context.setOffline` usage
// (for the PWA/offline journey).
const fs = require('fs')
const path = require('path')

const args = process.argv.slice(2)
const requireOffline = args.includes('--offline')
const repoRoot = path.join(__dirname, '..')
const e2eDir = path.join(repoRoot, 'e2e')

const WEB_FIRST = [
  'toBeVisible', 'toBeHidden', 'toBeEnabled', 'toBeDisabled', 'toBeChecked',
  'toBeEditable', 'toBeFocused', 'toBeEmpty', 'toBeAttached', 'toContainText',
  'toHaveText', 'toHaveAttribute', 'toHaveClass', 'toHaveCount', 'toHaveCSS',
  'toHaveId', 'toHaveJSProperty', 'toHaveRole', 'toHaveTitle', 'toHaveURL',
  'toHaveValue', 'toHaveValues',
]
const ACTIONS = [
  'click', 'fill', 'press', 'goto', 'reload', 'goBack', 'goForward', 'check',
  'selectOption', 'hover', 'focus', 'tap', 'setType', 'setInputFiles', 'setOffline',
]

function findSpecs(dir) {
  const out = []
  if (!fs.existsSync(dir)) return out
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name)
    if (e.isDirectory()) out.push(...findSpecs(p))
    else if (e.name.endsWith('.spec.ts')) out.push(p)
  }
  return out
}

const errors = []
const specs = findSpecs(e2eDir)

if (specs.length === 0) {
  errors.push('no e2e/*.spec.ts discovered — author the journey spec (e2e/timer.spec.ts)')
}

const roleSelectorRe = /getBy(Role|TestId|LabelText|Text|Placeholder|AltText|Title)\s*\(/
const cssSelectorRe = /\.(locator|waitForSelector)\s*\(\s*['"`][.#[]|page\.\$\$?\s*\(|querySelector\s*\(|\.(click|fill|press|type|check|selectOption|hover|focus|tap)\s*\(\s*['"`][.#[]/
const passwordReplayRe = /getBy(Label|Placeholder)\s*\(\s*['"`][^'"`]*password['"`]/i
const acCommentRe = /\/\/\s*AC\s*\d/gi
const testRe = /^\s*test(\.only|\.skip)?\s*\(/gm
const waitForTimeoutRe = /waitForTimeout\s*\(/
const traceOffRe = /trace\s*:\s*['"`]off['"`]/

for (const spec of specs) {
  const src = fs.readFileSync(spec, 'utf8')
  const rel = path.relative(repoRoot, spec)
  const lines = src.split('\n')

  // waitForTimeout
  if (waitForTimeoutRe.test(src)) {
    errors.push(rel + ': uses waitForTimeout — wait on conditions/selectors (expect(...).toBeVisible(), getByRole(...).click()), never sleep')
  }
  // bare CSS selectors
  if (cssSelectorRe.test(src)) {
    errors.push(rel + ': uses bare CSS selectors (locator(".cls") / page.$() / click(".cls")) — select by role/accessible-name/testid (getByRole/getByLabelText/getByTestId/getByText)')
  }
  // require at least one role/accessible/testid selector
  if (!roleSelectorRe.test(src)) {
    errors.push(rel + ': no role/accessible-name/testid selector (getByRole/getByLabelText/getByTestId/getByText) found — e2e selects by role, not CSS')
  }
  // password-field UI login replay
  if (passwordReplayRe.test(src)) {
    errors.push(rel + ': replays the login UI (fills a password field) — use the auth fixture (e2e/fixtures/auth.ts, authedPage) for session setup')
  }
  // auth fixture usage
  if (!/fixtures\/auth|authedPage/.test(src)) {
    errors.push(rel + ': does not use the auth fixture — import { test, expect } from the auth fixture and use authedPage for the authenticated session')
  }
  // AC mapping comments (>=2)
  const acCount = (src.match(acCommentRe) || []).length
  if (acCount < 2) {
    errors.push(rel + ': has ' + acCount + ' `// AC` mapping comment(s) — need >=2 mapping each acceptance criterion to a step')
  }
  // one journey per spec (exactly one test() definition)
  const testCount = (src.match(testRe) || []).length
  if (testCount !== 1) {
    errors.push(rel + ': has ' + testCount + ' test() definition(s) — one journey per spec (got ' + testCount + ', expected 1)')
  }
  // awaited web-first assertions + count
  let webFirstCount = 0
  for (const line of lines) {
    for (const m of WEB_FIRST) {
      if (line.includes('.' + m + '(')) {
        webFirstCount++
        if (!/\bawait\b/.test(line) && !/^\s*\/\//.test(line)) {
          errors.push(rel + ': un-awaited web-first assertion `' + m + '` — `await expect(locator).' + m + '(...)` actually waits; a bare expect(...).' + m + '() is a no-op flake')
        }
      }
    }
  }
  if (webFirstCount < 2) {
    errors.push(rel + ': has ' + webFirstCount + ' user-observable (web-first) assertion(s) — need >=2 assertions on visible/observable outcomes')
  }
  // awaited page actions
  for (const line of lines) {
    if (/^\s*\/\//.test(line)) continue
    if (/\bexpect\s*\(/.test(line)) continue // inside an expect is fine
    for (const a of ACTIONS) {
      const re = new RegExp('\\.' + a + '\\s*\\(')
      if (re.test(line) && !/\bawait\b/.test(line)) {
        errors.push(rel + ': un-awaited page action `.' + a + '()` — Playwright actions return promises; await them or the journey races ahead of the UI')
      }
    }
  }
  // trace not off
  if (traceOffRe.test(src)) {
    errors.push(rel + ': sets trace to "off" — trace on failure is the discriminating evidence for debugging-test-failures; do not disable')
  }
  // offline requirement
  if (requireOffline && !/setOffline\s*\(/.test(src)) {
    errors.push(rel + ': PWA/offline journey must use context.setOffline(...) to toggle the network — a real offline journey drives the browser offline, not a mock')
  }
}

// trace config present in playwright.config.ts
const configPath = path.join(repoRoot, 'playwright.config.ts')
if (fs.existsSync(configPath)) {
  const cfg = fs.readFileSync(configPath, 'utf8')
  if (!/trace\s*:/.test(cfg)) {
    errors.push('playwright.config.ts: no trace setting — set trace: "retain-on-failure" (or "on-first-retry") so failing e2e produces a trace')
  } else if (traceOffRe.test(cfg)) {
    errors.push('playwright.config.ts: trace is "off" — failing e2e produces no evidence; set trace: "retain-on-failure"')
  }
}

if (errors.length) {
  console.error('verify-spec: FAILED')
  for (const e of errors) console.error('  - ' + e)
  process.exit(1)
}
console.log('verify-spec: ok — no waitForTimeout, role selectors, awaited assertions/actions, AC mapping, auth fixture, one journey, trace on failure' + (requireOffline ? ', setOffline used' : ''))
process.exit(0)
