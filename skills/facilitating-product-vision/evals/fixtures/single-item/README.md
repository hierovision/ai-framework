# Phase Colors — feature brief

A standalone item brief. Used for evals that ask to design a
single named feature (the `route-plan-single-item` eval routes this
to designing-architecture).

## What the user wants

Design and plan an implementation of **phase colors on lesson
cards**. Cosmetic; teacher-only.

## Acceptance sketch (from the wishlist)

- Lesson cards render with a color that maps to the lesson phase
  (intro / practice / exit).
- The mapping is configurable per district (some districts already
  use a 4-color scheme; do not break them).
- No accessibility regression — color is the SECONDARY signal, not
  the only one. Shape or icon must carry the phase for color-blind
  teachers.

## Known constraints

- Frontend is React + Tailwind; the color tokens are CSS custom
  properties keyed off a `data-phase` attribute.
- District theme settings are loaded from the `district` row.

## Out of scope

- Do NOT plan the differentiation-by-reading-level slice here.
- Do NOT plan the teacher dashboard v2 here.

## Scope reminder

This is a single-item brief. The user wants ONE implementation
plan, not a roadmap pass.