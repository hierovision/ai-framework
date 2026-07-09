---
name: capturing-ui-evidence
description: Captures the current visual state of UI targets into a structured, addressable EVIDENCE ARTIFACT — screenshots (full-page + element-clipped) plus a schema-valid evidence.json of curated computed CSS, bounding boxes, and CDP matched-styles (which rule + line set each property, and what overrode it). Deterministic by construction. Reuses the e2e role/accessible-name/testid selector doctrine; bare-CSS targets are flagged fragile. Targets a dev-server route (auth via a session fixture) or a component harness. Use whenever the user says 'capture the current state of X', 'grab screenshots + computed CSS for the header at mobile+desktop', 'get evidence for the overflowing card', or correcting-ui calls it. Not for diagnosing or fixing CSS (correcting-ui), writing e2e tests (writing-e2e-tests), or visual regression assertions. Produces the artifact + a one-line inventory; does NOT interpret.
---

# Capturing UI Evidence

The capture side of the UI iteration loop — the perception-verified
counterpart to the core loop's "reproduce" step. It makes the visual state
**observable and machine-comparable** by writing a structured, addressable
evidence artifact that `correcting-ui` consumes to map a visual symptom to
the exact source rule. This skill **captures deterministically**; it does
**not** diagnose, interpret, or edit. Division of labor: capture says
*which rule, where*; the fixer says *what to change*; the prompt says
*intended*.

A capture pass is **done** when the evidence artifact exists, is
schema-valid, covers every requested (selector × viewport), screenshots are
written, and the matched-styles map is populated for each selector. The skill
reports the artifact path + a one-line inventory and **STOPs** — it never
judges the evidence.

## The capture pass

Copy this checklist and check off items as you complete them.

```
Capture Progress:
- [ ] 1. Identify the input (target, selectors, viewports)
- [ ] 2. Detect stack & load the matching capture-stack reference
- [ ] 3. Invoke the harness (scripts/capture.mjs) — execute, do not reimplement
- [ ] 4. Objective closure (validate the artifact; defer the real browser)
- [ ] 5. Hand off the artifact + inventory; STOP
```

### Step 1 — Identify the input

Three things define a capture run; pin them before invoking the harness:

- **The target, which selects the mode.** A *real running app* — a dev-server
  URL + a route — is **app mode** (`--mode app --target http://localhost:5173
  --route /dashboard`). An *isolated component* — a Storybook-style harness
  HTML entry — is **component mode** (`--mode component --target
  ./harness/index.html`, loaded over `file://`, no dev server). The invocation
  names which; the harness handles both. If the view needs a session, pass
  `--auth-fixture <p.mjs>` (app mode) — the e2e auth-fixture pattern, not a
  login-UI replay.
- **The selectors.** Resolve by role / accessible name (label) / data-testid
  in that preference order — the `writing-e2e-tests` doctrine, reused. A
  bare-CSS selector (`css:.v-card`, or any unprefixed selector) is a **last
  resort** and is flagged `fragile: true` in the artifact so the fixer knows
  the target address was fragile. Prefer adding a `data-testid` to an opaque
  component over reaching for a class. Multi-target runs comma-separate specs.
  The grammar lives in `scripts/capture.mjs --help`.
- **The viewports.** One or more `WxH` specs (e.g. `375x667,1280x720`).
  Viewport + device scale factor are **pinned** by the harness — a re-capture
  with the same specs yields the same computed values (see below).

### Step 2 — Detect stack & load the matching capture-stack reference

