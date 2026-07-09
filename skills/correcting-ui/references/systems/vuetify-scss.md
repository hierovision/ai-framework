# CSS System: Vuetify 3 + SCSS (the pt reality)

Read this when the detected CSS system is Vuetify 3 themed with SCSS design
variables (Vue 3 + Vuetify + `*.scss` with `$tokens`, a `vuetify` theme
config, or `@use 'vuetify/...'` imports). This file is **correct-time** — the
adherence rules a fix must satisfy — and is the system-specific complement to
the stack-neutral matched-styles contract at
[../capturing-ui-evidence/references/evidence-schema.md](../../capturing-ui-evidence/references/evidence-schema.md)
("which rule set it") and the capture-stack note at
[../capturing-ui-evidence/references/stacks/vue-supabase.md](../../capturing-ui-evidence/references/stacks/vue-supabase.md)
(capture-time Vuetify concerns). A correction edits source **adhering** to
this system; it does not fight it.

## Contents

- The system in one paragraph
- Token / variable priority (fixes snap to tokens)
- Specificity discipline (where overrides come from, and how not to fight them)
- Scoping discipline (no gratuitous ::v-deep)
- Naming discipline
- Vendor-source winners (node_modules theme rules)
- Adherence quick-reference

## The system in one paragraph

Vuetify 3 components carry their own classes (`.v-card`, `.v-btn--variant-*`)
and are themed by descendant rules of the shape `.v-theme--light .v-card { … }`
which carry **two class hooks** — higher specificity than a plain one-class
override, so they win the cascade silently. The project layers SCSS design
variables (`$spacing-*`, `$radius-*`, `$font-*`, `$text-*`) on top. The system
prefers **component props and semantic classes** over raw CSS, **named tokens**
over magic numbers, and **flat specificity** over override arms races. A
correction that needs to raise specificity or add `!important` to win is a
signal the change is larger than a correction — route to `designing-architecture`.

## Token / variable priority (fixes snap to tokens)

A track value (padding, margin, border-radius, gap, font-size, line-height,
width/height) snaps in this order:

1. A **design token / theme scale** when present (a named token is self-
   documenting: `$spacing-md` says "the medium spacing" where `16px` says
   nothing). This is always preferred.
2. Else reuse an **existing SCSS variable** already used elsewhere for the
   same concern (DRY — one source of truth per scale).
3. Else **introduce a well-named variable** (`$section-gap-md`) so the next
   reader inherits the scale rather than re-deriving it.

Never a **magic px** where a token exists — a bare `16px` defeats the scale,
drifts from the single source of truth, and is not self-documenting. Never a
raw `!important` to win the cascade (see Specificity discipline). The bundled
`scripts/check-adherence.js` flags a magic px on a track property when the
project declares a token for it; fix by snapping to the token.

## Specificity discipline (where overrides come from, and how not to fight them)

The matched-styles map is the deterministic answer to "why is my padding
ignored": it names the **winner** (the max-precedence declaration under
Cascading-4) and the **overridden** chain with source locations. The classic
Vuetify trap is the `.v-theme--light .<component>` descendant rule winning
over a plainer override because of its two class hooks. The correct response
is NEVER to raise your selector's specificity or add `!important` to out-rank
it. Instead:

- Edit the **winner** if it lives in a project-owned stylesheet (the fix
  targets the rule the matched-styles map named, not the element's own
  lower-specificity rule guessed from the screenshot).
- If the winner lives in a **vendored** sheet (`node_modules/...`,
  `source_url` names it), do NOT edit vendored CSS. Use a **component prop** /
  **semantic class** / a **scoped token** at the component boundary — the
  change belongs in your component, not in the framework. Editing vendored
  CSS is silently lost on the next `npm update`.
- If the only way to make the intended fix stick is to raise specificity or
  add `!important`, that is a signal the change is **larger than a
  correction** — route to `designing-architecture` for a plan rather than
  starting an override arms race the next reader loses.

Keep the edited rule's specificity flat vs the baseline rule for the same
target (no added compound selector). `check-adherence.js` flags a specificity
raise on the `--target-selector`.

## Scoping discipline (no gratuitous ::v-deep)

Prefer a **component prop** or a **scoped class on your own element** over
piercing the Vuetify component boundary. `::v-deep` / `:deep()` reaches into
framework internals that change across Vuetify releases — a `:deep()` fix is
fragile and is a last resort when a prop/semantic-class/slot genuinely cannot
express the intent. If you reach for `:deep()`, state why the prop path
failed; `check-adherence.js` flags any `:deep()` so the choice is auditable.

## Naming discipline

- Target a Vuetify component by its **role / accessible name / `data-testid`**
  at capture time (so the `fragile` flag stays false and the matched-styles
  address is a stable contract). Editing uses the **semantic class** the
  capture resolved, not framework internals.
- When you introduce a class, name it after the **intent** (`.order-row`,
  `.detail-panel`), not the appearance (`.blue-card`) — names that describe
  appearance rot when the theme changes.
- One block family per concern; do not multiply class hooks on a single node
  to win the cascade (that is the specificity anti-pattern above).

## Vendor-source winners (node_modules theme rules)

When `matched_styles.<prop>.winner.source_url` is under `node_modules`, the
tracked change is on YOUR side of the component boundary:

- Prefer a **Vuetify prop** that maps to the property (`density`, `variant`,
  `color`, `rounded`), or a **theme override** in your project's theme config
  (the single source of truth a token-driven project already has), or a
  **scoped rule on your own wrapper** with appropriately-scoped specificity.
- Editing the vendored declaration is never the fix — it is silently lost on
  the next framework update and bypasses the project's theme contract.

## Adherence quick-reference

| concern | rule | caught by |
|---|---|---|
| magic px on a track prop where a token exists | snap to the token | check-adherence — `--tokens` |
| raised specificity on the target rule | keep flat (no added compound selector) | check-adherence — `--target-selector` |
| new `!important` | never; route to design if force is needed | check-adherence (baseline diff) |
| `::v-deep` / `:deep()` | avoid; prefer a prop / scoped class — justify if used | check-adherence (system vuetify-scss) |
| vendored `source_url` winner | do not edit vendored CSS — component prop / theme override | reasoning (the matched-styles map) |

See `scripts/check-adherence.js --help` for the exact flags the quality-gate
step runs.