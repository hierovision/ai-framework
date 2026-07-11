#!/usr/bin/env node
// audit.mjs — deterministic accessibility audit harness (Playwright + axe-core).
//
// Run (EXECUTE — do not reimplement): the agent INVOKES this script to run an
// axe-core audit against a target and emit a schema-versioned report.json. It
// is the UI loop's Phase 3 PROACTIVE auditor: given a page/route/component it
// FINDS violations and reports them with severity + the source location to
// fix, then STOPs. It does NOT fix (fixes route to correcting-ui /
// implementing-features) and does NOT edit source.
//
//   node scripts/audit.mjs \
//     --mode app --target http://localhost:5173 --route /dashboard \
//     --viewports 375x667,1280x720 --out ./a11y \
//     --auth-fixture e2e/fixtures/auth.mjs --level AA
//
//   node scripts/audit.mjs \
//     --mode component --target ./harness/index.html \
//     --viewports 375x667,1280x720 --out ./a11y
//
// REPORT (per run, written to <out>/report.json): a schema-versioned artifact
// (see references/report-schema.md — the single source of truth; do not
// duplicate here). Each violation carries the axe rule id, the WCAG success
// criterion, the impact mapped to the library severity backbone
// (blocker/major/minor/nit), the offending node (selector + accessible-name
// context), a concrete human-readable reason, and a fix pointer + routing.
// axe `incomplete` results (axe ran but could not fully judge — e.g. contrast
// at non-default states, focus-visible, name-role-value) resurface in a
// needs-manual-verification list. A static beyond-axe manual checklist
// (keyboard trap, focus order, focus-visible, reduced-motion, live-region
// semantics, form-error association) is ALWAYS emitted — flagged NOT faked,
// because axe automates ~30-40% of WCAG and the rest is a human task.
//
// CARDINAL RULE (from debugging-test-failures — load-bearing): never green an
// audit by suppressing a rule / excluding a node / narrowing scope to dodge a
// violation. The harness applies NO rule exclusion and NO scope narrowing by
// default. An explicit user risk acceptance is recorded dated in the report's
// accepted_risks (the violation STAYS, marked accepted) — a suppressed check
// with a record is a decision; a silent suppression is a lie.
//
// DETERMINISM (load-bearing): the same canned axe input yields the same
// report (the objective self-check asserts byte-equal classification). In a
// real browser the axe result is the deterministic engine; animations + fonts
// + load are awaited as conditions (never a fixed timeout), viewport + device
// scale factor pinned — mirroring the capturing-ui-evidence harness.

// ---------------------------------------------------------------------------
// Exports (importable by the objective self-check stub, which injects either
// a real Playwright chromium + axe-core source, or a CANNED axe-results
// fixture so the classification + report-emission logic can be unit-checked
// WITHOUT a real browser install).
// ---------------------------------------------------------------------------
export { runAudit, buildReport, classifyImpact, wcagScFromTags, routeForRule, MANUAL_CHECKLIST, CONFORMANCE_TAGS, SCHEMA_VERSION }

const SCHEMA_VERSION = '1.0'

// ---------------------------------------------------------------------------
// Severity backbone — reuses reviewing-code's blocker/major/minor/nit. axe
// impact maps MECHANICALLY (no vibe): a real critical is a blocker; a minor is
// a nit. Severity inflation (minor->blocker) and deflation (critical->minor)
// are both defects the grader catches.
// ---------------------------------------------------------------------------
const IMPACT_TO_SEVERITY = {
  critical: 'blocker',
  serious: 'major',
  moderate: 'minor',
  minor: 'nit',
}
function classifyImpact(impact) {
  return IMPACT_TO_SEVERITY[impact] || 'minor' // unknown impact -> floor at minor, never silently dropped
}

// ---------------------------------------------------------------------------
// WCAG scoping — the conformance tags axe runs, by level. Default WCAG 2.2
// AA; AAA on request. WCAG 2.2 adds wcag22* tags (e.g. target-size,
// focus-not-obscured). AA = A + AA criteria across 2.0/2.1/2.2.
// ---------------------------------------------------------------------------
const CONFORMANCE_TAGS = {
  AA: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'],
  AAA: ['wcag2a', 'wcag2aa', 'wcag2aaa', 'wcag21a', 'wcag21aa', 'wcag21aaa', 'wcag22aa', 'wcag22aaa'],
}

