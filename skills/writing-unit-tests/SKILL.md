---
name: writing-unit-tests
description: Author unit tests for isolated logic — table-driven cases plus edge cases (empty, boundary, error) derived from the AC's observable behaviour, mocking true externals, never the behaviour under test. Use whenever the user says 'write unit tests for X', 'cover the plan's criteria', 'we have no tests for the store', or surfaces a gap for a pure function, Pinia store, composable, or utility — even without saying 'unit'. Each test is proven to fail (break the behaviour -> red, restore -> green; a test never seen red proves nothing) and maps to an AC when a plan is in play. Routes wrong-layer requests to siblings — behaviour at a store+client/DB+policy seam -> writing-integration-tests; a user journey via the real UI -> writing-e2e-tests. Not for diagnosing failing tests (debugging-test-failures), implementing features (implementing-features), or authoring plans (designing-architecture).
---

# Writing Unit Tests

The verify stage's authoring side for the **unit layer**: turn acceptance
criteria (or untested isolated behaviour) into table-driven unit tests
that assert observable behaviour, each proven to fail when that behaviour
breaks. A pass is **done** when the new tests are green on the real
module, red on a broken variant, the full suite is green, no existing
test was weakened, and the handoff carries the AC → test mapping plus
the meaningfulness proof evidence.

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
- [ ] 6. Meaningfulness proof (break -> red -> restore -> green)
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

### Step 6 — Meaningfulness proof (mandatory)

After writing a test, prove it can fail. Break the guarded behaviour —
swap in a seeded broken variant, or make a one-line breakage in the
module under test — run the test, observe **RED**; restore the real
behaviour, observe **GREEN**. A new test that has never been seen red
proves nothing: it may pass for the wrong reason, or vacuously. This is
the authoring-side mirror of `debugging-test-failures` class 2 ("a test
that can no longer fail is not a test") — author so that class 2 never
applies to your tests.

If the project ships a meaningfulness verifier (e.g. `npm run
meaningfulness`), run it — it independently confirms red-on-broken /
green-on-fixed. Record the proof evidence in the handoff (which variant
broke, which test went red, that the real module was restored).

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
closed; success is exit codes, never intent.

Hand off, concisely:

- **Test files added** — one line per file, at the project's conventional
  path.
- **AC → test mapping** — per criterion, the test (or rows) that verify
  it; criteria whose verifier is a higher-layer observable are noted and
  routed, not silently skipped.
- **Meaningfulness proof evidence** — which broken variant / breakage
  turned which test red; that the real module was restored; the
  objective verifier's exit code if one ran.
- **Suite status** — the full command and its exit 0.
- **Follow-ups** — any out-of-scope behaviour recorded for the next
  design/triage pass.

Then **STOP**. Do not commit, push, or open a PR unless the user asks.
Do not move to integration/e2e on your own — those are sibling skills
the user invokes separately.

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
