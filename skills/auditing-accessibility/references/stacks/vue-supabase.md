# Stack: vue-supabase (audit-time concerns)

Read this when the audit pass detects the project stack is `vue-supabase`
(Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase Postgres + Auth + RLS,
Vite + Playwright). This file is **audit-time** — the specifics the harness +
the auditor need to interpret a11y findings against this stack. Project
specifics come from the project's rules file (`AGENTS.md` /
`.opencode/agents.md`); this file holds the stack-wide audit concerns.

If the project declares a different stack, do not read this file — read the
matching `references/stacks/<stack>.md` (resolved against this skill's own
directory, not the project's). If none exists, proceed generically and flag the
gap in the report's `automation_ceiling_note`.

## Contents

- Dev-server startup (Vite) + auth-fixture (app mode)
- Vuetify built-in a11y + where it breaks
- Accessible-name patterns for v-btn / v-text-field
- Theme-contrast-token pitfalls
- Route-level focus management in the SPA
- The beyond-axe checks this stack especially needs

## Dev-server startup (Vite) + auth-fixture (app mode)

App-mode audit needs a running dev server. Vite serves on 5173 by default:

- start the server once per audit session: `npm run dev` →
  `http://localhost:5173`. The harness blocks on `waitUntil: 'networkidle'`,
  so the server must be up BEFORE `--target` is passed. Do NOT audit during an
  HMR editing session; audit against a stable build.
- `--auth-fixture <p.mjs>` points at a module that default-exports
  `async function setup(context)` and seeds the Supabase JWT via
  `context.addInitScript` — NOT by replaying the login UI. Replaying login
  couples the audit frame to the auth flow and shows a post-login transitional
  state. For routes that gate on a user/role (RLS cases), seed the matching
  token. See the e2e pattern at
  [../../writing-e2e-tests/references/stacks/vue-supabase.md](../../writing-e2e-tests/references/stacks/vue-supabase.md).

## Vuetify built-in a11y + where it breaks

Vuetify 3 components ship built-in a11y — real roles, `aria-*`, focus
management — so most axe flags on raw HTML `<button>`/`<input>` (button-name,
label) should NOT fire when components are used correctly. Where they DO fire,
the defect is almost always a misused prop or a custom override, not Vuetify:

- `v-btn` renders a real `<button>` with an accessible name from its slot
  text. An **icon-only** `v-btn` (`<v-btn icon="mdi-close">`) has NO accessible
  name unless you add `aria-label`. axe flags this as `button-name`; the fix is
  the `aria-label` prop — route to `implementing-features`.
- `v-text-field` wires `<label for>` automatically FROM its `label` prop.
  A field with an empty / omitted `label` prop is an unlabeled input
  (`label` rule) — add the prop, not a hand-written `<label>`. A single field
  with TWO labels attached is the `form-field-multiple-labels` rule.
- `v-dialog` / `v-menu` manage focus + `aria-modal`. A focus TRAP that fires
  for real (focus stuck, not returned) is the beyond-axe keyboard-trap check —
  axe may flag `incomplete`; the auditor surfaces it in
  `needs_manual_verification`.

## Accessible-name patterns for v-btn / v-text-field

- `v-btn` → name from slot text; icon-only → `aria-label="…"`. A bare
  `<v-btn><v-icon>…</v-icon></v-btn>` with no text/aria-label is the canonical
  `button-name` finding on this stack.
- `v-text-field` → `label="…"`. The error state (`:error-messages` /
  `:rules`) must ALSO be associated (`error-messages` renders aria-describedby
  automatically WHEN a messages slot/error is set); a missing
  `error-messages` on a failed submission is the beyond-axe form-error-
  association check (SC 3.3.1 / 3.3.3), surfaced in the manual checklist.
- `data-testid` stays THE stable address; axe's CSS target chain is
  volatile against Vuetify class internals (`.v-btn--variant-tonal`), so where
  the auditor must reference a node it prefers the `accessible_name` /
  `selector_spec` over the bare class.

## Theme-contrast-token pitfalls

Low-contrast findings (`color-contrast`) on this stack are usually a theme
TOKEN chosen too close to its neighbor, not hand-written CSS. Two common
shapes:

- A `v-btn` variant (`tonal`/`text`/`plain`) uses theme `surface`/`on-surface`
  pairs; a custom `color` prop with insufficient contrast against the variant
  background fails SC 1.4.3. The `source_location` (real-browser CDP) records
  the computed colors so the fix snaps to a theme token, not a magic px.
- Text over a `v-card` themed background where the custom surface token is too
  light. Route to `correcting-ui` (a contrast/spacing fix) — and
  `correcting-ui` snaps the token, exactly its discipline.

## Route-level focus management in the SPA

A Vuetify SPA route change does NOT move focus by default. axe will not flag
this (it is a runtime behaviour), but it is the beyond-axe **focus order** +
**live-region** checks. On route change the app should move focus to the new
page's `<h1>` or a skip target and announce the change — absence is a manual
finding, surfaced in the per-route `needs_manual_verification` / the static
`manual_checklist`.

## The beyond-axe checks this stack especially needs

- **Keyboard trap** in `v-dialog`/`v-menu`/`v-bottom-sheet` — verify Tab
  cycles inside and `Esc` returns focus; a Vuetify focus-trap that does not
  restore focus is a real finding axe may mark `incomplete`.
- **Focus-visible** on `v-btn` — Vuetify ships a focus ring, but a custom
  `:focus { outline: none }` override removes it; verify across viewports.
- **Live-region semantics** — `v-snackbar` (toast) and `v-alert` should be
  announced; a snackbar without `role`/`aria-live` is the SC 4.1.3 finding.
- **Reduced-motion** — Vuetify transitions (`<v-slide-x-transition>`) do not
  respect `prefers-reduced-motion` by default; verify motion stops.