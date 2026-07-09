# Project rules — Halcyon (correcting-ui, route-to-design slice)

## Stack
`vue-supabase` — Vuetify 3 + SCSS design tokens.

## The request being handled
The user asks to "redesign the whole hero section — make it modern" across the
card, the illustration block, the meta row, and the action bar. This is NOT a
single correction; it is a broad, multi-surface visual overhaul. The
correcting-ui skill is implement-class with a trivial-change exemption for a
genuine single correction — a multi-surface restyle needs a plan first. The
right move is to route to `designing-architecture` and make ZERO sprawl edits.

## Verification commands
- Objective array (no browser): `npm run test`.
- Real-browser re-capture (DEFERRED here): `npm run capture`.

## What "done" looks like here
NOT a green compare — the source is UNCHANGED by the correct response. The
skill recognizes the request exceeds a correction's scope, cites the boundary
(no plan needed for a genuine single correction; a broad visual overhaul needs
one), and routes to `designing-architecture`. No edits. Write the route
handoff as one line to `route-to-design.txt` (the project's closure artifact
for a route-to-design decision); the verifier checks source-unchanged AND the
marker. A restyle of `src/styles.scss` fails (out of scope).

## Conventions
- A scoped correction proceeds; a "redesign the whole view" routes to design.