# CSS System: Tailwind

Read this when the detected CSS methodology is Tailwind — utility-first
classes composed in markup, a `tailwind.config.*` defining the design tokens
(spacing scale, radii, typography), and a thin component layer that uses
`@apply` sparingly. Detect Tailwind from a `tailwind.config.{js,ts,cjs,mjs}`
file and/or `@tailwind` directives in the stylesheet. Stubs below hold the
real adherence rules; expand them as a new project's Tailwind conventions pin
down.

## The system in one paragraph

Tailwind moves styling to the **composition** of utilities in markup; a
component layer (`@layer components`) collapses repeated utility chains into a
named class via `@apply`. The scale lives in `tailwind.config` as tokens —
`spacing`, `borderRadius`, `fontSize`, `colors` — and a correction snaps to
those tokens (`p-4`, `rounded-lg`, `text-base`) or to a `@apply`-ed component
class. Ad-hoc CSS rules with bespoke class names defeat the utility system:
the fix belongs in markup composition or in the component layer, not bespoke
CSS.

## Adherence rules (a fix must satisfy these)

- **No bespoke class selectors in raw CSS**: a `.css`/`.scss` rule with a
  non-utility class selector (e.g. `.fancy-card { … }`) is ad-hoc CSS that
  bypasses the utility system. Compose utilities in markup, or `@apply` them
  into a component-layer class. `check-adherence.js --system tailwind` flags
  authored class-selector rules.
- **`@apply` sparingly**: use `@apply` to collapse a repeated utility chain
  into a named component class — not to mix bespoke properties into a utility
  context. A `@apply` that pulls 20 utilities is a signal the markup should
  compose them directly.
- **Snap to the config scale**: track values use the Tailwind scale (e.g.
  `border-radius: theme(borderRadius.lg)` / `@apply rounded-lg`), never a
  magic px outside the config. A magic px here is both a weaken of the system
  and a silent scale drift.
- **No new `!important`**: Tailwind's `!` important-variant utilities exist
  for cascade overrides; reach for them at the markup layer deliberately, not
  by editing a rule to force the cascade. (And prefer the `@layer` order
  fix over a `!`.)
- **Specificity flat**: utility classes are single-class; a correction that
  raises specificity (nesting a component class in a parent) reintroduces the
  cascade race utilities avoid.

## When this system

- A `tailwind.config.*` exists, and/or the stylesheet has `@tailwind base |
  components | utilities;` directives.
- Classes in markup are utility-named (`flex gap-4 rounded-lg`), not semantic.

## Not

- A semantic-class methodology (BEM) — that is `bem.md`.
- A component-framework-theme descendant cascade (Vuetify) — `vuetify-scss.md`.

## Adherence quick-reference

| concern | rule | caught by |
|---|---|---|
| bespoke class selectors in CSS | compose utilities / `@apply` component layer | check-adherence — `--system tailwind` |
| magic px outside config | snap to `theme(…)` / the scale | check-adherence — `--tokens` |
| new `!important` | use `!`-utilities deliberately at markup; fix `@layer` order instead | check-adherence (baseline diff) |
| raised specificity | keep flat (one class) | check-adherence — `--target-selector` |