# Evidence Artifact Schema

The single source of truth for the evidence artifact `capturing-ui-evidence`
writes and `correcting-ui` (and any diff/regression consumer) reads. Capture
LINKS this file; consumers LINK it — the format is never duplicated across
skills. The artifact is VERSIONED (`schema_version`); a consumer that reads
a version it does not understand must stop and surface the drift, not guess.

`capturing-ui-evidence` produces the artifact; it does NOT interpret it. The
contract below is what makes the capture *addressable* by the downstream fixer.

## Contents

- Top-level shape
- `capture_meta` (run metadata)
- `entries[]` (per selector × viewport)
- Curated computed-CSS profile (the named, documented set)
- `matched_styles` (the key value — symptom → source rule)
- Determinism guarantees
- Target-resolution discipline + the `fragile` flag
- Versioning + drift

## Top-level shape

```jsonc
{
  "schema_version": "1.0",            // string; the consumer gates on this
  "capture_meta": { ... },            // run metadata (see below)
  "entries": [ /* per (selector x viewport) */ ]
}
```

A run with `N` selectors and `V` viewports emits exactly `N × V` entries.
Two screenshot files accompany it (written to the same `--out` dir): a
full-page PNG per viewport and an element-clipped PNG per (selector ×
viewport). Filenames are STABLE (run `--name` + viewport + sanitized
selector slug) so a re-capture overwrites comparable files.

## `capture_meta` (run metadata)

