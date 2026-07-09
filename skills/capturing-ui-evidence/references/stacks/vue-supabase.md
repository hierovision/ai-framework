# Stack: vue-supabase (capture-time concerns)

Read this when the capture pass detects the project stack is `vue-supabase`
(Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase Postgres + Auth + RLS,
Vite + Playwright). This file is **capture-time** — the specifics the harness
needs to drive capture against this stack — and is the complement of the
matched-styles contract at
[../evidence-schema.md](../evidence-schema.md) (stack-neutral). Project
specifics come from the project's rules file (`AGENTS.md` / `.opencode/
agents.md`); this file holds the stack-wide capture concerns.

If the project declares a different stack, do not read this file — read the
matching `references/stacks/<stack>.md` (resolved against this skill's own
directory, not the project's). If none exists, proceed generically and flag
the gap in the handoff.

## Contents

- Dev-server startup (Vite)
- Auth-fixture for capture (app mode)
- Vuetify component-root selectors
- Vuetify specificity overflow (where overrides come from)
- Isolated component harness entry (component mode)
- Where this stack trips a capture pass

## Dev-server startup (Vite)

App-mode capture needs a running dev server. Vite serves on the configured port
(5173 by default for Vuetify scaffolds):

- start the server once per capture session: `npm run dev` (Vite) →
  `http://localhost:5173`. Capture blocks on `waitUntil: 'networkidle'`, so the
  server must be up BEFORE `--target` is passed; a capture against a not-yet-up
  server fails the navigation, it does not silently retry on a timeout.
- HMR reloads mid-capture perturb layout; capture against a stable build, not
  during an editing session. (The freeze injected by the harness freezes
  *animation*, not HMR.)
- For the Objective closure the harness does not start Vite itself; the caller
  starts it (or runs component mode against a static harness instead). Capture
  reports the artifact + inventory; it does not own process lifecycle.

## Auth-fixture for capture (app mode)

Supabase auth is a JWT in localStorage. The capture **auth fixture** mirrors
the e2e pattern exactly (it is the same seam, read for capture rather than
driven as a journey):

- `--auth-fixture <p.mjs>` points at a module that default-exports
  `async function setup(context)`. It seeds the Supabase token via
  `context.addInitScript` so the captured route renders an authenticated state
  — NOT by replaying the login UI. Replaying login before capture couples the
  snapshot to the auth flow and produces a post-login transitional frame.
- For routes that need a specific user/role (RLS cases the matched-styles map is
  about to point at), seed the corresponding token; multi-user capture runs
  multiple contexts, not login+logout inside one capture. See the e2e
  reference at
  [../../writing-e2e-tests/references/stacks/vue-supabase.md](../../writing-e2e-tests/references/stacks/vue-supabase.md)
  for the fixture's session-setup detail.

## Vuetify component-root selectors

Vuetify 3 components expose roles and accessible names — use them. Capture
targets resolve by role / accessible name / data-testid in that preference
order; a bare-CSS selector is a last resort and is flagged `fragile: true`
(see [../evidence-schema.md](../evidence-schema.md) → Target-resolution).

- A `v-btn` renders a real `<button>` — `role:button[Submit]` resolves it. A
  `v-card` renders region/`article`-ish semantics with an `aria-label` if you
  give it one; target it as `role:region[Order summary]` or by `data-testid`.
- Prefer adding a `data-testid` to an opaque Vuetify component rather than
  reaching for a `.v-card__title` / `.v-btn--variant-tonal` class. Class names
  are Vuetify implementation details; they change across releases and a
  fragile-target flag in the artifact will tell the fixer the address was
  unstable.
- Where a `getByRole` does not exist (a bare layout `<div>`), adding a
  `data-testid` is the cheap fix; the artifact records the target_kind so
  the next pass (or `correcting-ui`) sees the fragility of what was captured.

## Vuetify specificity overflow (where overrides come from)

A symptom source rule in this stack is very often the Vuetify theme cascade —
the `.v-theme--light .v-card { ... }` descendant rules that theme the
component. That selector has higher specificity (two classes) than a plain
`.v-card` override, so it wins silently and is the classic "why is my padding
ignored" report the matched-styles map exists to answer. The harness emits the
winner AND the overridden chain with source locations; here the override source
is usually a Vuetify-generated SCSS file under `node_modules` — the `source_url`
will say so, and `correcting-ui` routes that to "snap to a token / use a
component prop", not to editing the vendored sheet.

## Isolated component harness entry (component mode)

When the symptom is in a single component, capture it in isolation rather than
in the full app, so the matched-styles map points at the component's own rules,
not surrounding layout. For this stack an isolated entry is a Storybook-style
harness:

- a small HTML file importing the component's compiled styles (or the live
  Vuetify theme) is enough — load it via component mode
  (`--mode component --target ./harness/index.html`); the harness opens it over
  `file://`, no Vite needed.
- for a Vuetify component specifically, mount it under `v-app` + `v-theme`
  in the harness so the theme cascade is present — an isolated capture that
  omits the theme reports a winner the real app would OVERRIDE, so the
  harness must reproduce the cascade it is capturing against.

## Where this stack trips a capture pass

- **Capturing against a not-yet-up Vite server.** Navigation fails; start Vite
  before `--target`, or use component mode against a static harness.
- **Bare `.v-btn--variant-tonal` selectors.** Vuetify class internals;
  target by role/testid so the flag stays false and the fixer trusts the
  address.
- **Replaying login before capture.** Couples the snapshot to auth; seed the
  token via the auth fixture instead.
- **Isolated component harness omitting the Vuetify theme.** The matched-styles
  map reports a winner the real app overrides; mount under `v-app` to
  reproduce the cascade.
- **`waitForTimeout` in a custom capture wrapper.** Forbidden — it is the
  class-4 flake; the harness waits on conditions (`networkidle`,
  `document.fonts.ready`, a layout-stability `waitForFunction`), never a
  fixed interval.