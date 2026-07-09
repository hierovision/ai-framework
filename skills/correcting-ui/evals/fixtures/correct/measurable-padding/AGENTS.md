# Project rules — Halcyon (correcting-ui, measurable-padding slice)

## Stack
`vue-supabase` — Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase, Playwright.
CSS system: Vuetify 3 theme tokens + SCSS design variables (`$spacing-*`,
`$radius-*`, `$font-*`). Prefer component props / semantic classes over raw
CSS; reuse an SCSS variable over a magic px.

## The defect being corrected
The `.info-card` reads cramped: its content clips. Captured `.info-card`
computed `padding-top/right/bottom/left` = `8px` (the `$spacing-sm` scale,
which the design intend says should be `$spacing-md` = `16px`). The patient
excerpt describing this is in the prompt — treat it as INTENDED; the matched-
styles map (which rule + line set the value) is the deterministic lookup that
tells you the SOURCE RULE to edit.

## Verification commands (the loop's closure instruments)
- Objective array (no browser): `npm run test` — verifies the candidate's
  source edit adheres to the CSS system AND that a correct re-capture would
  achieve the objective computed delta with the regression guard clean.
- CSS-system adherence (failable): `npm run adhere`.
- before/after compare (failable): `npm run compare`.
- Real-browser re-capture (DEFERRED in this harness): `npm run capture`.

In this harness a real browser is NOT available, so the loop's re-capture is
replaced by a canned re-capture (evidence/after-good-evidence.json) that
represents the deterministic outcome of a CORRECT fix — the verifier proves
that candidate fix closes the objective compare, and (where the scenario
baits it) that a WRONG fix would NOT. Real re-capture is a DEFERRED
validation, documented in evals.json notes — never silently skipped.

## CSS system contract
The single source of truth for Vuetify/SCSS adherence is the skill's
`references/systems/vuetify-scss.md`. A correction must: snap track values to
a token/variable, keep specificity flat (no raised compound selectors), add no
new `!important`, and not pierce with `::v-deep`. If the correct fix needs any
of those, it is larger than a correction — route to designing-architecture.

## Conventions
- No magic px where a `$variable` exists. No `!important` to win the cascade.