| field | type | note |
|---|---|---|
| `mode` | `"app" \| "component"` | which capture mode produced the run |
| `target` | string | app: dev-server URL; component: harness HTML path |
| `route` | string \| null | app mode only; appended to `target` |
| `viewports` | `string[]` | the `WxH` specs, in run order |
| `selectors` | `string[]` | the selector specs, as given |
| `profile` | `"curated" \| "full"` | which computed profile was emitted |
| `name` | string | run name (stable filenames) |
| `auth_fixture_used` | boolean | app mode: was the auth fixture applied |
| `device_scale_factor` | number | pinned (1) — scale perturbs geometry/screenshots |
| `animations_disabled` | boolean | the freeze CSS was injected |
| `capture_clock` | string \| number | metadata only — a CONSUMER MUST EXCLUDE it from diffs |
| `inventory` | string | one-line human inventory (also the skill's report) |

`capture_meta` is for traceability + determinism knobs; the DIFFABLE substance
of the artifact is `entries[]`. `capture_clock` and any abs/filename fields
are explicitly excluded from before/after comparison — only `computed`,
`bbox`, and `matched_styles.winner`/`overridden` values participate in a diff.

## `entries[]` (per selector × viewport)

```jsonc
{
  "selector_spec": "role:button[Submit]",  // canonical spec string
  "target_kind": "role",                   // role | label | testid | text | css
  "fragile": false,                        // true iff a bare-CSS target (last resort)
  "viewport": { "width": 375, "height": 667 },
  "bbox": { "x": 16, "y": 120, "width": 100, "height": 36 },  // viewport coords
  "screenshots": { "full": "...png", "clip": "...png" },     // basenames in --out
  "profile": "curated",                    // which computed profile was emitted
  "computed": { /* property -> value */ },  // curated (or full) computed CSS
  "matched_styles": { /* property -> { winner, overridden } */ }
}
```

`bbox` is the element's client rect in viewport coordinates from
`ElementHandle.boundingBox()` — the geometry a layout critique measures
alignment, spacing, and overflow against (alignment = equal coords; overflow =
child box ⊄ parent box; spacing = computed value == target).

## Curated computed-CSS profile (the named, documented set)

`getComputedStyle`/`CSS.getComputedStyleForNode` emits ~300 longhands; the
curated profile keeps only the groups a visual critique reads, with a
one-line *why* per group. The curated set lives in `scripts/capture.mjs`
(`CURATED_PROPERTIES`) AND in this section — they agree. Default
`profile: "curated"`; pass `--profile full` to emit all ~300 only when the
curated set misses the property under investigation (rare; verbose).

| group | why | representative properties |
|---|---|---|
| box model | geometry the layout critique measures against | width, height, box-sizing, margin-*, padding-*, border-*-width, min/max-* |
| layout (flex/grid) | how the box participates in its container | display, flex-*, justify-content, align-*, gap, grid-*, order |
| positioning | where the box sits / how it stacks | position, top/right/bottom/left, inset, z-index, float, clear |
| typography | text metrics + flow the critique reads for legibility/overflow | font-*, line-height, letter-spacing, text-*, white-space, word-break, overflow-wrap |
| color/background | theme-token usage + contrast | color, background-*, opacity |
| borders | shape + rounding + token adherence | border-*-style/color/width, border-radius + corners |

Authored **shorthands** (`padding`, `margin`, `border`, `gap`, …) are
expanded into their curated longhands so the matched-styles map keys align
with the computed block's longhands. Each expanded longhand decl is marked
`shorthand: "<name>"` so the fixer edits the authored shorthand declaration,
not each longhand. ~80 curated properties; the validator's curated ceiling is
100 (>100 is not a curation, it is a dump).

## `matched_styles` (the key value — symptom → source rule)

For each (curated or full) property in `computed`, `matched_styles[prop]` is:

```jsonc
{
  "winner": {                          // the authored declaration that won the cascade
    "selector": ".card .btn",          // authored selector text; "@inline style attribute" for inline
    "source_url": "styles.css",        // stylesheet source URL; the document URL for inline/<style> blocks
    "line": 8,                         // absolute 0-indexed line in source_url; null for UA / inline / un-located
    "column": 18,                      // absolute column; null when line is null
    "value": "8px",                     // the authored (or expanded-longhand) value as written
    "important": false,
    "origin": "author"                 // author | user | ua
    "shorthand": "padding"             // only present when this decl came from an authored shorthand
  },
  "overridden": [ /* same shape, lower-precedence */ ],
  "inherited_or_initial": false        // only true when winner is null (no authored rule set this on the node)
}
```

This is the load-bearing value of the harness. `correcting-ui` maps a visual
symptom to the **exact source rule** (selector + file + line) instead of
guessing CSS from prose — the division of labor locked in the Phase 3 plan.
The winner is the max-precedence declaration under Cascading-4: tier =
`origin × importance` (author-important > author-normal > user > UA), then
specificity, then source order; inline declarations carry an effective
pseudo-1e9 specificity so they out-rank any author selector without
`!important`, exactly as the spec specifies. Authored shorthand decls are
expanded to longhands before precedence resolution so a longhand `computed`
key always has a candidate winner.

`winner` may be `null` (with `inherited_or_initial: true`) when no rule on
this node — not the UA sheet, not authored — set the property (e.g. an
inherited value from a parent). That is a populated entry, not an absent one:
the consumer sees the property was inspected.

## Determinism guarantees

A capture is a contract: the same input yields the same computed values, or the
downstream diff is meaningless. The harness:

- disables animations + transitions (an injected freeze `<style>` +
  `emulateMedia({ reducedMotion })`) so transient motion never enters the
  snapshot;
- waits on **conditions, never fixed timeouts** — `waitUntil: 'networkidle'`,
  `document.fonts.ready`, and a layout-stability `waitForFunction` poll (two
  consecutive reads of the document snap equal). `waitForTimeout` is forbidden
  in the capture path (it is the `debugging-test-failures` class-4 flake);
- pins `deviceScaleFactor: 1` and an explicit viewport per run.

The determinism knobs are STRUCTURALLY GREP-able in `scripts/capture.mjs`
(see the determinism-curation eval's `check-determinism.js`) so the property
stays green even where Playwright is absent.

## Target-resolution discipline + the `fragile` flag

Targets resolve by role / accessible-name (label) / data-testid in that
preference order — the `writing-e2e-tests` selector doctrine, reused verbatim.
A role selector survives markup refactors and doubles as an accessibility
check; a CSS class breaks on the next UI change and bypasses that signal. The
selector-spec grammar (see `scripts/capture.mjs` help) is:

- `role:<role>[<accessible-name>]` — by role + accessible name
- `label:<text>` — by accessible name (label)
- `testid:<id>` — by `data-testid`
- `text:<text>` — by visible text
- `css:<selector>` — **bare CSS, a last resort**

A `css:` target (or an unprefixed selector) sets `target_kind: "css"` AND
`fragile: true` in the entry. The fragility flag is load-bearing:
`correcting-ui` must know the target address was fragile so it does not trust
the captured source rule as a stable contract across refactors.

## Versioning + drift

`schema_version` is a string `"MAJOR.MINOR"`. A breaking change to the shape
(`entries[]` fields, `matched_styles` shape, the profile contract) bumps
MAJOR. An additive change (a new optional field) bumps MINOR. A consumer
that reads a version outside its supported range must STOP and surface the
drift rather than silently misparse — the artifact is a contract.