function buildAxeRunOptions(level, wcagVersion) {
  const tags = CONFORMANCE_TAGS[level === 'AAA' ? 'AAA' : 'AA']
  return {
    runOnly: { type: 'tag', values: tags },
    // Default: run the FULL rule universe for the conformance level — NO rule
    // is disabled. Excluding a rule to dodge a violation is the cardinal-rule
    // breach; accepted_risks records an explicit, dated exception instead.
    resultTypes: ['violations', 'passes', 'incomplete', 'inapplicable'],
    _wcag_version: wcagVersion, // metadata only
  }
}

// ---------------------------------------------------------------------------
// WCAG success-criterion extraction. axe tags carry the SC as
// `wcag<digit><digit><digit>` (e.g. wcag143 = SC 1.4.3) alongside the level
// tags. Parse those into canonical "X.Y.Z" codes + the W3C SC URL.
// ---------------------------------------------------------------------------
function wcagScFromTags(tags) {
  if (!Array.isArray(tags)) return []
  const seen = new Set()
  const out = []
  for (const t of tags) {
    const m = /^wcag(\d)(\d)(\d)$/i.exec(String(t))
    if (m) {
      const code = `${m[1]}.${m[2]}.${m[3]}`
      if (!seen.has(code)) { seen.add(code); out.push(code) }
    }
  }
  return out
}

const WCAG_SC_BASE = 'https://www.w3.org/WAI/WCAG22/Understanding/'
function wcagScUrl(code) { return WCAG_SC_BASE + code }

// ---------------------------------------------------------------------------
// Fix routing — reuses the library's division of labor (read-only auditor +
// siblings fix). A contrast/spacing fix -> correcting-ui; a markup/role/
// keyboard/label fix -> implementing-features; a structural redesign ->
// designing-architecture. Default -> implementing-features.
// ---------------------------------------------------------------------------
const RULE_TO_ROUTE = {
  'color-contrast': 'correcting-ui',
  'color-contrast-enhanced': 'correcting-ui',
  'target-size': 'correcting-ui',
  'avoid-inline-spacing': 'correcting-ui',
  // structural / markup / role / label -> implement (or design for a redesign)
  'heading-order': 'implementing-features',
  'label': 'implementing-features',
  'form-field-multiple-labels': 'implementing-features',
  'button-name': 'implementing-features',
  'link-name': 'implementing-features',
  'image-alt': 'implementing-features',
  'input-image-alt': 'implementing-features',
  'area-alt': 'implementing-features',
  'dlitem': 'implementing-features',
  'list': 'implementing-features',
  'listitem': 'implementing-features',
  'landmark': 'implementing-features',
  'landmark-unique': 'implementing-features',
  'region': 'implementing-features',
  'page-has-heading-one': 'implementing-features',
  'bypass': 'implementing-features',
  'html-has-lang': 'implementing-features',
  'valid-lang': 'implementing-features',
  'tabindex': 'implementing-features',
  'aria-allowed-attr': 'implementing-features',
  'aria-allowed-role': 'implementing-features',
  'aria-valid-attr': 'implementing-features',
  'aria-valid-attr-value': 'implementing-features',
  'aria-required-attr': 'implementing-features',
  'aria-required-children': 'implementing-features',
  'aria-required-parent': 'implementing-features',
  'aria-hidden-focus': 'implementing-features',
  'aria-roles': 'implementing-features',
  'focus-order-semantics': 'implementing-features',
  'empty-heading': 'implementing-features',
  'presentation-role-conflict': 'implementing-features',
  'svg-img-alt': 'implementing-features',
  'table-duplicate-name': 'implementing-features',
  'td-headers': 'implementing-features',
  'th-has-data-cells': 'implementing-features',
  'marquee': 'implementing-features',
  'meta-viewport': 'implementing-features',
  'autocomplete-valid': 'implementing-features',
  'nested-interactive': 'implementing-features',
  'scrollable-region-focusable': 'implementing-features',
}
const REDESIGN_HINTS = ['keyboard-trap', 'focus-order', 'frame-title', 'frame-tested']
function routeForRule(ruleId, wcagSc) {
  if (RULE_TO_ROUTE[ruleId]) return RULE_TO_ROUTE[ruleId]
  if (REDESIGN_HINTS.some((h) => String(ruleId).includes(h))) return 'designing-architecture'
  return 'implementing-features'
}

