---
name: validating-ui
description: Validates a changed flow's runtime UI inside the implementing-features loop — a real browser walks the journey, console errors AND warnings AND pageerrors block unless allowlisted (dated + justified entries), a screenshot + ariaSnapshot are archived, and council-ux (text evidence) reviews correctness / appropriateness / accessibility with findings fed back to the implementer (bounded to 2 fix cycles). Invoked by implementing-features Step 8; use whenever a change has visible UI and the implement loop reaches the runtime-validation gate. Not for authoring e2e specs (writing-e2e-tests), capturing CSS evidence (capturing-ui-evidence), axe audits (auditing-accessibility), or fixing CSS (correcting-ui).
---

# Validating UI (in-loop runtime validation)

Validate the runtime behavior of a just-implemented change through a real
browser, at the point in the implement loop where tests are green and
before the coverage gate. The step's job is the residue the suite cannot
see: console errors / warnings / pageerrors (dev-server-only defects),
teardown crashes on close paths, and the UX subagent's review of
correctness / appropriateness / accessibility. Stack-agnostic body: the
only framework-specific guidance lives in
[references/stacks/vue-supabase.md](references/stacks/vue-supabase.md)
(and the sibling skills' own stack references); projects adapt via local
overrides (`--target`, `--journey`, `--allowlist`, `--auth-fixture`).

## The validation pass

```
Validation Progress:
- [ ] 1. Identify the changed flow (from the plan's ACs + the diff)
- [ ] 2. No visible UI -> explicit "no visible UI" skip note; STOP
- [ ] 3. Author/adapt the journey module (writing-e2e-tests doctrine)
- [ ] 4. Run scripts/smoke.mjs (net: errors AND warnings AND pageerrors block unless allowlisted)
- [ ] 5. Invoke council-ux on the text evidence (correctness / appropriateness / accessibility)
- [ ] 6. Fix findings in scope; bounded re-run (max 2 cycles)
- [ ] 7. Return: net verdict + findings + residual follow-ups
```

### Step 1 — Identify the changed flow

Read the plan's ACs + the implement diff and name the user flow that
exercises the change (the route, the dialog, the interaction). If the
project's e2e suite has a spec for that flow (authored at the
implement pass's red-first Step 5), its selectors are the journey's
starting point.

### Step 2 — No visible UI

If the change has no visible UI (pure logic, internal store refactor):
skip the harness with an explicit **"no visible UI"** note in the run
summary — the explicit negative is the closure signal, mirroring the
coverage gate. Do not invent a flow.

### Step 3 — Author/adapt the journey module

Journey module contract: `references/evidence-schema.md`. Reuse the
e2e spec's selectors where they exist; otherwise author per
`writing-e2e-tests` doctrine (role / accessible-name / testid; condition
waits, never `waitForTimeout`; auth via fixture). **Journey-completeness
rule (R2):** a journey that opens a dialog/form must exercise its close
path — including closing with the form in an open/edited state — or
explicitly justify why the close path is out of scope. Teardown crashes
live on close paths; a journey that asserts console-clean mid-journey
with the dialog open proves nothing (the incident's exact gap).

### Step 4 — Run the harness

```
node scripts/smoke.mjs --target <dev-server-url> \
  --journey <project>/.opencode/smoke/<plan-slug>.journey.mjs \
  --out .opencode/evidence/<plan-slug>/ \
  [--allowlist .opencode/smoke-allowlist.json] \
  [--auth-fixture <storageState.json>] \
  [--clip-role <role> --clip-name <name> | --clip-testid <id>]
```

Runtime dirs: `.opencode/smoke/` (journey modules), `.opencode/evidence/`
(screenshots, evidence.json, REVIEW.md) and `.opencode/smoke-allowlist.json`
are **runtime artifacts, gitignored by default** (the library's
`.gitignore` ignores `.opencode/`); never commit them.

**Net discipline (R1):** console **errors AND warnings AND pageerrors**
block the run (exit non-zero) unless the message matches an allowlist
entry. Dev-mode framework warnings can carry runtime defects that
production builds strip — the dev-server gate is the only place they
surface, so they are failures, not noise (the Vue warn shapes are the
stack-reference example). The failing report carries the offending
message text. Allowlist entries must be **dated + justified**; no
blanket suppression. The allowlist is project-owned
(`.opencode/smoke-allowlist.json` or `--allowlist`); the skill ships no
default entries.

The harness emits `evidence.json` (schema: references/evidence-schema.md)
with the console log, pageerrors, screenshots (full-page + element clip,
archived for the human handoff), and the `ariaSnapshot()` accessibility
tree — the text evidence the review subagent reads (it cannot see
images).

**Layer mapping (R4):** if the change's teardown path cannot be driven
by the journey harness (e.g. transitions that never complete in a
component harness), pin the mechanism at the nearest callable API as a
structural proxy and cover the full flow at the real-browser journey
layer — both proven red-first (worked example in the stack reference).

**Vision (advisory, default off):** the screenshot is always archived;
`VALIDATING_UI_VISION=1` additionally routes it to the optional advisory
vision pass (`vision-critic-fast` = minimax-m3). Advisory-only, never a
gate — model-routing flags M3's UI-CSS judgment as not yet confirmed —
and never billed by default. The human manual-validation handoff owns
visual sign-off.

### Step 5 — Invoke council-ux on the text evidence

Invoke `council-ux` (subagent_type `council-ux`) with the text evidence
bundle:

- the harness report + exit code and the evidence.json text fields
  (console errors/warnings, pageerrors, journey error, allowlist hits)
- the `aria_snapshot` accessibility tree
- the journey module + the plan ACs / one-line diff summary

Brief: review **correctness** (does the flow behave as the ACs say?),
**appropriateness** (is the interaction right for the user?),
**accessibility** (roles, names, keyboard/close paths in the a11y
tree). Return 3–5 findings, each with: what, where, why, suggested
in-scope fix. Text-only evidence is the contract — council-ux is a
text-only model; do not ask it to judge screenshots.

### Step 6 — Fix findings in scope; bounded loop

Feed the findings back to the implementer. Fixes are in-scope only
(plan's `Files to Modify` + `Included`); a finding that needs out-of-
scope work is recorded as a follow-up, not built. Re-run Step 4 after
each fix round. **Bounded: max 2 fix cycles.** Unresolved residual
findings after the bound are recorded (plan History follow-ups + the
handoff), not silently dropped.

### Step 7 — Return

Return to `implementing-features`: the net verdict (clean / blocked with
the offending messages), the council-ux findings (fixed + residual), the
evidence paths (`.opencode/evidence/<plan-slug>/`), and any follow-ups.
The implementer records residuals in the plan History + handoff, and the
handoff cites the screenshot for the human manual validation.

## When to defer or skip

- **No visible UI** — explicit skip note (Step 2).
- **No dev server / no chromium in the environment** — the run is
  DEFERRED (recorded, not silently skipped); the implement loop still
  proceeds on the suite's green + the explicit deferral note. The
  skill's own self-check (`npm run test` in the eval fixture) and the
  validator are the regression net for the harness itself.
- **Screenshot review** — always human-owned at the manual-validation
  handoff; the optional advisory vision pass (default off) is the only
  in-loop image judgment and it is never a gate.

## References

- [references/evidence-schema.md](references/evidence-schema.md) —
  evidence.json schema, allowlist format + discipline, journey-module
  contract (`run(page)`), harness CLI surface (local-override points).
- [references/stacks/vue-supabase.md](references/stacks/vue-supabase.md)
  — Vue dev-mode warn shapes as runtime defects, the v-for string-ref
  crash class + `stopAllPreviews` worked example, the leave-transition
  teardown trap + layer mapping, project-side override pattern.