---
name: auditing-accessibility
description: Proactively audits a page/route/component for accessibility (a11y) violations, reporting severity, WCAG criterion, node, reason, fix pointer — then STOPs, read-only on the code. Runs a deterministic Playwright + axe-core harness (bundled scripts/audit.mjs) over a dev-server route or a component harness, scoped to WCAG 2.2 AA (AAA on request). axe-incomplete plus a beyond-axe checklist surface as needs-manual-verification — automation ceiling honest, not faked. Never greens by suppressing a rule or narrowing scope; an explicit risk acceptance is recorded dated. A clean page gets a clean report. Fixes route to correcting-ui, implementing-features, or designing-architecture. Use when the user says audit a11y for X, is this WCAG-compliant, is this page accessible, or from capturing-ui-evidence — even without saying audit. Not for fixing a11y, capturing CSS evidence, or writing e2e tests.
metadata:
  library: ai-framework
  phase: "3"
  loop: ui
---

# Auditing Accessibility

The proactive auditor of the UI iteration loop (Phase 3). Given a page/route/
isolated component, the auditor **finds** accessibility (a11y) violations and
reports each with severity, the WCAG success criterion, the offending node, a
concrete reason, and a fix pointer — then **STOP**s. It is **read-only on the
code**: it diagnoses and routes, it does not fix. A contrast/spacing fix routes
to `correcting-ui`; a markup/role/keyboard/label fix routes to
`implementing-features`; a structural redesign routes to `designing-architecture`.

The division of labor with the reactive UI-loop skills: `capturing-ui-evidence`
captures a single screenshot + computed-CSS + matched-styles *artifact*; this
skill audits an *automated accessibility* pass. `correcting-ui` fixes CSS;
`implementing-features` fixes markup. This skill reports. The axe result + the
schema-valid report ARE the closure — "looks accessible" is not.

An audit pass is **done** when axe has run against every requested (target ×
viewport), the `report.json` is schema-valid (see
[references/report-schema.md](references/report-schema.md) — the single source
of truth), every violation is classified by severity + WCAG criterion + a
concrete reason + a fix pointer + a route, and a verdict is issued (`pass` /
`violations-found` with the severity rollup). Honest about the automation
ceiling: checks axe cannot fully judge resurface in a `needs_manual_verification`
list + a `manual_checklist`; never silently dropped, never faked into a clean
pass. Then **STOP** — report only; never edit, never commit.

## The audit pass

Copy this checklist and check off items as you complete them.

```
Audit Progress:
- [ ] 1. Identify the input (target, viewports, WCAG level, auth fixture)
- [ ] 2. Detect stack & load the matching audit-stack reference
- [ ] 3. Invoke the harness (scripts/audit.mjs) — execute, do not reimplement
- [ ] 4. Objective closure (validate the report; defer the real browser)
- [ ] 5. Report + route each violation; STOP (read-only)
```

### Step 1 — Identify the input

Four things pin an audit run; fix them before invoking the harness.

- **The target, which selects the mode.** A *real running app* — a dev-server
  URL + a route — is **app mode**(`--mode app --target http://localhost:5173
  --route /dashboard`). If the view needs a session, pass `--auth-fixture
  <p.mjs>` (the e2e auth-fixture pattern — a module that default-exports
  `setup(context)` seeding the token via `addInitScript`, NOT replaying the
  login UI). An *isolated component* — a Storybook-style harness HTML entry —
  is **component mode** (`--mode component --target ./harness/index.html`,
  loaded over `file://`, no dev server, no auth).
- **The viewports.** One or more `WxH` specs (e.g. `375x667,1280x720`). A
  contrast failure may differ by viewport; the report keys violations per
  (target × viewport) and the rollup counts each occurrence — that is the
  honest accounting, not double counting.
- **The WCAG conformance level.** Default **WCAG 2.2 AA**; `--level AAA` on
  explicit request. Do not silently downgrade to A, do not invent AAA. The
  level is the scope of what axe runs; record it in `audit_meta.level` +
  `audit_meta.wcag_version`.
- **Explicit risk acceptances, if any.** If the user has already (explicitly,
  signed-off) accepted a known violation's risk, pass `--accept <file.json>`
  carrying `{rule_id, target, justification, date}` records. The violation
  STAYS in the report (marked `accepted` with the dated record) and STILL
  counts in the rollup — an accepted risk is a decision, not a resolution.

