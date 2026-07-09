# Project rules — Halcyon (correcting-ui, regression-guard slice)

## Stack
`vue-supabase` — Vuetify 3 + SCSS design tokens.

## The defect being corrected
The `.hero` reads cramped (content clips its box). The design intent: bump
`.hero` padding from `$spacing-sm` (8px) to `$spacing-md` (16px). `.hero` and
`.sidebar` are SIBLINGS in a flex row — the correction must move `.hero`'s
padding only; `.sidebar`'s bbox and computed block must stay byte-identical.
A fix that hits the target but shifts `.sidebar` is a REGRESSION, not closure —
the regression guard (every OTHER captured element unchanged) is the UI-loop
analogue of "the full suite is still green."

## Verification commands
- Objective array (no browser): `npm run test`.
- CSS-system adherence (failable): bundled `check-adherence.js`.
- before/after compare (failable): bundled `compare-evidence.js`.
- Real-browser re-capture (DEFERRED here): `npm run capture`.

## CSS system contract
Single source of truth: the skill's `references/systems/vuetify-scss.md`. The
fix snaps to `$spacing-md`, keeps specificity flat, adds no `!important`, and
does NOT touch `.sidebar` or any shared parent that would shift it.

## Conventions
- Closure is target-delta-achieved AND regression-guard-clean together.