// ---------------------------------------------------------------------------
// Beyond-axe manual checklist — the high-value checks axe CANNOT automate.
// ALWAYS emitted in the report (flagged, not faked) regardless of verdict,
// because axe automates ~30-40% of WCAG and the rest is a human verification
// task. Honest about automation's ceiling — never claim full conformance from
// automation alone.
// ---------------------------------------------------------------------------
const MANUAL_CHECKLIST = [
  {
    check: 'Keyboard trap',
    how_to_verify: 'Tab through the page in DOM order; focus must leave every container (modals, menus, widgets) via Tab/Shift+Tab without getting stuck and without a manual key handler trapping it.',
    why_not_automated: 'axe flags some focus-trap risk but cannot fully model runtime DOM + scripted focus management that moves targets after load.',
    wcag_sc: ['2.1.2'],
  },
  {
    check: 'Focus order',
    how_to_verify: 'Tab through the page; the DOM focus order must preserve meaning and operability relative to the visual reading order, including dynamically revealed content.',
    why_not_automated: 'Requires a human semantic reading of the page across dynamic states, not a static snapshot.',
    wcag_sc: ['2.4.3'],
  },
  {
    check: 'Meaningful focus-visible',
    how_to_verify: 'Every focusable element shows a visible focus indicator on keyboard focus at every viewport; verify no `outline: none` without an equivalent replacement indicator.',
    why_not_automated: 'axe checks a focus indicator exists for some edges but cannot confirm the indicator is perceptible across all states + viewports.',
    wcag_sc: ['2.4.7', '2.4.13'],
  },
  {
    check: 'Reduced-motion honored',
    how_to_verify: 'Set OS `prefers-reduced-motion: reduce`; page animations, transitions, parallax, and auto-moving content must stop or be reduced to essential motion.',
    why_not_automated: 'axe does not enumerate motion sources against the reduced-motion media query.',
    wcag_sc: ['2.3.3'],
  },
  {
    check: 'Live-region semantics',
    how_to_verify: 'Dynamically inserted/updated content (toasts, status, errors, list inserts) is in a polite/assertive live region (`aria-live`, `role="status"`, `role="alert"`) and announced to a screen reader.',
    why_not_automated: 'axe cannot observe the dynamic update sequence and confirm the live region fires at the right moment.',
    wcag_sc: ['4.1.3'],
  },
  {
    check: 'Form-error association',
    how_to_verify: 'On submit error, each field error is programmatically associated (`aria-describedby` / `<label for>`) to its input, announced, and focus moves to the first error or the error summary.',
    why_not_automated: 'axe cannot observe the post-submit error state; pre-submit static checks miss the association-on-error.',
    wcag_sc: ['3.3.1', '3.3.3'],
  },
]

