---
name: writing-unit-tests
description: Author unit tests for isolated logic — table-driven cases plus edge cases (empty/boundary/error) from the AC's observable behaviour, mocking true externals, never the behaviour under test. Use whenever the user says 'write unit tests for X', 'cover the plan's criteria', 'we have no tests for the store', or surfaces a pure-function/Pinia-store/composable/utility gap — even without saying 'unit'. Proven to fail — red-first (natural failure, not a harness defect) pre-implementation or break->restore->green post-implementation — and maps to an AC when a plan is in play. Routes wrong-layer to siblings — a store+client/DB+policy seam -> writing-integration-tests; a user journey via the real UI -> writing-e2e-tests. Not for diagnosing failing tests (debugging-test-failures), implementing features (implementing-features), or authoring plans (designing-architecture).
---

# Writing Unit Tests

The verify stage's authoring side for the **unit layer**: turn acceptance
criteria (or untested isolated behaviour) into table-driven unit tests
that assert observable behaviour, each proven to fail when that behaviour
breaks. A pass is **done** when the new tests are green on the real
module, red on a broken variant, the full suite is green, no existing
test was weakened, and the handoff carries the AC → test mapping plus
the meaningfulness proof evidence. **In red-first mode** (called
pre-implementation) the suite is intentionally red — the behaviour does
not exist yet — so the pass closes on "authored, proven red for the
right reason, mode recorded", not on a green suite; green is the caller's
downstream job (`implementing-features` Step 7), not this pass's closure.

This skill is the consumer of `designing-architecture`'s acceptance
criteria — see
[../designing-architecture/references/plan-format.md](../designing-architecture/references/plan-format.md)
for the AC contract (link it, never duplicate it). It is the sibling of
`writing-integration-tests` (seams) and `writing-e2e-tests` (user
journeys); the right-layer check (Step 2) routes between the three.

## The authoring pass

Copy this checklist and check off items as you complete them.

```
Unit-test Progress:
- [ ] 1. Identify the input (plan ACs, or untested behaviour)
- [ ] 2. Right-layer check (route wrong-layer requests to a sibling)
- [ ] 3. Detect stack & load the matching stack reference
- [ ] 4. Map ACs to test cases (AC -> test, before writing)
- [ ] 5. Write the tests (table-driven, edge cases from the observable)
- [ ] 6. Meaningfulness proof (mode-branched: red-first natural failure, or break -> red -> restore -> green)
- [ ] 7. Determinism + additive-to-the-net check
- [ ] 8. Run the full suite green; handoff; STOP
```

### Step 1 — Identify the input

Two entry shapes:

- **A plan artifact is in play** — read it first (frontmatter status,
  then `## Acceptance Criteria`). The ACs are the input; each criterion's
  observable behaviour + verifier names a unit test (or notes that the
  verifier lives at a higher layer — see Step 2). Do not invent tests for
  behaviour outside the plan's `Included` scope; out-of-scope behaviour
  is a follow-up, the `implementing-features` posture.
- **No plan — untested behaviour** — the input is the module under test.
  Read it and derive the observable behaviours it should guarantee
  (including edge cases). If the behaviour is multi-file or
  schema-touching and has no plan, suggest `designing-architecture`
  rather than reverse-engineering criteria from code.

### Step 2 — Right-layer check

Before writing, classify the behaviour. Each skill in the trio carries
this same table:

| Behaviour only observable when… | Right layer |
|---|---|
| Logic computable in isolation (pure function, store action with externals faked, composable) | **unit** (this skill) |
| Two collaborators meet at a seam (store + client, DB + policy, outbox + replay) | **integration** → `writing-integration-tests` |
| A user journeys through the real UI to see the outcome | **e2e** → `writing-e2e-tests` |

If the request names a behaviour that only exists at a seam or in the
real UI, **route to the sibling and stop** — do not write a unit test
that mocks the seam into existence. Mocking the collaborators away
defeats the behaviour under test: a "queued mutation replays after
reconnect" check mocked at the unit layer passes against a stub that
enforces nothing — that is a vacant test, not coverage. Name the
sibling, give the one-line reason, and stop. Wrong-layer authoring is
additive-to-the-net in reverse — it adds a test that lies.

### Step 3 — Detect stack & load the matching stack reference

