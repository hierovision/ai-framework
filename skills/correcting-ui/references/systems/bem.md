# CSS System: BEM

Read this when the detected CSS methodology is BEM — class names shaped
`block`, `block__element`, `block--modifier`, `block__element--modifier`, with
**flat specificity** (single-class selectors, no descendant coupling) and a
block-family convention per concern. Detect BEM from `__` / `--` dunders in
the class names and from any stylelint `plugin/no-descending-specificity` or
`selector-class-pattern` config enforcing the pattern. Stubs below hold the
real adherence rules; expand them as a new project's BEM conventions pin
down.

## The system in one paragraph

BEM is a flat, single-class methodology: each node gets classes that name its
block, its element-within-block, and its modifier state. There is one block
family per concern; elements and modifiers do NOT cascade off descendant
selectors. Flat specificity means every override wins on **source order**, not
on selector weight — so the cascade is predictable and a correction edits the
**declaration at the rule that owns it**, never arms up to out-rank a sibling.

## Adherence rules (a fix must satisfy these)

- **Naming**: every class matches `^[a-z][a-z0-9]*(-[a-z0-9]+)*(__[a-z0-9-]+)?(--[a-z0-9-]+)*$`
  — one block, optional `__element`, optional `--modifier`. A `.card .title`
  descendant or a `.card-title` ad-hoc compound is a violation.
- **Flat specificity**: a rule chains ONE class hook. A descendant selector
  chaining two classes (`.block .block__element`) reintroduces the specificity
  race BEM exists to avoid — use the element/modifier class on the node
  directly. `check-adherence.js --system bem` flags two-class descendant
  selectors.
- **No new `!important`**: BEM's flat specificity means the cascade resolves
  on source order; `!important` is a band-aid for a specificity accident. Fix
  the selector, never force the cascade.
- **No magic px where a token exists**: BEM projects carry a spacing/typography
  scale (CSS custom properties or a preprocessor map); snap track values to
  the scale.
- **Modifiers carry intent, not overrides**: a `--condensed` modifier sets
  the condensed values; do not stack a second class to force `!important`
  over the base.

## When this system

- Class names contain `__` / `--` dunders, and/or a stylelint config enforces
  `selector-class-pattern: ^[a-z]+(__[a-z0-9-]+)?(--[a-z0-9-]+)*$`.
- A single class per node; rules written as `.` + one name, no descendant
  compound selectors.

## Not

- A project using utility classes that compose in markup (Tailwind) — that is
  `tailwind.md`.
- A project theming a component framework with descendant theme rules
  (Vuetify) — that is `vuetify-scss.md`; BEM and Vuetify can coexist, but the
  override discipline lives in the Vuetify file.

## Adherence quick-reference

| concern | rule | caught by |
|---|---|---|
| naming | `block__element--modifier`, one block family | check-adherence — `--system bem` |
| flat specificity | one class per selector; no descendant coupling | check-adherence — two-class flag |
| new `!important` | never | check-adherence (baseline diff) |
| magic px | snap to the scale | check-adherence — `--tokens` |