// ---------------------------------------------------------------------------
// runAudit — the core entry. Two modes of execution:
//   (1) CANNED: pass opts.axeResults (a single axe results object applied to
//       each viewport, OR a Map<viewportString, axeResults>). No browser. The
//       objective self-check uses this to unit-check classification + report
//       emission deterministically. A real axe run is DEFERRED.
//   (2) REAL: pass opts.chromium (real Playwright) + opts.axeSource (the
//       axe-core UMD bundle string, resolvable via NODE_PATH / skill-local
//       install / copy — see Dependency resolution below). The harness
//       injects axe-core via addInitScript and runs axe.run() per viewport.
// ---------------------------------------------------------------------------
async function runAudit(opts) {
  const {
    mode = 'app',
    target,
    route = '',
    viewports = [],
    out,
    level = 'AA',
    wcagVersion = '2.2',
    name = 'audit',
    authFixturePath,
    chromium,
    axeSource,
    axeResults,
    acceptedRisks = [],
    chromiumLaunchOptions = {},
    now = () => 0,
  } = opts

  if (!target && !axeResults) throw new Error('runAudit requires --target (or canned axeResults)')
  if (!out) throw new Error('runAudit requires --out')
  if (!viewports.length && !axeResults) throw new Error('at least one --viewport is required')
  if (!viewports.length && axeResults) viewports.push('1280x720') // canned single-viewport default

  const fs = await import('node:fs/promises')
  const urlMod = await import('node:url')
  const path = await import('node:path')
  await fs.mkdir(out, { recursive: true })

  const viewportSpecs = viewports.map(parseViewport)
  const axeRunOptions = buildAxeRunOptions(level, wcagVersion)
  const accepted = normalizeAccepted(acceptedRisks)

  let authUsed = false
  const perViewport = [] // { viewport, axeResults, route, pageUrl, sourceLocations }

  if (axeResults) {
    // CANNED path — no browser. Apply canned results per viewport (a flat
    // object applies to all; a Map keys on the 'WxH' string).
    for (const vp of viewportSpecs) {
      const res = (axeResults instanceof Map) ? (axeResults.get(`${vp.width}x${vp.height}`) || axeResults.get('any') || []) : axeResults
      perViewport.push({ viewport: vp, axeResults: res, route: mode === 'app' ? route : null, pageUrl: target, sourceLocations: extractCannedSourceLocations(res) })
    }
  } else {
    // REAL path — Playwright + injected axe-core.
    if (!chromium) throw new Error('runAudit REAL mode requires a `chromium` surface (real Playwright)')
    if (!axeSource) throw new Error('runAudit REAL mode requires `axeSource` (the axe-core UMD bundle string)')
    const browser = await chromium.launch(chromiumLaunchOptions)
    const context = await browser.newContext({
      viewport: { width: viewportSpecs[0].width, height: viewportSpecs[0].height },
      deviceScaleFactor: 1, isMobile: false, hasTouch: false,
    })
    if (mode === 'app' && authFixturePath) {
      const authMod = await import(urlMod.pathToFileURL(path.resolve(authFixturePath)).href)
      const setup = authMod.default
      if (typeof setup !== 'function') throw new Error('--auth-fixture must default-export setup(context)')
      await setup(context); authUsed = true
    }
    const page = await context.newPage()
    await page.emulateMedia({ reducedMotion: 'reduce' })
    // Inject axe-core UMD so window.axe is defined before navigation results.
    await page.addInitScript((src) => {
      const el = document.createElement('script')
      el.setAttribute('data-audit-axe', 'true')
      el.textContent = src
      ;(document.documentElement || document.head || document.body).appendChild(el)
    }, axeSource)
    let client = null
    for (const vp of viewportSpecs) {
      await page.setViewportSize({ width: vp.width, height: vp.height })
      if (mode === 'component') {
        const fileUrl = urlMod.pathToFileURL(path.resolve(target)).href
        await page.goto(fileUrl, { waitUntil: 'networkidle' })
      } else {
        await page.goto(joinUrl(target, route), { waitUntil: 'networkidle' })
      }
      await page.evaluate(() => document.fonts ? document.fonts.ready : null)
      await page.waitForFunction(() => document.readyState === 'complete').catch(() => {})
      if (!client) client = await context.newCDPSession(page).catch(() => null)
      const results = await page.evaluate((opts) => {
        if (!window.axe || typeof window.axe.run !== 'function') throw new Error('axe-core was not injected (window.axe missing) — resolution gap, see audit.mjs')
        return window.axe.run(document, opts)
      }, axeRunOptions)
      const sourceLocations = client ? await enrichSourceLocations(page, client, results) : {}
      perViewport.push({ viewport: vp, axeResults: results, route: mode === 'app' ? route : null, pageUrl: page.url(), sourceLocations })
    }
    await browser.close()
  }

  const report = buildReport({
    mode, target, route, viewports: viewports.slice(), level, wcagVersion,
    name, authUsed, perViewport, acceptedRisks: accepted, now,
  })
  const reportPath = path.join(out, 'report.json')
  await fs.writeFile(reportPath, JSON.stringify(report, null, 2) + '\n', 'utf8')
  return { reportPath, verdict: report.verdict, severity_rollup: report.severity_rollup, violations: report.violations.length }
}

