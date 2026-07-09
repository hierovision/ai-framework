---
name: correcting-ui
description: Diagnose and fix a CSS/SCSS defect by triangulating the capturing-ui-evidence artifact — screenshot, computed CSS, the matched-styles source map, and the source — to a root-cause rule, editing adhering to the project's CSS system, then re-capturing to confirm the objective computed/geometry delta plus a regression guard and adherence. Vision is the final perceptual residue only, never the first signal. Use whenever the user says 'fix the overflowing card', 'the padding is wrong here', 'this looks misaligned or cramped or off', or hands off from capturing-ui-evidence — even without saying 'fix'. A scoped correction proceeds without a plan; a full restyle routes to designing-architecture first. Never a magic px or !important override to win the cascade. Not for capturing evidence (capturing-ui-evidence), writing e2e tests, perceptual-only critique with no source fix, or non-CSS debugging.
metadata:
  library: ai-framework
  phase: "3"
  loop: ui
---

# Correcting UI

The diagnose-and-fix side of the UI iteration loop (Phase 3), the perception-
verified counterpart to the core loop's implement + debug stages. The stated
pain this exists to fix: vision models are weak at translating a *text
description* of a CSS problem into the correct *fix*. The architecture boxes
that weakness out — the capture harness's **matched-styles map** says WHICH
authored rule + source line set each property (a deterministic lookup, not a
guess); the **computed CSS + geometry** say WHAT is actually applied; the
user's prompt says INTENDED. **Vision is the LAST signal (perceptual residue
only), never the first.** Division of labor: the screenshot says *what looks
wrong*; matched-styles says *which rule*; the source says *how it's written*;
the prompt says *intended*; the model never guesses CSS from prose.