Identify the project stack from the rules file (`AGENTS.md` /
`.opencode/agents.md`). If this skill bundles a matching reference under
`references/stacks/` (resolved against this skill's own directory — not the
project's), read it now and apply its capture concerns. If none exists,
proceed generically and flag the gap in the handoff.

Available stack references:

- vue-supabase → [references/stacks/vue-supabase.md](references/stacks/vue-supabase.md)
  Read when the project is Vue 3 + Pinia + Vuetify 3 + Supabase + Playwright.
  Applies Vite dev-server startup, the auth-fixture session setup for
  capture, Vuetify component-root selectors, the `.v-theme--light` theme
  specificity overflow (where silent overrides come from), and the isolated
  component harness entry (mount under `v-app` so the cascade is reproduced).

### Step 3 — Invoke the harness (execute, do not reimplement)

`scripts/capture.mjs` is the bundled "right tool for the job": a Playwright +
CDP harness that is more reliable than generated code and costs zero context
until its output returns. **Execute** it — do not read it as a reference and
do not reimplement its capture logic in the conversation. Invoke it:

```bash
# app mode — a real running route, auth via the e2e auth-fixture pattern
node <this-skill>/scripts/capture.mjs \
  --mode app --target http://localhost:5173 --route /dashboard \
  --selectors "role:button[Submit],testid:submit-btn" \
  --viewports 375x667,1280x720 --out ./evidence \
  --auth-fixture e2e/fixtures/auth.mjs

# component mode — an isolated component harness over file://
node <this-skill>/scripts/capture.mjs \
  --mode component --target ./harness/index.html \
  --selectors "role:button[Submit]" \
  --viewports 375x667,1280x720 --out ./evidence
```

The harness writes, per run, to `--out`:
- a full-page PNG per viewport and an element-clipped PNG per
  (selector × viewport), with **stable** filenames;
- `evidence.json` — the schema-versioned artifact: per (selector × viewport)
  the **curated** computed-CSS profile (NOT all ~300 longhands — a named,
  documented set; pass `--profile full` only when the curated set misses the
  property under investigation), the bounding box, and the **CDP
  matched-styles map**: for each captured property, which authored selector +
  source URL + line/column set it, and what overrode it. This is the key
  value — it collapses symptom→source mapping into a deterministic lookup so
  the fixer never guesses CSS from prose.

The key value comes from a CDP session (`CSS.getMatchedStylesForNode` +
`CSS.getComputedStyleForNode` + `CSS.getInlineStylesForNode`) the harness
opens; the agent never touches it directly.

**Dependency resolution (do this before invoking).** `capture.mjs` does
`await import('playwright')`, which ESM resolves from the script's own
location. When the skill is installed globally (symlinked into
`~/.config/opencode/skills/`), that location is NOT the project, so a
project-local `playwright` will not be found and the harness exits
without writing an artifact. Ensure `playwright` is resolvable from the
run — the reliable options, in order: (a) run with the project's modules
on the path, `NODE_PATH=<project>/node_modules node .../capture.mjs …`;
(b) if the skill dir is writable, install `playwright` there once; (c)
copy `capture.mjs` into the project and run it from the project root. If
the harness errors with `Cannot find package 'playwright'`, this is the
cause — it is a resolution gap, not a capture failure. When only a cached
chromium (not the pinned build) exists, also set
`CAPTURE_CHROMIUM_EXECUTABLE=<path/to/chrome>` (Step 4).

### Step 4 — Objective closure

A capture pass closes on objective signals, never on "looks captured".

- In a real environment: the harness exits 0 and the artifact exists at
  `--out/evidence.json`. Verify it is schema-valid — the contract is
  [references/evidence-schema.md](references/evidence-schema.md); if a
  schema validator is present in the project, run it on the artifact. The
  matched-styles map must be populated for each selector (every captured
  property has a winner — `null` only for an inherited/initial value).
- Where a real browser is NOT available (eval harness, CI sandbox), a real
  capture cannot run. Closure is then the **objective self-check**: run
  `npm run test` (the bundled structural verifier in the eval fixture) which
  drives `runCapture` against a canned CDP/DOM fake and asserts the emitted
  artifact is schema-valid + curated + matched-styles populated with source
  locations; the structural determinism grep and the schema validator are
  green. Document the real-browser capture as a **deferred** validation
  (per the `writing-e2e-tests` real-browser-deferral precedent) — honest
  deferral, not a silent skip.
- Where a chromium binary IS available even though the `playwright` npm
  package's pinned build is not installed (a cached build, a system Chrome),
  the harness can still run a REAL capture: set
  `CAPTURE_CHROMIUM_EXECUTABLE=<path/to/chrome>` and run `capture.mjs` — it
  launches that binary and the real artifact validates against the SAME
  schema validator. This *realizes* the otherwise-deferred validation rather
  than just documenting it; prefer a realized real run whenever a chromium is
  reachable. (Two such CLI runs with the same input produce a byte-equal
  artifact — the determinism guarantee holds in a real browser, not just the
  fake.)

The artifact path + a one-line inventory (selectors × viewports × profile,
screenshot count) is the report.

### Step 5 — Hand off the artifact + inventory; STOP

Report, concisely: **artifact path**; **inventory** (one line:
entries/screenshots/selectors/viewports/profile); **mode** (app vs component);
**fragile targets flagged** (any `css:` selectors — name them); the
**deferred real-browser validation** status where no browser is available.
Then **STOP**. Do not interpret the evidence, do not propose fixes, do not
edit CSS — that is `correcting-ui`. Do not commit; `capturing-ui-evidence`
produces the artifact, the fixer consumes it.

## Determinism (load-bearing)

The same input MUST yield the same computed values, or the downstream diff is
meaningless. The harness guarantees this by construction:

- animations + transitions are disabled (an injected freeze `<style>` +
  `emulateMedia({ reducedMotion })`) so transient motion never enters the
  snapshot;
- waits on **conditions, never fixed timeouts** — `waitUntil: 'networkidle'`,
  `document.fonts.ready`, and a layout-stability `waitForFunction` poll. A
  `waitForTimeout` in the capture path is the `debugging-test-failures`
  class-4 flake and is forbidden; the structural determinism grep catches a
  regression;
- `deviceScaleFactor: 1` and an explicit viewport are pinned per run.

The determinism knobs are STRUCTURALLY GREP-able in `scripts/capture.mjs` so
the property stays green where Playwright is absent. Determinism is not a
nicety — a nondeterministic capture poisons the downstream `correcting-ui`
diff.

## When not to use this skill

- **Diagnosing or fixing CSS** — that is `correcting-ui`; this skill captures
  the evidence it consumes. Capturing is the loop's "reproduce", not the fix.
- **Writing e2e tests** — that is `writing-e2e-tests`. Capture produces a
  one-shot artifact for diagnosis, not a persistent regression spec; a
  visual-regression assertion in the test suite is a test, not evidence.
- **Inspecting a page manually / one-off debugging** — a quick
  `getComputedStyle` in the devtools is faster, and there is no contract to
  preserve. Capture pays when the fixer will consume the artifact.
- **Rendering a screenshot for a human pass/fail** — capture's artifact is for
  a machine consumer; a vision-critic pass is the `auditing-visual-design`
  / `correcting-ui` concern, downstream of this artifact.

## References

- [references/evidence-schema.md](references/evidence-schema.md) — the
  evidence artifact CONTRACT (single source of truth; `correcting-ui` links
  it). Top-level shape, `capture_meta`, `entries[]`, the curated computed-CSS
  profile (named, documented, with the one-line *why* per group),
  `matched_styles` (winner + overridden + source locations), determinism
  guarantees, target-resolution + the `fragile` flag, schema versioning + drift.
  Read when authoring or validating an artifact, or when `correcting-ui`
  consumes one.
- [references/stacks/vue-supabase.md](references/stacks/vue-supabase.md) —
  capture concerns for the Vue 3 + Vuetify 3 + Supabase + Playwright stack.
  Read at Step 2 when the project's rules file declares stack `vue-supabase`.
- `scripts/capture.mjs` — the deterministic Playwright + CDP harness
  (execute; see `--help` for the selector grammar). Exports `runCapture` +
  `CURATED_PROPERTIES` so the objective self-check can feed it a canned
  CDP/DOM fake without a real browser install.
- The e2e selector + auth-fixture + real-browser-deferral doctrine this skill
  reuses lives in
  [../writing-e2e-tests/SKILL.md](../writing-e2e-tests/SKILL.md) — role/
  accessible-name/testid preference order, condition waits (never
  `waitForTimeout`), the auth-fixture session pattern, and the structural-
  verifier-when-no-browser precedent.