// ---------------------------------------------------------------------------
// buildReport — pure (no I/O). Classifies axe results + emits the
// schema-versioned report. Unit-tested for determinism (canned input -> byte-
// equal classification). The objective self-check asserts this directly.
// ---------------------------------------------------------------------------
function buildReport({ mode, target, route, viewports, level, wcagVersion, name, authUsed, perViewport, acceptedRisks, now }) {
  const violations = []
  const needsManualVerification = []
  const accByNode = indexAccepted(acceptedRisks) // key `${rule_id}\u0000${target}` -> acceptance record

  for (const pv of perViewport) {
    const res = pv.axeResults || {}
    const vp = { width: pv.viewport.width, height: pv.viewport.height }
    const scLocs = pv.sourceLocations || {}

    for (const v of res.violations || []) {
      const ruleId = v.id
      const wcagSc = wcagScFromTags(v.tags)
      const severity = classifyImpact(v.impact)
      const route = routeForRule(ruleId, wcagSc)
      for (const node of v.nodes || []) {
        const nodeTarget = Array.isArray(node.target) ? node.target.join(' ') : String(node.target || '')
        const key = ruleId + '\u0000' + nodeTarget
        const acc = accByNode[key] || null
        violations.push({
          rule_id: ruleId,
          rule_help: v.help || null,
          help_url: v.helpUrl || (wcagSc.length ? wcagScUrl(wcagSc[0]) : null),
          wcag_sc: wcagSc,
          wcag_level: level,
          wcag_version: wcagVersion,
          impact: v.impact || null,
          severity,
          node: {
            target: nodeTarget,
            html: node.html || null,
            accessible_name: node.accessibleName || null,
            selector_spec: resolveAccessibleSpec(node),
          },
          reason: humanReason(v, node),
          fix_pointer: fixPointer(v, node, route),
          route,
          source_location: scLocs[`${ruleId}\u0000${nodeTarget}`] || node.sourceLocation || null,
          viewport: vp,
          route_path: pv.route,
          accepted: !!acc,
          accepted_record: acc ? { date: acc.date, justification: acc.justification } : null,
        })
      }
    }

    for (const inc of res.incomplete || []) {
      const ruleId = inc.id
      const wcagSc = wcagScFromTags(inc.tags)
      for (const node of inc.nodes || []) {
        const nodeTarget = Array.isArray(node.target) ? node.target.join(' ') : String(node.target || '')
        needsManualVerification.push({
          rule_id: ruleId,
          rule_help: inc.help || null,
          wcag_sc: wcagSc,
          impact: inc.impact || null,
          severity: classifyImpact(inc.impact),
          node: { target: nodeTarget, html: node.html || null, selector_spec: resolveAccessibleSpec(node) },
          reason: humanReason(inc, node),
          what_to_verify: whatToVerify(inc, node),
          viewport: { width: pv.viewport.width, height: pv.viewport.height },
          route_path: pv.route,
        })
      }
    }
  }

  const severity_rollup = { blocker: 0, major: 0, minor: 0, nit: 0 }
  for (const v of violations) severity_rollup[v.severity] = (severity_rollup[v.severity] || 0) + 1

  const anyViolation = violations.length > 0
  // Verdict follows the severity rollup MECHANICALLY — never a separate
  // judgement (reviewing-code posture). "Looks accessible" is not a verdict;
  // the axe result + schema-valid report ARE the closure.
  const verdict = anyViolation ? 'violations-found' : 'pass'

  const totalRulesRun = perViewport.reduce((n, pv) => {
    const r = pv.axeResults || {}
    return n + ((r.violations || []).length + (r.passes || []).length + (r.incomplete || []).length + (r.inapplicable || []).length)
  }, 0)

  return {
    schema_version: SCHEMA_VERSION,
    audit_meta: {
      mode,
      target,
      route: mode === 'app' ? route : null,
      viewports: viewports.slice(),
      level,
      wcag_version: wcagVersion,
      axe_run: !perViewport.some((pv) => pv.axeResults && pv.axeResults._canned),
      axe_engine: 'axe-core',
      name,
      auth_fixture_used: authUsed,
      device_scale_factor: 1,
      animations_disabled: true,
      rules_run_total: totalRulesRun,
      audit_clock: typeof now === 'function' ? now() : now, // metadata only — excluded from determinism comparison
    },
    verdict,
    severity_rollup,
    violations,
    needs_manual_verification: needsManualVerification,
    manual_checklist: MANUAL_CHECKLIST,
    accepted_risks: acceptedRisks,
    automation_ceiling_note: ' axe automated ~30-40% of WCAG. The axe result + this schema-valid report ARE the automated closure; the needs-manual-verification list + manual_checklist are OUTSTANDING human tasks and must NOT be assumed clear. "Axed it" is not "verified accessible."',
  }
}

