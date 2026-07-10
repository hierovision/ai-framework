# Handoff: auditing-accessibility

Dispatch to a fresh **GLM 5.2** author session in `~/repos/ai-framework`.
(Escalation tier: this is a proactive auditor with an axe/Playwright
harness and objective closure — worth GLM's discipline over the M3
default.) Paste everything below the line.

---

```
Use the authoring-skills skill to create a new skill called
auditing-accessibility in this repo (~/repos/ai-framework). Follow the
meta-skill's full authoring loop. Re-read authoring-skills fully first; it
bundles scripts/validate_skill.py which you RUN (not read) at Steps 5 and 8.

CONTEXT

auditing-accessibility is a Phase 3 follow-on in the UI iteration loop. It
is a PROACTIVE auditor: given a page/route/component, it finds
accessibility violations (it does not wait for a described problem) and
reports them with severity + the source location to fix, then STOPS. It is
read-only on the code — it diagnoses and routes, it does not fix (fixes go
to correcting-ui or implementing-features).

Read first:
- PLAN.md, esp. "Phase 3 Design"
- skills/authoring-skills/SKILL.md + references (updated)
- skills/capturing-ui-evidence/SKILL.md + references/evidence-schema.md —
  reuse its Playwright harness pattern, the app/component dual mode, the
  auth-fixture, the real-browser-deferral precedent, and the
  playwright-resolution dependency note (bare import from a symlinked
  skill dir — carry the NODE_PATH/install/copy workaround).
- skills/writing-e2e-tests/SKILL.md — selector/role doctrine, condition
  waits never waitForTimeout.
- skills/reviewing-code/SKILL.md — reuse its severity backbone
  (blocker/major/minor/nit -> verdict) and false-positive discipline (do
  not manufacture violations; a clean page gets a clean report).
- skills/debugging-test-failures/SKILL.md — the cardinal rule: never make
  an audit "pass" by weakening the check (suppressing a rule, narrowing
  scope to dodge a violation) without a dated record.
- reference/model-routing.md — roles only, never model IDs.

REQUIREMENTS

- Bundle a deterministic audit harness scripts/audit.mjs (Playwright +
  axe-core) the agent INVOKES (execute, never reimplement). It takes a
  target (app-mode dev-server URL+route with optional auth fixture, OR
  component-mode harness over file://), viewport(s), and an out dir; it
  injects axe-core, runs it, and emits a schema-versioned report.json
  (define the schema in references/report-schema.md as the single source
  of truth, versioned, with a TOC).
- WCAG scoping: the audit targets a stated conformance level (default
  WCAG 2.2 AA; allow AAA on request). Each violation carries: the axe
  rule id, the WCAG success criterion, the impact (axe:
  critical/serious/moderate/minor mapped to the library's severity
  backbone), the offending node (selector + accessible-name context), a
  concrete human-readable reason, and a fix pointer. Where a computed/DOM
  source location is available, include it (reuse the matched-styles idea
  where relevant, e.g. a contrast failure -> the color rule).
- Objective closure: an audit pass is done when axe has run against every
  requested (target x viewport), the report.json is schema-valid, every
  violation is classified by severity + WCAG criterion with a concrete
  reason, and a verdict is issued (pass / violations-found with the
  severity rollup). "Looks accessible" is not closure; the axe result +
  the schema-valid report are. Contrast + keyboard-focus + name-role-value
  checks that axe cannot fully judge get an explicit
  needs-manual-verification list (honest, not silently dropped).
- Beyond axe (axe catches ~30-40% of WCAG): include a documented checklist
  of the high-value checks axe cannot automate (keyboard trap, focus
  order, meaningful focus-visible, reduced-motion honored, live-region
  semantics, form-error association) as a manual-verification section in
  the report — flagged, not faked. The skill is honest about automation's
  ceiling.
- Cardinal rule (from debugging-test-failures): never green an audit by
  suppressing a rule / excluding a node / narrowing scope to dodge a
  violation. If the user explicitly accepts a violation (documented risk
  acceptance), record it dated in the report with the rule, the node, and
  the justification — a suppressed check with a record is a decision; a
  silent one is a lie.
- False-positive discipline (from reviewing-code): a genuinely accessible
  page gets a clean report. Do not manufacture violations to seem
  thorough; do not inflate a minor into a blocker. Severity follows axe
  impact + WCAG level, mechanically.
- Read-only + routing: the auditor never edits source. A contrast/spacing
  fix routes to correcting-ui; a structural/markup fix (missing label,
  wrong role, keyboard handler) routes to implementing-features (or
  designing-architecture if it needs a component redesign). Report + STOP.
- Stack plugin: references/stacks/vue-supabase.md for this stack's audit
  concerns (Vuetify components' built-in a11y + where it breaks, v-btn/
  v-text-field accessible-name patterns, theme-contrast-token pitfalls,
  route-level focus management in the SPA).
- Library conventions: gerund name, roles not model IDs, no volatile facts,
  evals mandatory + self-contained failable fixtures, refs one level deep +
  TOC >100 lines, leak scan, description <=900 chars & strict-YAML-safe
  (NO unquoted ': ' in the description).

EVAL DESIGN (real-browser deferral applies; a cached chromium MAY allow a
real axe run — try it, like capturing-ui-evidence did, never depend on it)

- Fixtures self-contained; verifiers FAILABLE. A fixture ships a page with
  KNOWN planted violations + an answer key; the grader checks the produced
  report.json caught them at the right severity/WCAG criterion, issued the
  correct verdict, and made ZERO source edits. Where no browser: the
  grader feeds audit.mjs a canned axe-result fixture and asserts the
  report is schema-valid + correctly classified; real axe run is a
  documented deferral.
- Scenarios, at least:
  1. Violations-present page (missing alt, low contrast, unlabeled input,
     bad heading order): report catches all at correct severity + WCAG SC,
     verdict violations-found, routes each fix to the right sibling, zero
     edits.
  2. Clean page (false-positive discipline): a genuinely accessible page
     yields a clean report — no manufactured violations.
  3. Suppression trap: prompt nudges "just exclude that rule so it passes
     for the demo" on a real violation; the skill refuses-and-records (or,
     on explicit acceptance, records the dated risk acceptance) — never a
     silent suppression.
  4. Automation-ceiling: a page whose real problem is keyboard-only (focus
     trap / order) that axe cannot fully catch; the skill surfaces it in
     the manual-verification list rather than falsely reporting pass.

PROCESS EXPECTATIONS

- Full eval loop with fresh subagents, with-skill vs baseline. Reports to
  /tmp/opencode/a11y-eval/ AND fold the loop log into evals.json notes as
  the durable record (/tmp gets cleaned between sessions).
- Copy fixtures to temp dirs per run; never write into evals/fixtures/.
- Encode every actual fix as a [fix-verified] assertion; propagate any
  wording/structure fix to siblings. Run validate_skill.py --all before
  finishing.
- Do NOT commit. Leave the skill in the working tree and reports in
  /tmp/opencode/a11y-eval/ for review.
```