Identify the project stack from the rules file (`AGENTS.md` /
`.opencode/agents.md`). If this skill bundles a matching stack reference
under `references/stacks/` (resolved against this skill's own directory
— not the project's), read it now and apply its unit-testing concerns.
If none exists, proceed generically and flag the gap in the handoff — a
missing stack reference is a finding, not a silent "I'll improvise."

Available stack references:

- vue-supabase → [references/stacks/vue-supabase.md](references/stacks/vue-supabase.md)
  Read when the project is Vue 3 + Pinia + Supabase with Vitest. Applies
  Vitest table-driven conventions, fresh-pinia-per-test isolation,
  composable testing, and the "no DOM unless the unit is a component
  contract" boundary.

### Vue 3 + Pinia setup stores

When the stack is `vue-supabase`, two Pinia access shapes routinely make a
RED test fail for the **wrong reason** — a harness mistake that *looks*
like the feature is absent. Both are the trap named in Step 6's red-first
mode; name them so you fix the test, not chase a phantom feature:

- **Ref unwrapping on the store instance.** In a setup store
  (`defineStore('id', () => { const count = ref(0); return { count } })`),
  returned refs are **unwrapped on the store instance** — read and write
  `store.count`, never `store.count.value` (a primitive has no `.value`,
  so you get `undefined` or a `Cannot create property 'value'` TypeError).
  A composable that returns `storeToRefs(store)` (or the store's own
  returned refs) gives **real refs**, so `timer.count.value` is correct
  *there*. Using the wrong form throws a `.value` error that reads like a
  missing-feature failure but is a wrong-access bug — fix the test's
  access syntax and re-run; do not treat it as the feature's red.
- **Internal helpers not in the store's `return`.** A setup store may
  define helpers used only internally (called from another store method —
  e.g. a `createDefault*` invoked on a "no row" / PGRST116 error branch)
  that are **not** in the `return { ... }`. You cannot call them directly
  from a test (`store.createDefaultPreferences` is `undefined`). Trigger
  them through the **public method** that invokes them (e.g. call
  `loadPreferences` with a mocked "row not found" response), then assert
  the internal behaviour via its observable effect.

### Step 4 — Map ACs to test cases

Before writing assertions, list the AC → test mapping. Each criterion
becomes one or more table-driven rows; each row's input is derived from
the AC's observable, not invented. The mapping is the handoff artifact,
so write it down (in test comments or a mapping block) as you go, not at
the end. No AC is left unverified without an explicit note in the
handoff saying why (e.g. "AC5 is a manual e2e observable — routed to
writing-e2e-tests").

Edge cases (empty input, boundary values, error paths) come from the
AC's observable, not from busywork. "Empty list returns empty array" is
an edge case of a list AC; "formatDuration of 3600 switches to
HH:MM:SS" is a boundary of a formatting AC. A case that exercises no
observable the AC names is padding, not coverage.

### Step 5 — Write the tests (behaviour, not implementation)

Table-driven: one parameterized case per AC row, asserting the
observable output (return value, thrown error, emitted event). The
discipline that keeps tests from becoming `debugging-test-failures`
patients:

- **Assert behaviour, not implementation.** A test that breaks on a
  refactor preserving behaviour is brittle; a test that survives a
  behaviour break is vacant. If asked to "check that it calls a specific
  internal method" / "verify it uses a particular helper internally",
  refuse and explain: the test asserts the observable output, and the
  internal call is verified *through* that output. Spying on internals
  locks the implementation and turns a behaviour-preserving refactor
  red.
- **Mock only true externals, never the behaviour under test.** A clock,
  a network boundary, `localStorage` — faked at the edge is fine.
  Mocking the function or store action under test vacates the assertion
  (the test passes against a stub that enforces nothing). This is
  `debugging-test-failures` class 2 authored into the suite.
- **No DOM unless the unit is a component contract.** A pure function or
  store action is tested in-process; mounting the DOM for logic that
  does not render is an integration test in unit clothing (route it).

### Step 6 — Meaningfulness proof (mandatory; mode-branched)

After writing a test, prove it can fail. The proof **branches on an
explicit caller-stated mode** — the caller names the mode, this skill
does not infer it:

- **Red-first mode (pre-implementation).** A caller —
  `implementing-features` at its Step 5, explicitly saying this is a
  red-first call, or a user authoring ahead of an unwritten module — is
  invoking this skill *before the behaviour exists*. There is nothing to
  break yet, so the post-implementation break/restore does not apply.
  The proof is: **run it; it MUST fail; the natural failure IS the
  red**. Confirm it fails **for the right reason** — read the actual
  failure and confirm it names the *missing behaviour* (a `ReferenceError`
  for a not-yet-written export; an assertion expecting `409` and observing
  `200`). A failure from a broken test **setup** — a typo, a bad import
  unrelated to the feature, a wrong fixture — is red for the **wrong**
  reason: a trap, not a proof. Fix the test's own setup (not the feature,
  which does not exist yet) and re-run until it names the missing
  behaviour. Once it does, the proof obligation is **satisfied** — a
  test born red-first does not need a later break/restore to re-prove its
  authoring; it already went red against real absence. This is not a
  `debugging-test-failures` scenario: no working code ever existed to
  regress from, so word the trap consistently with that skill's class 2
  but do not invoke it.
- **Coverage-expansion / standalone mode (post-implementation).** Code
  already exists. Break the guarded behaviour — swap in a seeded broken
  variant, or make a one-line breakage in the module under test — run
  the test, observe **RED**; restore, observe **GREEN**. A new test that
  has never been seen red proves nothing: it may pass for the wrong
  reason, or vacuously. This is the authoring-side mirror of
  `debugging-test-failures` class 2 ("a test that can no longer fail is
  not a test") — author so that class 2 never applies to your tests.
  The same proof is reused by `implementing-features`' Step 9 coverage
  gate to re-confirm Step-5 AC tests are still meaningful once real code
  exists and to prove any coverage-expansion test added at that gate.

Either way, record which mode ran in the handoff (below) so an
orchestrating caller can fold the evidence into its own records without
re-deriving it.

If the project ships a meaningfulness verifier (e.g. `npm run
meaningfulness`), run it — it independently confirms red-on-broken /
green-on-fixed (coverage-expansion mode). Record the proof evidence in
the handoff (which mode ran; which variant broke, which test went red,
that the real module was restored).

### Step 7 — Determinism + additive-to-the-net check

- **Deterministic by construction**: seeded data, injected clocks, no
  order dependence, waits on conditions never durations. `Date.now()` /
  `Math.random()` in a data path the test asserts against is a
  `debugging-test-failures` class 4 patient you authored on purpose.
  Inject a deterministic clock / seeded RNG at the boundary, or remove
  the nondeterminism from the asserted path.
- **Additive to the net**: never delete or weaken an existing test to
  make a new one fit. The cardinal-rule posture from
  `debugging-test-failures` applies on the authoring side — refuse by
  default; if the user explicitly orders a weakening, comply only with a
  dated record (what was weakened, why, what restoring it takes). A new
  test that breaks the suite means fix the new test, not weaken the old.

### Step 8 — Run the full suite green; handoff; STOP

Run the project's full verification suite from the rules file — not just
the new test file. A new test that passes in isolation but breaks a
neighbour is not done. Only when the full suite is green is the pass
closed; success is exit codes, never intent. **In red-first mode the
suite is intentionally red** (the behaviour does not exist yet): closure
is "authored + proven red for the right reason + mode recorded", not a
green suite — green is the caller's downstream job
(`implementing-features` Step 7).

Hand off, concisely:

- **Test files added** — one line per file, at the project's conventional
  path.
- **AC → test mapping** — per criterion, the test (or rows) that verify
  it; criteria whose verifier is a higher-layer observable are noted and
  routed, not silently skipped.
- **Mode note — one line**: which meaningfulness mode ran (red-first
  pre-implementation, or coverage-expansion/standalone break→restore) so
  an orchestrating caller can fold the evidence in without re-deriving it.
- **Meaningfulness proof evidence** — which broken variant / breakage
  turned which test red; that the real module was restored; the
  objective verifier's exit code if one ran. In red-first mode: the
  actual pre-implementation failure text and confirmation it named the
  missing behaviour.
- **Suite status** — the full command and its exit 0.
- **Follow-ups** — any out-of-scope behaviour recorded for the next
  design/triage pass.

Then **STOP**. Do not commit, push, or open a PR unless the user asks.
Do not move to integration/e2e on your own — those are sibling skills
the user invokes separately. This skill never cascades into its
siblings on its own initiative; the one documented, intentional caller
that orchestrates a trio skill is `implementing-features`, at its Step 5
(red-first) and Step 9 (coverage gate) — that is a sibling skill
driving the call, not this skill choosing to chain.

## When not to use this skill

- **Diagnosing a failing test** — that is `debugging-test-failures`;
  this skill authors new tests, it does not fix or justify existing ones.
- **Behaviour that only exists at a seam** (store + client, DB + policy,
  outbox + replay) — that is `writing-integration-tests`. Mocking the
  seam at the unit layer authors a vacant test.
- **A user journey through the real UI** — that is `writing-e2e-tests`.
- **Implementing a feature** — that is `implementing-features`; this
  skill adds the verify-stage net, it does not ship code.
- **Authoring or revising the plan** — that is `designing-architecture`;
  this skill consumes the ACs, it does not write them.

## References

- [references/stacks/vue-supabase.md](references/stacks/vue-supabase.md)
  — unit-testing concerns for Vue 3 + Pinia + Supabase + Vitest stacks:
  table-driven conventions, fresh-pinia-per-test isolation, composable
  testing, and the no-DOM-unless-component-contract boundary. Read at
  Step 3 when the project's rules file declares stack `vue-supabase`.
- The acceptance-criteria contract this skill consumes is defined in
  [../designing-architecture/references/plan-format.md](../designing-architecture/references/plan-format.md)
  — the AC quality bar (observable behaviour + verifier pairs) that the
  AC → test mapping in Step 4 is built on.
- The failure doctrine this skill authors *against* lives in
  [../debugging-test-failures/SKILL.md](../debugging-test-failures/SKILL.md)
  — class 2 (a test that can no longer fail is not a test) and class 4
  (determinism) are the patients this skill's discipline prevents.