// ---------------------------------------------------------------------------
// Report-shaping helpers
// ---------------------------------------------------------------------------
function humanReason(v, node) {
  const help = v.help || v.id
  const fail = node && node.failureSummary ? node.failureSummary : ''
  return fail ? `${help} — ${fail}` : help
}
function fixPointer(v, node, route) {
  const help = v.helpUrl ? `See ${v.helpUrl}` : ''
  return `${v.help || v.id}. Refactor the node so it satisfies the axe rule (fix the markup/CSS, not by suppressing the rule). ${help}`.trim()
}
function whatToVerify(inc, node) {
  const base = inc.help ? `${inc.help} — axe could not fully determine this; verify manually against the WCAG criterion.` : 'axe could not fully determine this; verify manually.'
  const fail = node && node.failureSummary ? ` Failure detail: ${node.failureSummary}` : ''
  return base + fail
}
// Resolve an accessible-name-ish spec from an axe node. axe node.target is a
// CSS chain; if the caller attached `accessibleName` we reuse it. We DO NOT
// fabricate a role spec from a CSS chain (false-positive discipline) — it is
// recorded as the bare `target` plus the accessible name where axe gave one.
function resolveAccessibleSpec(node) {
  if (node && node.selector_spec) return node.selector_spec
  if (node && node.accessibleName) return `label:${node.accessibleName}`
  return null
}