A correction pass is **done** when (1) the targeted computed/geometry **delta
was achieved** (the intent's measurable target moved to its objective value),
(2) the **regression guard** holds (no OTHER captured element's bbox or
computed block changed), (3) **stylelint-style adherence** passes (no
specificity raise, no new `!important`, no magic px, naming matches the
system), and (4) the perceptual residue is either **adjudicated by the
vision-critic role** or **honestly deferred** where no vision model is
available. "Looks better" alone is never closure.

## Division of labor with the sibling skill

`correcting-ui` is the **consumer** of `capturing-ui-evidence`'s artifact and
the producer of source edits. The artifact contract is a single source of
truth — link it, never duplicate it:
[../capturing-ui-evidence/references/evidence-schema.md](../capturing-ui-evidence/references/evidence-schema.md)
(top-level shape, `capture_meta`, `entries[]`, the curated computed profile,
`matched_styles` winner + overridden + source locations, determinism, the
`fragile` flag, schema versioning + drift). Capture produces the artifact;
this skill consumes it, edits source, re-captures, and compares.

## The correct pass

Copy this checklist and check off items as you complete them.

```
Correct Progress:
- [ ] 1. Resolve target + intent (from the prompt; the plan if one is in play)
- [ ] 2. Detect the CSS system & load the matching system reference
- [ ] 3. Capture the BASELINE (invoke capturing-ui-evidence — execute, do not reimplement)
- [ ] 4. Gate on the artifact; triangulate the FOUR sources to a root-cause rule
- [ ] 5. Edit ADHERING to the system (fixes snap to tokens)
- [ ] 6. Re-capture + compare (objective delta + regression guard)
- [ ] 7. Quality gate (adherence: no specificity raise, no new !important, no magic px)
- [ ] 8. Perceptual acceptance (vision-critic for residue only)
- [ ] 9. Handoff; STOP (no commit unless asked)
```

### Step 1 — Resolve target + intent

Pin two things before touching anything:

- **The target** — which element(s) and viewports the complaint is about.
  Where a `capturing-ui-evidence` artifact is already in hand, the target is
  its `entries[]`; otherwise the prompt names it.
- **The intent** — what the user wants the target to become. Classify it:
  - **measurable** ("make padding 16px", "stop the overflow", "align these
    two", "use the md scale") — closure is the objective delta (Step 6).
  - **perceptual** ("feels cramped", "looks off", "give it room") — decompose
    into measurable proxies (the spacing/density/contrast scale the judgement
    rides on) and close on those; the residue that genuinely has no
    measurable target goes to Step 8.
  - **broad restyle** ("redesign the whole settings page", "modernize this
    view across X, Y, Z") — this is multi-surface visual work, NOT a single
    correction: route to `designing-architecture` (see Implement-class
    boundaries) and
    make zero sprawl edits. A genuine single correction needs no plan
    (trivial-change exemption); a broad overhaul needs one.

Where a plan artifact is in play, reconcile the intent with the plan's
acceptance criteria; where the prompt's request exceeds the plan's scope,
record it as a follow-up (the `implementing-features` posture, reused below).

### Step 2 — Detect the CSS system & load the matching system reference

The CSS methodology is a **plugin dimension**. Detect it from the rules file
(`AGENTS.md` / `.opencode/agents.md`) PLUS config files: a `tailwind.config.*`
→ Tailwind; a Vuetify theme config / `@use 'vuetify/...'` / `*.scss` with
`$tokens` and `.v-theme--*` rules → Vuetify-SCSS; `__`/`--` class dunders +
a `selector-class-pattern` stylelint rule → BEM. Load the matching reference
under `references/systems/` (resolved against this skill's own directory —
not the project's). If undetectable, **ask one question** rather than guessing
the methodology — a fix written against the wrong system is wrong twice.

Available system references:

- vuetify-scss → [references/systems/vuetify-scss.md](references/systems/vuetify-scss.md)
  — Vuetify 3 theme tokens + SCSS `$variables`; prefer component props /
  semantic classes over raw CSS; the `.v-theme--light .x` descendant override
  is where the winner often lives; no `::v-deep` unless unavoidable; vendor-
  source winners route to props, not vendored edits.
- bem → [references/systems/bem.md](references/systems/bem.md) —
  `block__element--modifier` naming + flat specificity (one class per
  selector); the cascade resolves on source order, never on specificity or
  `!important`.
- tailwind → [references/systems/tailwind.md](references/systems/tailwind.md)
  — utilities compose in markup; `@apply` sparingly in a component layer; no
  bespoke class selectors in raw CSS; snap to the `tailwind.config` scale.

If none matches, proceed generically and flag the gap in the handoff (a
missing system reference is a finding, not a silent "I'll improvise").

### Step 3 — Capture the BASELINE — invoke capturing-ui-evidence

The baseline is an evidence artifact, not a screenshot you eyeball. **Execute**
the sibling skill's harness — do NOT reimplement capture, do NOT read its
script as reference, do NOT settle for a `getComputedStyle` in devtools. The
artifact is the addressable input Step 4 triangulates.

Invoke `capturing-ui-evidence` for the target (selectors × viewports), in app
mode (a running dev-server route, auth via the e2e auth-fixture pattern) or
component mode (an isolated harness over `file://`) — the sibling skill
selects based on the target the invocation names. See
[../capturing-ui-evidence/SKILL.md](../capturing-ui-evidence/SKILL.md) for the
invocation and `scripts/capture.mjs --help` for the selector grammar. The
baseline captures: per (selector × viewport) the curated computed CSS, the
bounding box, and the CDP `matched_styles` map (winner + overridden + source
locations).

**Dependency resolution (do this before invoking).** The capture harness does
`await import('playwright')`, ESM-resolved from its own (globally-symlinked)
location — a project-local `playwright` may not resolve from there. Ensure it
does (in order): run with `NODE_PATH=<project>/node_modules`; or install
`playwright` in the skill dir; or copy `capture.mjs` into the project. If the
harness errors `Cannot find package 'playwright'`, that is a resolution gap,
not a capture failure. When only a cached/system chromium exists (not the
pinned build), also set `CAPTURE_CHROMIUM_EXECUTABLE=<path/to/chrome>` so the
harness launches that binary.

**If capture cannot run at all (no browser reachable and no cached chromium):**
the loop degrades to **source + matched-styles reasoning**: read the captured
artifact if a prior pass left one, read the source the matched-styles map
names, reason the delta from the declaration, and edit at the root cause. The
visual re-verification (Step 6's re-capture, Step 8's vision) is then a
**documented deferral** (per the `writing-e2e-tests` real-browser-deferral
precedent) — honest, not silent. Where a cached chromium IS reachable, realize
the otherwise-deferred real capture via `CAPTURE_CHROMIUM_EXECUTABLE`; prefer a
realized real run whenever a chromium is reachable.

### Step 4 — Gate on the artifact; triangulate the FOUR sources

**Gate on schema before consuming.** Read `schema_version` (string `"MAJOR.MINOR"`).
A version this skill does not understand is **drift** — STOP and surface it;
never misparse the artifact (the contract: see
[../capturing-ui-evidence/references/evidence-schema.md](../capturing-ui-evidence/references/evidence-schema.md)
→ Versioning + drift). Stable pins: `capture_clock` and abs/filename fields
are EXCLUDED from any before/after diff — only `computed`, `bbox`, and
`matched_styles.winner`/`overridden` participate.

**Triangulate the four sources** to a root-cause **hypothesis** that names a
SOURCE RULE (selector + file + line), not a CSS-from-prose guess — the
debugging skill's hypothesis discipline (an explicit, falsifiable hypothesis
naming location + mechanism), applied to the cascade:

1. **The screenshot** — *what looks wrong* (the symptom). Vision reads this
   last, for the residue; it never picks the rule.
2. **The computed CSS** — *what is actually applied* (the measured value at
   the symptom element).
3. **The matched-styles map** — *which authored rule + source line set it*
   (the deterministic lookup). For the property under complaint, read
   `matched_styles.<prop>.winner` (selector + `source_url` + line) AND the
   `overridden` chain. **This is the load-bearing signal.** If the symptom
   element's property has a winner from a **DIFFERENT selector** than the
   obvious own rule (an override up the cascade — the classic Vuetify
   `.v-theme--light .x` descendant), the **fix target is that winner**, not
   the element's own rule guessed from the screenshot. This is the
   discriminating move the map exists for; a naive fix at the overridden rule
   leaves the computed value unchanged.
4. **The source** — *how the winning rule is written* (open `source_url:line`
   and read the declaration in context; confirm the shorthand vs longhand the
   `shorthand:` marker names so you edit the authored shorthand, not each
   expanded longhand).

State the hypothesis in the transcript: "`<prop>` at `<selector>`
(`<file>:<line>`) reads `<value>` because <mechanism>; the intended is
`<target>`; the fix is to edit `<that rule>` to `<that value/token>`." If the
winner is from a **vendored** sheet (`node_modules`) or a UA/inline origin,
the fix is NOT to edit that rule — route to a component prop / theme override /
scoped class (see the system reference). If reasoning from the four sources
cannot pin a source rule, STOP and hand back rather than guessing — the map
existing to remove guessing is the whole point.

### Step 5 — Edit ADHERING to the system (fixes snap to tokens)

Edit the source rule Step 4 named. The edit adheres to the detected system
(Step 2 reference) and the **token priority**: a track value (padding, margin,
border-radius, gap, font-size, line-height, width/height) snaps in this order:

1. a **design token / theme scale** when present (named → self-documenting);
2. else reuse an **existing SCSS variable** for the same concern (DRY);
3. else introduce a **well-named variable** so the next reader inherits the
   scale.

NEVER a magic px where a token exists. NEVER a raw `!important` to win the
cascade. NEVER a raised specificity on the target rule. If the **correct**
fix requires raising specificity or fighting the system, that is the signal
the change is **larger than a correction** — route to `designing-architecture`
(Implement-class boundaries). Scope the diff to the fix target only; do not
"while I'm here" restyle a sibling (it will trip the regression guard at
Step 6 and is out-of-scope sprawl).

### Step 6 — Re-capture + compare (objective delta + regression guard)

Re-invoke `capturing-ui-evidence` over the SAME (selectors × viewports) so
the before/after are comparable (deterministic by construction — same input
yields the same computed values; if the two artifacts differ only in
`capture_clock`/filenames, they're structurally equal). Then run the bundled
compare on the two artifacts (execute, do not reimplement):

```bash
node <this-skill>/scripts/compare-evidence.js <before.json> <after.json> \
    --target <selector_spec> --expect <prop>=<value> [--expect …] \
    [--guard-exclude <selector_spec>]
```

It exits 0 only when BOTH closure conditions hold:

- **Target delta achieved** — each `--expect <prop>=<value>` is the after's
  computed value AND differs from the before (a hold = a no-op, not a fix).
- **Regression guard clean** — every entry NOT excluded (default: the target
  itself) has byte-equal `bbox` + `computed` before→after. A fix that hits the
  target but shifts a sibling is **NOT done** — the guard is the UI-loop
  analogue of "the full suite is still green" (the debugging skill's
  regression-guard posture, applied to layout).

The compare gates on `schema_version` and STOPS on drift. Where the intent is
measurable (alignment = equal coords; overflow = child bbox ⊆ parent bbox;
spacing = computed value == target; color/contrast = computed value / WCAG
ratio), **closure is the objective delta** — never "looks better." If the
compare is RED, return to Step 4/5 — do not iterate the screenshot. If the
real re-capture cannot run (no browser), run the objective self-check the
project's fixture provides (the canned-re-capture compare) and document the
real re-capture as DEFERRED.

### Step 7 — Quality gate (adherence)

Run the bundled adherence checker on the edited source against its pristine
baseline (execute, do not reimplement):

```bash
node <this-skill>/scripts/check-adherence.js <candidate> --baseline <b> \
    --system <vuetify-scss|bem|tailwind> --tokens <tokens.json> \
    [--target-selector <sel>]
```

It is **FAILABLE** — exits non-zero when the fix weakened the CSS system: a
magic px on a track prop where a token exists, a specificity raise on the
target rule, a new `!important`, or a naming violation for the detected
system. This is the **CSS-system cardinal rule** — the analogue of the
debugging skill's "never green by weakening the net": a "win" achieved by
raising specificity, adding `!important`, or a magic-px override that defeats
the system is a **blocker**, not closure. Fix the source; never weaken the
gate to pass it (an explicit user order to weaken requires a dated record,
mirroring the debugging cardinal rule). Where the project has a real
stylelint config, also run it; the bundled checker covers the
correcting-ui-specific discipline stylelint does not (token snapping, vendored
edit detection).

### Step 8 — Perceptual acceptance (vision-critic for residue only)

Only the genuinely **perceptual residue** — the part of the intent with no
single measurable target, after the measurable proxies closed at Step 6 —
goes to a vision model. Per the repo-wide tiered strategy (Decision 4),
reference the ROLES, never model IDs (see repo-root
`reference/model-routing.md`): `vision-critic-fast` per iteration, `vision-
critic-final` for sign-off. Feed the critic the before/after screenshots +
the intent + the objective deltas already closed; ask it to adjudicate ONLY
the residue, never to re-derive the fix (it is the weak signal). 

- Where a vision model IS available: integrate its verdict; closure requires
  the residue accepted (or a follow-up for a targeted proxy the critic flags).
- Where NO vision model is available: **defer honestly** — record the residue
  and the deferral (a dated note) and surface the manual (human-eye)
  validation step in the handoff. A documented deferral is honest; a silent
  self-sign-off is not.

Never close on "looks better" alone. A measurable intent closed on the
measurable; a perceptual intent's measurable proxies closed objectively and
its residue to the critic or deferred.

### Step 9 — Handoff; STOP

Report, concisely: **what changed** (files + the exact rules, citing the
matched-styles winners edited); **the objective evidence** (before/after
computed + geometry deltas, regression-guard clean, adherence green +
stylelint green); **the vision verdict or its deferral**; **manual-validation
steps** for whatever needs human eyes (the perceptual residue, or any manual
closure); **follow-ups** (out-of-scope urges recorded, not done). Then **STOP**
and wait. Do NOT `git add`/commit/push/merge/PR unless the user asks; do not
move to the next roadmap item; do not run `reviewing-code` on yourself (the
quality gate folded its CSS review in at Step 7). The handoff is the gate; the
user decides what comes next.

## Objective-first closure (locked — Phase 3 Decision 4)

Where the intent is measurable, closure is the objective delta, computed from
the two artifacts — vision never substitutes for a measurable:

- **alignment** — equal coords (the target's x/y/edges match the reference).
- **overflow** — the overflowing child's `bbox` ⊆ parent `bbox` (no clip).
- **spacing** — the computed value == the target (a spacing scale step).
- **color / contrast** — the computed value / the WCAG ratio.
- **regression guard** — every OTHER captured element's `bbox` + `computed`
  byte-identical before→after (the guard is a closure condition in its own
  right, not a nicety).

Vision adjudicates only the perceptual residue and gives final sign-off
(Decision 4); it is never the first signal and never the only signal.

## Fixes snap to tokens (hybrid — locked Phase 3 Decision 5)

Honor a design token / theme scale when present (named = self-documenting);
else reuse an existing SCSS variable; else introduce a well-named one — DRY
and self-documenting by construction. Never a magic px; never a raw
`!important` override to win the cascade. If the correct fix requires raising
specificity or fighting the system, route to design (see below).

## The CSS-system cardinal rule

Never achieve a visual target by weakening the CSS system. These are all the
same move — making the closure signal lie, mirroring the debugging skill's
"never green by weakening the net":

- a **magic px** where a token exists (defeats the scale, not
  self-documenting);
- a **new `!important`** to out-rank the cascade winner (a force-win);
- a **raised specificity** on the target rule (an override arms race the next
  reader loses);
- a **vendored-sheet edit** (`node_modules`) silently lost on the next update;
- editing the **overridden** lower-specificity rule and reporting the unchanged
  computed value as "fixed."

If the user **explicitly orders** a weakening ("just `!important` it, demo in
an hour"), comply ONLY with an **explicit dated record** (the fix, why, what
restoring it takes) — mirroring the debugging cardinal rule's override path.
A weakened system with a record is a debt; without one it is a trap. If force
is genuinely the only way, that is the larger-than-a-correction signal —
route to design.

## Implement-class boundaries (scope discipline)

This skill is an **implement-class** skill (it edits source), reusing the
`implementing-features` posture and the `debugging-test-failures` honest-stops:

- A **scoped correction** proceeds — a single source rule (or a small coherent
  set) targeting one measurable defect. No plan is needed (trivial-change
  exemption); the matched-styles map IS the scoped contract.
- A **broad visual restyle** ("redesign the whole view across X, Y, Z") is
  multi-surface design work — route to `designing-architecture` first and make
  ZERO sprawl edits. Record the request as a follow-up; do not silently
  restyle.
- **Out-of-scope urges** ("while you're here, also restyle the nav") are
  recorded as follow-ups, not done — the diff must map one-to-one to the
  correction cited. Cite the matched-styles winner you edited; an un-cited
  edit is sprawl.
- **Honest stops**: if N reasonable fix attempts do not converge, STOP and
  report (do not thrash the cascade — the debugging skill's non-convergence
  posture); if the four-source triangulation reveals the defect is a plan/
  design contradiction (the matched-styles winner is the wrong rule to own
  this concern), STOP and route to design — same contract-breaking posture as
  the implementer.

## When not to use this skill

- **Capturing evidence** — that is `capturing-ui-evidence`; this skill
  consumes its artifact. Capturing is the loop's "reproduce"; this is the fix.
  Reuse the sibling skill at Steps 3 and 6 (execute its harness, do not
  reimplement).
- **Writing e2e tests** — `writing-e2e-tests`. A visual-regression assertion in
  the test suite is a test, not an evidence artifact or a fix.
- **Perceptual-only critique with no source fix** — pure "does this look
  right?" with no CSS to correct is the deferred `auditing-visual-design`
  concern, not this skill (this skill edits source).
- **Non-CSS debugging** — a failing test, a store/DB bug, an infra outage is
  the core loop (`debugging-test-failures`); this skill corrects CSS/SCSS.
- **A bordering redesign** — see Implement-class boundaries; route to
  `designing-architecture`.
- **Infrastructure / asset edits** — this skill edits CSS/SCSS (and the
  component props that drive them). Images, copy, data shape are not its
  surface.

## References

- [references/systems/vuetify-scss.md](references/systems/vuetify-scss.md) —
  Vuetify 3 + SCSS adherence (the pt reality): token priority, the
  `.v-theme--light .x` descendant override, scoping (no gratuitous
  `::v-deep`), naming, vendor-source winners routing to props. Read at Step 2
  when the system is Vuetify-SCSS.
- [references/systems/bem.md](references/systems/bem.md) — BEM adherence:
  `block__element--modifier` naming + flat specificity (one class per
  selector; the cascade resolves on source order). Read at Step 2 when class
  names carry `__`/`--` dunders.
- [references/systems/tailwind.md](references/systems/tailwind.md) — Tailwind
  adherence: utilities compose in markup, `@apply` sparingly in a component
  layer, no bespoke class selectors in raw CSS, snap to the `tailwind.config`
  scale. Read at Step 2 when a `tailwind.config.*` exists.
- `scripts/compare-evidence.js` — the closure instrument (execute): target
  delta + regression guard on two evidence artifacts; gates on schema_version.
- `scripts/check-adherence.js` — the quality gate (execute, FAILABLE): magic
  px / specificity raise / new `!important` / naming rejection for a detected
  system.
- The artifact contract is defined upstream in
  [../capturing-ui-evidence/references/evidence-schema.md](../capturing-ui-evidence/references/evidence-schema.md)
  — `schema_version`, `entries[]`, `matched_styles` (winner + overridden +
  source locations), the `fragile` flag, determinism, versioning + drift. This
  skill LINKS it; the format is never duplicated.
- The capture harness this skill invokes lives in the sibling:
  [../capturing-ui-evidence/SKILL.md](../capturing-ui-evidence/SKILL.md) +
  `scripts/capture.mjs` (the deterministic Playwright + CDP harness; the
  matched-styles map is its key value).
- The scope discipline, deviation protocol, and honest-stops come from
  [../implementing-features/SKILL.md](../implementing-features/SKILL.md); the
  hypothesis → discriminating-experiment loop and the cardinal rule ("never
  green by weakening the net") come from
  [../debugging-test-failures/SKILL.md](../debugging-test-failures/SKILL.md).
- The vision-critic tiering (`vision-critic-fast` per iteration,
  `vision-critic-final` for sign-off) and the roles-not-model-IDs rule live in
  repo-root [../../reference/model-routing.md](../../reference/model-routing.md).