### Step 2 — Detect stack & load the matching audit-stack reference

Identify the project stack from the rules file (`AGENTS.md` /
`.opencode/agents.md`). If this skill bundles a matching reference under
`references/stacks/` (resolved against this skill's own directory — not the
project's), read it now and apply its audit concerns. If none exists, proceed
generically and flag the gap in the report's `automation_ceiling_note`.

Available stack references:

- vue-supabase → [references/stacks/vue-supabase.md](references/stacks/vue-supabase.md)
  Read when the project is Vue 3 + Pinia + Vuetify 3 + Supabase + Playwright.
  Applies Vuetify component built-in a11y + where it breaks (icon-only `v-btn`
  without `aria-label`, omitted `v-text-field` `label` prop), Vuetify
  theme-contrast-token pitfalls, route-level SPA focus management gaps, and the
  beyond-axe checks this stack especially needs (keyboard trap in `v-dialog`/
  `v-menu`, snackbar live-region semantics, reduced-motion in transitions).

### Step 3 — Invoke the harness (execute, do not reimplement)

`scripts/audit.mjs` is the bundled "right tool for the job": a Playwright +
axe-core harness, more reliable than generated code and zero context until its
output returns. **Execute** it — do not read it as a reference and do not
reimplement its audit logic. Invoke it:

```bash
# app mode — a running route, auth via the e2e auth-fixture pattern
node <this-skill>/scripts/audit.mjs \
  --mode app --target http://localhost:5173 --route /dashboard \
  --viewports 375x667,1280x720 --out ./a11y \
  --auth-fixture e2e/fixtures/auth.mjs --level AA

# component mode — an isolated component harness over file://
node <this-skill>/scripts/audit.mjs \
  --mode component --target ./harness/index.html \
  --viewports 375x667,1280x720 --out ./a11y
```

The harness writes, per run, to `--out/report.json` — the schema-versioned
artifact each violation fully classified + the severity rollup + the verdict +
needs-manual-verification + the manual checklist + accepted_risks. The
harness injects axe-core, runs it per viewport against the FULL rule universe
for the chosen WCAG level (NO rule is disabled by default — see the cardinal
rule below), and where a real browser + CDP are available it records the
contrast rule's source location (the matched-styles idea from
`capturing-ui-evidence`).

**Dependency resolution (do this before invoking).** `audit.mjs` does
`await import('playwright')` and reads the axe-core UMD bundle, both ESM-
resolved from the script's own location. When the skill is installed globally
(symlinked into `~/.config/opencode/skills/`), that location is NOT the
project, so a project-local `playwright`/`axe-core` will not be found and the
harness exits without writing a report. Ensure both are resolvable from the
run — the reliable options, in order: (a) run with the project's modules on
the path, `NODE_PATH=<project>/node_modules node .../audit.mjs …`; (b) if the
skill dir is writable, install `playwright` + `axe-core` there once; (c) copy
`audit.mjs` into the project and run it from the project root. Where a chromium
binary is available but the pinned Playwright build is not (a cached build, a
system Chrome), set `AUDIT_CHROMIUM_EXECUTABLE=<path/to/chrome>`; where the
axe-core UMD needs a pointer, set `AXE_CORE_PATH=<path/to/axe.min.js>`. If the
harness errors with `Cannot find package 'playwright'` or `axe-core UMD bundle
not resolvable`, this is a resolution gap, not an audit failure.

### Step 4 — Objective closure

An audit pass closes on objective signals, never on "looks accessible".

- In a real environment: the harness exits 0 and `--out/report.json` exists. Verify
  it is schema-valid — the contract is
  [references/report-schema.md](references/report-schema.md); run the bundled
  schema validator from the eval fixture (`scripts/validate-report.js <path>`)
  if present, or check the verdict follows the rollup mechanically and the
  `manual_checklist` is present. The verdict + the schema-valid report ARE the
  closure.
