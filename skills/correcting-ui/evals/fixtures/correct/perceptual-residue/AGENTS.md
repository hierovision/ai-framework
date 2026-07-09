# Project rules — Halcyon (correcting-ui, perceptual-residue slice)

## Stack
`vue-supabase` — Vuetify 3 + SCSS design tokens.

## The defect being corrected
The `.summary-list` "feels cramped" — a perceptual complaint with NO single
measurable target. The skill extracts measurable proxies (the spacing scale:
`gap`, `padding`, `line-height` — the density knobs a "cramped" judgement
rides on), applies a within-system density easing (snap `gap` and `padding`
up one scale step to `$spacing-md`, `line-height` to the body-token ratio),
and sends the genuinely perceptual RESIDUE ("does it now breathe?") to the
`vision-critic-fast` role — DEFERRED honestly where no vision model is
available. Closure on the measurable proxies is objective; the residue is
not self-certified.

## Verification commands
- Objective array (no browser): `npm run test`.
- CSS-system adherence (failable): bundled `check-adherence.js`.
- before/after compare (failable): bundled `compare-evidence.js`.
- vision-critic pass (DEFERRED here — no vision model in harness).
- Real-browser re-capture (DEFERRED here): `npm run capture`.

## CSS system contract
Single source of truth: the skill's `references/systems/vuetify-scss.md`.
Density proxies snap to tokens (`$spacing-md`, the body font/line-height
ratio); no magic px; no `!important`; flat specificity.

## Conventions
- A perceptual intent is decomposed into measurable proxies the loop closes
  on; the residue goes to the vision-critic role, never to self-sign-off.
- Record the residue handoff as one line to `vision-residue.txt` naming the
  `vision-critic-fast` role (role, not model ID) and the DEFERRED status where
  no vision model is available — the verifier reads this to confirm the
  residue was not silently self-signed-off.