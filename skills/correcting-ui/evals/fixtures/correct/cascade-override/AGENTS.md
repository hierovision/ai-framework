# Project rules — Halcyon (correcting-ui, cascade-override slice)

## Stack
`vue-supabase` — Vue 3 + Vuetify 3, SCSS theme tokens. CSS system: Vuetify
3 theme tokens + SCSS variables (`$text-*`, `$spacing-*`.

## The defect being corrected
The `.qty-stepper` text reads washed out. The intuitive reading ("the stepper
text color is wrong") points at the component's OWN rule `.qty-stepper { color`
in src/styles.scss — but that rule is OVERRIDDEN. The matched-styles map
(`color` winner) pins the actual winning declaration to a DIFFERENT selector
`.v-theme--light .qty-stepper` in src/theme.scss (higher specificity — two
class hooks vs one). Editing the component's own rule changes nothing
(computed `color` stays `#6b6b6b`); editing the winner does. This slice baits
the naive-from-screenshot fix and rewards the matched-styles lookup.

## Verification commands
- Objective array (no browser): `npm run test`.
- CSS-system adherence (failable): bundled `check-adherence.js`.
- before/after compare (failable): bundled `compare-evidence.js`.
- Real-browser re-capture (DEFERRED here): `npm run capture`.

## CSS system contract
Single source of truth: the skill's `references/systems/vuetify-scss.md`. The
winning rule lives in the PROJECT theme file (src/theme.scss), not a vendored
sheet — so editing it is in scope. The fix keeps specificity flat (still two
class hooks, no raise), adds no `!important`, and snaps the color to a named
token (`$text-primary`). If the winner were a vendored `node_modules` sheet,
the correct response would be a component prop / token, not editing vendored
CSS — route that to the system reference.

## Conventions
- Target the matched-styles WINNER, never the element's own rule guessed from
  the screenshot. No `!important` to win the cascade. Snap to a token.