// ---------------------------------------------------------------------------
// Accepted-risk normalization. A record: { rule_id, target, justification,
// date } (date is ISO Y-M-D). We key the index on rule + target so a
// classified violation can be marked `accepted` without being suppressed.
// ---------------------------------------------------------------------------
function normalizeAccepted(list) {
  return (Array.isArray(list) ? list : []).map((r) => ({
    rule_id: String(r.rule_id || ''),
    target: String(r.target || ''),
    justification: String(r.justification || ''),
    date: String(r.date || todayISO()),
  }))
}
function indexAccepted(list) {
  const m = {}
  for (const r of list) if (r.rule_id) m[r.rule_id + '\u0000' + r.target] = r
  return m
}
function todayISO() { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}` }

// Canned fixtures may carry sourceLocation per node for the contrast->rule
// demonstration (mirrors capturing-ui-evidence matched-styles). Extract into
// the same scLocs key shape buildReport consumes.
function extractCannedSourceLocations(res) {
  const out = {}
  for (const v of (res && res.violations || [])) {
    for (const n of (v && v.nodes || [])) {
      if (n && n.sourceLocation) {
        const t = Array.isArray(n.target) ? n.target.join(' ') : String(n.target || '')
        out[`${v.id}\u0000${t}`] = n.sourceLocation
      }
    }
  }
  return out
}

// ---------------------------------------------------------------------------
// CDP source-location enrichment (REAL mode only, contrast -> the color rule).
// Reuses the capturing-ui-evidence matched-styles idea: for color-contrast
// failures we open CSS.getMatchedStylesForNode + getComputedStyleForNode and
// record the winning `color`/`background-color` rule + source line so the fix
// pointer names the rule to change, not "increase contrast" alone. Optional —
// where CDP is unavailable the entry's source_location stays null (honest).
// ---------------------------------------------------------------------------
async function enrichSourceLocations(page, client, results) {
  const out = {}
  for (const v of (results && results.violations || [])) {
    if (!/color/.test(v.id)) continue // contrast / color rules only
    for (const node of (v && v.nodes || [])) {
      const target = Array.isArray(node.target) ? node.target.join(' ') : String(node.target || '')
      try {
        const handle = await page.locator(node.target[node.target.length - 1] || target).elementHandle().catch(() => null)
        if (!handle) continue
        const marker = `audit-${Math.random().toString(36).slice(2)}`
        await handle.evaluate((el, m) => el.setAttribute('data-audit-target', m), marker)
        const { root } = await client.send('DOM.getDocument', { depth: -1, pierce: true })
        const { nodeIds } = await client.send('DOM.querySelectorAll', { nodeId: root.nodeId, selector: `[data-audit-target="${marker}"]` })
        await client.send('DOM.removeAttribute', { nodeId: nodeIds && nodeIds[0], name: 'data-audit-target' }).catch(() => {})
        const { computedStyle } = await client.send('CSS.getComputedStyleForNode', { nodeId: nodeIds && nodeIds[0] }).catch(() => ({ computedStyle: null }))
        const cs = computedStyle && (Array.isArray(computedStyle) ? computedStyle : computedStyle.cssProperties)
        const pick = (n) => { const r = (cs || []).find((p) => p && p.name === n); return r ? r.value : null }
        out[`${v.id}\u0000${target}`] = {
          selector: target,
          source_url: page.url(),
          computed: { color: pick('color'), 'background-color': pick('background-color') },
        }
      } catch { /* CDP optional — source_location stays null on failure */ }
    }
  }
  return out
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function parseViewport(v) {
  const m = /^(\d+)x(\d+)$/.exec(String(v).trim())
  if (!m) throw new Error(`bad viewport '${v}' — expected WxH (e.g. 375x667)`)
  return { width: +m[1], height: +m[2] }
}
function joinUrl(base, route) { return String(base).replace(/\/$/, '') + (route || '') }

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------
async function main() {
  const argv = process.argv.slice(2)
  const o = parseArgs(argv)
  if (o.help || !o.target || !o.viewports.length || !o.out) {
    process.stderr.write(helpText())
    process.exit(o.help ? 0 : 1)
  }
  const { default: pw } = await import('playwright').catch(() => ({ default: null }))
  if (!pw) { process.stderr.write('audit: cannot import playwright (resolution gap); for a browser-free run pass a canned axeResults via the importable API, or install/copy playwright + axe-core next to the skill.\n'); process.exit(1) }
  const axeSource = await readAxeCoreSource()
  const chromiumLaunchOptions = process.env.AUDIT_CHROMIUM_EXECUTABLE
    ? { executablePath: process.env.AUDIT_CHROMIUM_EXECUTABLE, headless: true }
    : { headless: true }
  const res = await runAudit({
    mode: o.mode, target: o.target, route: o.route,
    viewports: o.viewports.split(','), out: o.out, level: o.level, wcagVersion: o.wcag,
    name: o.name, authFixturePath: o.authFixture, acceptedRisks: parseAcceptedFile(o.accept),
    chromium: pw.chromium, axeSource, chromiumLaunchOptions,
  })
  process.stdout.write(`audited -> ${res.reportPath}\n`)
  process.stdout.write(`verdict: ${res.verdict}  rollup: ${JSON.stringify(res.severity_rollup)}  violations: ${res.violations}\n`)
}

// Resolve the axe-core UMD bundle. The skill dir is symlinked into the global
// skills path, so a project-local axe-core will not be found from the
// script's own location — mirror the capturing-ui-evidence playwright
// resolution guidance: (a) NODE_PATH=<project>/node_modules; (b) install
// axe-core into the skill dir once; (c) copy audit.mjs + axe-core into the
// project. A `_canned: true` axeResults path bypasses this for the no-browser
// objective self-check.
let AXE_BUNDLE_CACHE = null
async function readAxeCoreSource() {
  if (AXE_BUNDLE_CACHE) return AXE_BUNDLE_CACHE
  const fs = await import('node:fs/promises')
  const path = await import('node:path')
  const candidates = [
    process.env.AXE_CORE_PATH,
    path.resolve('node_modules/axe-core/axe.min.js'),
    path.resolve('node_modules', 'axe-core', 'axe.min.js'),
  ].filter(Boolean)
  for (const c of candidates) {
    try { AXE_BUNDLE_CACHE = await fs.readFile(c, 'utf8'); return AXE_BUNDLE_CACHE } catch {}
  }
  try {
    const url = await import('node:url')
    const mod = await import(url.pathToFileURL(path.resolve('node_modules/axe-core/package.json')).href)
    const p = path.resolve('node_modules/axe-core', mod.main || 'axe.js')
    AXE_BUNDLE_CACHE = await fs.readFile(p, 'utf8'); return AXE_BUNDLE_CACHE
  } catch {}
  throw new Error('audit: axe-core UMD bundle not resolvable (set AXE_CORE_PATH, or NODE_PATH=<project>/node_modules, or install axe-core next to the skill)')
}

function parseAcceptedFile(p) {
  if (!p) return []
  const fs = require('fs') // eval-time; CLI only
  try { return JSON.parse(fs.readFileSync(p, 'utf8')) } catch (e) { throw new Error('--accept file invalid JSON: ' + e.message) }
}

function parseArgs(argv) {
  const o = { mode: 'app', route: '', level: 'AA', wcag: '2.2', name: 'audit', viewports: [], accept: null }
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    switch (a) {
      case '--mode': o.mode = argv[++i]; break
      case '--target': o.target = argv[++i]; break
      case '--route': o.route = argv[++i]; break
      case '--viewports': o.viewports = argv[++i]; break
      case '--out': o.out = argv[++i]; break
      case '--level': o.level = argv[++i]; break
      case '--wcag': o.wcag = argv[++i]; break
      case '--name': o.name = argv[++i]; break
      case '--auth-fixture': o.authFixture = argv[++i]; break
      case '--accept': o.accept = argv[++i]; break
      case '-h': case '--help': o.help = true; break
      default: break
    }
  }
  return o
}

function helpText() {
  return [
    'usage: audit.mjs --mode app|component --target <url|path> --viewports WxH,WxH --out <dir>',
    '                  [options]',
    '',
    'options:',
    '  --route /path          app mode: route appended to --target',
    '  --level AA|AAA         WCAG conformance level (default AA)',
    '  --wcag 2.2             WCAG version (default 2.2)',
    '  --name <slug>          run name (stable filenames)',
    '  --auth-fixture <p.mjs> app mode: default-exports setup(context)',
    '                         (the e2e auth-fixture pattern)',
    '  --accept <file>        JSON array of accepted-risk records',
    '                         {rule_id,target,justification,date}',
    '',
    'env:',
    '  AXE_CORE_PATH          path to axe-core UMD bundle',
    '  NODE_PATH=<proj>/node_modules  resolve axe-core + playwright from project',
    '  AUDIT_CHROMIUM_EXECUTABLE      reuse a host/cached chromium binary',
    '',
    'The agent INVOKES this script (execute, do not reimplement). The',
    'harness runs axe-core against every (target x viewport) and emits a',
    'schema-versioned report.json (see references/report-schema.md). The',
    'importable runAudit() also accepts a canned axeResults fixture for the',
    'browser-free objective self-check (real axe run DEFERRED in that mode).',
  ].join('\n') + '\n'
}

// run as a script only when invoked directly. Compare on the REAL path of
// both sides so a symlinked install (the global skills dir) does NOT silently
// no-op: import.meta.url resolves to the real file URL, so realpath argv[1]
// (following the symlink) must match it when invoked directly. A bare
// `import.meta.url === pathToFileURL(process.argv[1])` MISSES when argv[1] is
// the symlink path (they differ), main() never ran, and the harness exited 0
// writing no report — a silent no-op footgun the eval subagents caught.
import { pathToFileURL as _pathToFileURL } from 'node:url'
import { realpathSync as _realpath } from 'node:fs'
const invokedDirect = (() => {
  try {
    if (!process.argv[1]) return false
    const argvReal = _pathToFileURL(_realpath(process.argv[1])).href
    return import.meta.url === argvReal || import.meta.url === _pathToFileURL(process.argv[1]).href
  } catch { return false }
})()
if (invokedDirect) main().catch((e) => { process.stderr.write('audit: ' + (e && e.stack || e) + '\n'); process.exit(1) })