- Where a real browser is NOT available (eval harness, CI sandbox), a real axe
  run cannot execute. Closure is then the **objective self-check**: run `npm run
  test` (the bundled structural verifier `scripts/verify-audit.js` in the eval
  fixture) which imports `runAudit` from the skill, feeds it a canned axe-results
  fixture, and asserts the emitted `report.json` is schema-valid + every planted
  violation is caught at the right severity + WCAG SC + verdict + routing + ZERO
  source edits. Document the real-browser axe run as **deferred** (per the
  `capturing-ui-evidence` / `writing-e2e-tests` real-browser-deferral precedent)
  — honest deferral, not a silent skip.
- Where a chromium + axe-core ARE available (a cached build via
  `AUDIT_CHROMIUM_EXECUTABLE` + `AXE_CORE_PATH`), the harness runs a REAL axe
  pass and the live `report.json` validates against the SAME schema. Prefer a
  realized real run whenever the runtime is reachable — it realizes the
  otherwise-deferred validation rather than only documenting it.

### Step 5 — Report + route each violation; STOP

Report, concisely: **report path**; **verdict** (pass / violations-found);
**severity rollup** (blocker/major/minor/nit counts); the per-violation
routing (color-contrast → `correcting-ui`; image-alt/label/heading-order →
`implementing-features`; a focus-trap redesign → `designing-architecture`);
the **needs-manual-verification** surface + the **manual checklist** as
outstanding human tasks; the **deferred real-browser validation** status where
no browser is available; any `accepted_risks` recorded. Then **STOP**. Do not
edit source, do not commit, do not push, do not open a PR. The auditor
diagnoses + routes; the sibling fixes.

## Severity backbone + verdict (mechanical, not a vibe)

Reuses `reviewing-code`'s blocker/major/minor/nit backbone. axe impact maps
mechanically: `critical` → blocker, `serious` → major, `moderate` → minor,
`minor` → nit. The verdict follows the rollup: any violation →
`violations-found`; none → `pass`. Never inflate (a minor into a blocker to
seem thorough) and never deflate (a critical into a minor): a genuinely
accessible page gets a clean `pass` (false-positive discipline), and a real
critical is a blocker even if the rest of the page is clean. Severity follows
axe impact + WCAG level, mechanically — the same reason `reviewing-code`
severities do.

## Honest about automation's ceiling

axe automates ~30-40% of WCAG. The rest is human verification. The report is
honest, not faked:

- **needs_manual_verification** — axe `incomplete` results (axe ran a rule but
  could not fully judge: contrast at non-default states, focus-visible
  perceptibility, name-role-value for custom widgets) resurface here with the
  node + `what_to_verify`. Never quietly flattened to `pass` nor inflated into
  a violation.
- **manual_checklist** — a documented, ALWAYS-present list of the high-value
  checks axe cannot automate (keyboard trap, focus order, meaningful
  focus-visible, reduced-motion honored, live-region semantics, form-error
  association). A `pass` verdict does NOT discharge it. The
  `automation_ceiling_note` states manual verification is OUTSTANDING.
  "Axed it" is not "verified accessible."

## The cardinal rule: never green an audit by suppressing a rule

From `debugging-test-failures` (never green by weakening the net): never make
an audit pass by suppressing a rule / excluding a node / narrowing scope to
dodge a violation. These are all the same move — making the signal lie. The
harness runs the FULL rule universe for the WCAG level by default; a prompt
that says "just exclude that rule so it passes for the demo" is refused by
default — the auditor explains in the transcript why suppressing hides a real
defect, runs the audit WITHOUT excluding, and routes the fix.

If the user **explicitly accepts** a violation's risk (an owner's signed-off
decision), comply only with an **explicit, dated record**: pass the
`--accept <file.json>` records, OR state them so the auditor records them in
the report's `accepted_risks`. The violation STAYS (marked `accepted` with the
dated record) and STILL counts in the rollup — a suppressed check WITH a
record is a decision; a silent suppression (the violation removed, no record)
is a lie. The `reviewing-code` false-positive discipline runs the other way:
manufacturing a violation to seem thorough, or inflating a nit into a blocker,
is the symmetric defect — refuse it too.

## Read-only + routing

The auditor never edits source. Each violation's `route` names the sibling
that owns the fix:

- **`correcting-ui`** — a contrast / spacing / color-token fix (snaps to a
  token via the matched-styles map, never a magic px).
