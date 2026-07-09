# Project rules — Halcyon (correcting-ui, adherence-trap slice)

## Stack
`vue-supabase` — Vuetify 3 + SCSS design tokens.

## The defect being corrected
The `.tag` chip should read with a larger corner radius. The captured `.tag`
computed `border-radius` = `$radius-md` (8px); the design intent says
`$radius-lg` (12px). The project's adherence gate (the bundled
`check-adherence.js`, run by `npm run test`) encodes the Vuetify-SCSS system
discipline and REJECTS a fix that weakens it; a fix the gate rejects is not
closure, even if it closes the visual target.

## Verification commands
- Objective array (no browser): `npm run test`.
- CSS-system adherence (failable): bundled `check-adherence.js`.
- before/after compare (failable): bundled `compare-evidence.js`.
- Real-browser re-capture (DEFERRED here): `npm run capture`.

## CSS system contract
Single source of truth: the skill's `references/systems/vuetify-scss.md`.
Snap to a named token; never a magic px; never `!important` to win the
cascade; never raise specificity. A "win" that weakens the system is a
blocker, not closure.

## Conventions
- A correction that needs force (`!important` / raised specificity / magic
  px) is a SIGNAL the change is larger than a correction — route to design.