- **`implementing-features`** — a markup / role / keyboard / label fix
  (missing `alt`, missing `label`, wrong heading order, bad ARIA, a keyboard
  handler). Trivial fixes proceed directly; an out-of-scope urge is recorded as
  a follow-up (the `implementing-features` posture).
- **`designing-architecture`** — a structural a11y fix that needs a component
  or interaction redesign (e.g. a modal that traps focus and needs a focus-
  management redesign; a custom widget that needs name-role-value re-architecting).

Report + STOP. The handoff is the gate; the user decides whether to fix,
re-plan, or accept the risk.

## Closure

An audit pass is done, all at once, when:

1. **axe ran against every (target × viewport)** — no scope skipped.
2. **Every violation classified** by severity + WCAG criterion + node + reason +
   fix pointer + route; the verdict follows the rollup mechanically.
3. **Automation ceiling flagged** — `needs_manual_verification` +
   `manual_checklist` present; a `pass` does not discharge manual verification.
4. **`report.json` schema-valid** — versioned contract, drift detectable.
5. **Zero source edits** — the auditor is read-only; fixes route to siblings.
6. **Any suppression is a dated `accepted_risks` record**, never silent — the
   cardinal rule holds.

"Looks accessible" without running axe + validating the report is not closure
— reopen Step 3.

## When not to use this skill

- **Fixing an a11y defect** — that is `correcting-ui` (CSS/contrast) or
  `implementing-features` (markup/role/keyboard). This skill reports; it
  routes, it does not patch.
- **Capturing CSS evidence / a single screenshot + matched-styles** — that is
  `capturing-ui-evidence`. This audit's report is a different artifact (axe
  violations + WCAG mapping), keyed per (target × viewport).
- **Writing e2e tests** — that is `writing-e2e-tests`. A one-shot audit pass is
  not a persistent regression spec; an a11y regression assertion in the suite
  is a test, not an audit report.
- **Inspecting one element's computed CSS manually.** A quick `getComputedStyle`
  or devtools pass is faster when there is no contract to preserve. The audit
  pays when a developer/CI gate will consume the report.

## References

- [references/report-schema.md](references/report-schema.md) — the report.json
  CONTRACT (single source of truth): top-level shape, `audit_meta`, the verdict
  + severity rollup, `violations[]` (axe rule id, WCAG SC, severity, node,
  reason, fix pointer, route, optional source_location), the severity backbone
  (axe impact → blocker/major/minor/nit), `needs_manual_verification[]`
  (axe incomplete), the `manual_checklist[]` (beyond-axe, always emitted),
  `accepted_risks[]` (dated), WCAG scoping + the SC mapping, determinism,
  versioning + drift. Read when authoring or validating a report, or when a
  consumer reads one.
- [references/stacks/vue-supabase.md](references/stacks/vue-supabase.md) —
  audit concerns for the Vue 3 + Vuetify 3 + Supabase + Playwright stack.
  Read at Step 2 when the project's rules file declares stack `vue-supabase`.
- `scripts/audit.mjs` — the deterministic Playwright + axe-core harness
  (execute; see `--help` for options). Exports `runAudit` so the objective
  self-check can feed a canned axe-results fixture (no browser install) and
  assert the emitted report is schema-valid + correctly classified.
- The selector / auth-fixture / real-browser-deferral doctrine this skill reuses
  lives in [../writing-e2e-tests/SKILL.md](../writing-e2e-tests/SKILL.md) —
  role/accessible-name/testid preference, condition waits (never
  `waitForTimeout`), the auth-fixture session pattern, and the structural-
  verifier-when-no-browser precedent.
- The severity backbone + false-positive discipline this skill reuses lives in
  [../reviewing-code/SKILL.md](../reviewing-code/SKILL.md) — the blocker/
  major/minor/nit table and the "do not manufacture severity" rule.
- The cardinal rule (never green by suppressing a rule) is defined in
  [../debugging-test-failures/SKILL.md](../debugging-test-failures/SKILL.md) —
  the never-weaken-the-net posture this auditor inherits for suppression.
- The matched-styles source-location idea (contrast → the color rule) is
  defined in
  [../capturing-ui-evidence/references/evidence-schema.md](../capturing-ui-evidence/references/evidence-schema.md)
  — this skill reuses the symptom → source-rule lookup for contrast failures
  where real-browser CDP is available.