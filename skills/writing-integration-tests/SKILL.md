---
name: writing-integration-tests
description: Author integration tests for seams — behaviour that only exists where collaborators meet (store+client, DB+policy, outbox+replay). Real collaborators, faked transport at the edge; RLS via the authenticated client, never a service-role bypass; seeded state per test. Use whenever the user says 'write integration tests for X', 'test the RLS policy', 'test the offline replay', or surfaces a seam gap — even without saying 'integration'. Proven to fail — red-first (natural failure names the missing seam) pre-implementation or break->restore->green post-implementation — and maps to an AC when a plan is in play. Routes wrong-layer to siblings — isolated logic -> writing-unit-tests; a user journey via the real UI -> writing-e2e-tests. Not for diagnosing failing tests (debugging-test-failures), implementing features (implementing-features), or authoring plans (designing-architecture).
---

# Writing Integration Tests

The verify stage's authoring side for the **integration layer**: turn
acceptance criteria whose behaviour only exists at a seam into
integration tests that drive real collaborators through a faked
transport at the outermost boundary. A pass is **done** when the new
tests are green on the fixed collaborators, red on a broken variant,
the full suite is green, no existing test was weakened, and the handoff
carries the AC → test mapping plus the meaningfulness proof evidence.
**In red-first mode** (called pre-implementation) the suite is
intentionally red — the seam behaviour does not exist yet — so the pass
closes on "authored, proven red for the right reason, mode recorded",
not on a green suite; green is the caller's downstream job
(`implementing-features` Step 7), not this pass's closure.

This skill is the consumer of `designing-architecture`'s acceptance
criteria — see
[../designing-architecture/references/plan-format.md](../designing-architecture/references/plan-format.md)
for the AC contract (link it, never duplicate it). It is the sibling of
`writing-unit-tests` (isolated logic) and `writing-e2e-tests` (user
journeys); the right-layer check (Step 2) routes between the three.

## The authoring pass

Copy this checklist and check off items as you complete them.

```
Integration-test Progress:
- [ ] 1. Identify the input (plan ACs, or an untested seam)
- [ ] 2. Right-layer check (route wrong-layer requests to a sibling)
- [ ] 3. Detect stack & load the matching stack reference
- [ ] 4. Map ACs to seam assertions (AC -> test, before writing)
- [ ] 5. Write the test (real collaborators, faked transport at the edge)
- [ ] 6. Meaningfulness proof (mode-branched: red-first natural failure, or break the seam -> red -> restore -> green)
- [ ] 7. Determinism + additive-to-the-net check
- [ ] 8. Run the full suite green; handoff; STOP
```

### Step 1 — Identify the input

Two entry shapes:

- **A plan artifact is in play** — read it first (frontmatter status,
  then `## Acceptance Criteria`). Integration ACs name a seam: a
  verifier that needs two collaborators to meet (store + client, DB +
  policy, outbox + replay). Each AC's verifier names the integration
  test that implements it. Do not invent tests for behaviour outside
  the plan's `Included` scope; out-of-scope behaviour is a follow-up,
  the `implementing-features` posture.
- **No plan — an untested seam** — the input is a behaviour that only
  shows up when collaborators run together (a policy that hides rows,
  a replay that flushes a queue, a cache that invalidates on a write).
  If the behaviour is isolated logic with no collaborator, that is a
  unit test — route to `writing-unit-tests` (Step 2). If the behaviour
  is a user journey through the real UI, route to `writing-e2e-tests`.

### Step 2 — Right-layer check

Before writing, classify the behaviour. Each skill in the trio carries
this same table:

| Behaviour only observable when… | Right layer |
|---|---|
| Logic computable in isolation (pure function, store action with externals faked, composable) | **unit** → `writing-unit-tests` |
| Two collaborators meet at a seam (store + client, DB + policy, outbox + replay) | **integration** (this skill) |
| A user journeys through the real UI to see the outcome | **e2e** → `writing-e2e-tests` |

If the request names isolated logic or a user journey, **route to the
sibling and stop** — do not manufacture a fake seam to justify an
integration test. Faking a store + client around a pure function that
touches neither creates a test of the fake, not of the function — a
vacant test at the wrong layer. Name the sibling, give the one-line
reason, and stop. Wrong-layer authoring is additive-to-the-net in
reverse — it adds a test that lies.

### Step 3 — Detect stack & load the matching stack reference

Identify the project stack from the rules file (`AGENTS.md` /
`.opencode/agents.md`). If this skill bundles a matching stack
reference under `references/stacks/` (resolved against this skill's own
directory — not the project's), read it now and apply its
integration-testing concerns. If none exists, proceed generically and
flag the gap in the handoff.

Available stack references:

- vue-supabase → [references/stacks/vue-supabase.md](references/stacks/vue-supabase.md)
  Read when the project is Vue 3 + Pinia + Supabase. Applies the
  supabase test-client pattern (faked transport at the outermost
  boundary), seeding + cleanup discipline, RLS policy testing through
  the authenticated client (never service-role bypass), and
  offline-outbox replay seam testing.

### Step 4 — Map ACs to seam assertions

Before writing assertions, list the AC → test mapping. Each integration
AC becomes one or more assertions on the seam's observable outcome:
which rows a user sees, which mutations reached the client and in what
order, what state a collaborator holds after the interaction. The
mapping is the handoff artifact; write it down as you go. No AC is left
unverified without an explicit note (e.g. "AC4 is a manual e2e
observable — routed to writing-e2e-tests").

### Step 5 — Write the test (real collaborators, faked transport at the edge)

The discipline that keeps integration tests meaningful:

- **Real collaborators where feasible; fake only the transport, at the
  outermost boundary.** The store, the outbox, the policy-evaluation
  logic are real — they are the behaviour under test. The supabase
  client (the network/Postgres edge) is faked, because real Postgres is
  not available in the test process. Faking a collaborator that is part
  of the behaviour under test vacates the assertion — the test passes
  against a stub that enforces nothing. This is `debugging-test-failures`
  class 2 authored into the suite, and on a security seam it is the
  cardinal-rule weakening applied to isolation.
- **RLS / policy isolation is asserted through the authenticated client
  as the user, never through a service-role bypass.** A service-role
  query bypasses RLS — using it to assert "user B gets zero rows" tests
  the bypass, not the policy. Seed through a service role if you must
  set up rows the user could not create, then assert isolation through
  the user's own authenticated client. The "wrong user gets zero rows"
  shape is the canonical isolation assertion.
- **Seeded state per test; reset between tests.** Integration state
  (rows, queue, cache) that leaks across tests produces the
  order-dependent flake `debugging-test-failures` class 4 owns. Seed
  deterministically per test and reset the collaborator's state in
  `beforeEach` / a reset helper.
- **Assert the seam's observable outcome, not the internal call
  sequence between collaborators.** "Which rows came back," "which
  mutations reached the client and in order," "the queue is empty
  after" are behaviour. "The store called the client N times" is
  implementation — it locks the interaction and breaks on a
  behaviour-preserving refactor. If asked to assert an internal call
  count, refuse and explain: the outcome is verified *through* the
  observable, not by spying on the conversation between collaborators.

### Step 6 — Meaningfulness proof (mandatory; mode-branched)

After writing a test, prove it can fail. The proof **branches on an
explicit caller-stated mode** — the caller names the mode, this skill
does not infer it:

- **Red-first mode (pre-implementation).** A caller —
  `implementing-features` at its Step 5, explicitly saying this is a
  red-first call, or a user authoring ahead of an unwritten seam — is
  invoking this skill *before the behaviour exists*. There is nothing to
  break yet, so the post-implementation break/restore does not apply.
  The proof is: **run it; it MUST fail; the natural failure IS the
  red**. Confirm it fails **for the right reason** — read the actual
  failure and confirm it names the *missing seam behaviour* (a `not
  found` for an absent store action/replay path; an assertion expecting
  only-B-rows and observing A-rows because the policy module is absent;
  a reference to a collaborator that does not yet exist). A failure from
  a broken test **setup** — a typo, a bad import, a wrong seed — is red
  for the **wrong** reason: a trap, not a proof. Fix the test's own setup
  (not the feature, which does not exist yet) and re-run until it names
  the missing seam behaviour. Once it does, the proof obligation is
  **satisfied** — a test born red-first does not need a later
  break/restore to re-prove its authoring; it already went red against
  real absence. This is not a `debugging-test-failures` scenario: no
  working code ever existed to regress from, so word the trap
  consistently with that skill's class 2 but do not invoke it.
- **Coverage-expansion / standalone mode (post-implementation).** Code
  already exists. Break the guarded behaviour — swap in a seeded broken
  variant of the collaborator/policy (a leaky policy, a replay that
  drops mutations), or make a one-line breakage in the seam — run the
  test, observe **RED**; restore the real behaviour, observe **GREEN**.
  A new test that has never been seen red proves nothing: it may pass
  against a stub that enforces nothing, or vacuously. This is the
  authoring-side mirror of `debugging-test-failures` class 2 ("a test
  that can no longer fail is not a test") — author so that class 2 never
  applies to your tests. On a security seam the proof is non-negotiable:
  an isolation test that passes on a leaky policy is a false guarantee.
  The same proof is reused by `implementing-features`' Step 9 coverage
  gate to re-confirm Step-5 AC seam tests are still meaningful once real
  code exists and to prove any coverage-expansion test added at that
  gate.

Either way, record which mode ran in the handoff so an orchestrating
caller can fold the evidence into its own records without re-deriving it.

If the project ships a meaningfulness verifier (e.g. `npm run
meaningfulness`), run it — it independently confirms red-on-broken /
green-on-fixed (and, on RLS fixtures, that no service-role bypass was
used). Record the proof evidence in the handoff (which mode ran; which
variant broke, which test went red, that the real collaborator was
restored).

### Step 7 — Determinism + additive-to-the-net check

- **Deterministic by construction**: seeded state per test, injected
  clocks, no order dependence, waits on conditions never durations.
  Shared collaborator state across tests is a `debugging-test-failures`
  class 4 patient you authored on purpose — reset between tests.
- **Additive to the net**: never delete or weaken an existing test to
  make a new one fit. The cardinal-rule posture from
  `debugging-test-failures` applies on the authoring side — refuse by
  default; if the user explicitly orders a weakening, comply only with a
  dated record (what was weakened, why, what restoring it takes).

### Step 8 — Run the full suite green; handoff; STOP

Run the project's full verification suite from the rules file — not
just the new test file. A new integration test that passes in isolation
but breaks a neighbour (shared state leak, policy swap not restored) is
not done. Only when the full suite is green is the pass closed; success
is exit codes, never intent. **In red-first mode the suite is
intentionally red** (the seam behaviour does not exist yet): closure is
"authored + proven red for the right reason + mode recorded", not a
green suite — green is the caller's downstream job
(`implementing-features` Step 7).

Hand off, concisely: **test files added**; **AC → test mapping**;
**mode note — one line** (which meaningfulness mode ran: red-first
pre-implementation, or coverage-expansion/standalone break→restore)
so an orchestrating caller can fold the evidence in; **meaningfulness
proof evidence** (which mode ran; which broken variant turned which
test red, that the real collaborator was restored, the objective
verifier's exit code if one ran; in red-first mode, the actual
pre-implementation failure text and confirmation it named the missing
seam behaviour); **suite status**; **follow-ups**. Then **STOP**. Do
not commit, push, or open a PR unless the user asks. Do not move to
unit/e2e on your own — those are sibling skills the user invokes
separately. This skill never cascades into its siblings on its own
initiative; the one documented, intentional caller that orchestrates a
trio skill is `implementing-features`, at its Step 5 (red-first) and
Step 9 (coverage gate) — that is a sibling skill driving the call, not
this skill choosing to chain.

## When not to use this skill

- **Isolated logic** (pure function, store action with externals faked,
  composable) — that is `writing-unit-tests`. Manufacturing a fake seam
  around logic that has no collaborator authors a vacant test.
- **A user journey through the real UI** — that is `writing-e2e-tests`.
- **Diagnosing a failing test** — that is `debugging-test-failures`;
  this skill authors new tests, it does not fix existing ones.
- **Implementing a feature** — that is `implementing-features`; this
  skill adds the verify-stage net, it does not ship code.
- **Authoring or revising the plan** — that is `designing-architecture`;
  this skill consumes the ACs.

## References

- [references/stacks/vue-supabase.md](references/stacks/vue-supabase.md)
  — integration-testing concerns for Vue 3 + Pinia + Supabase stacks:
  the supabase test-client pattern (faked transport at the outermost
  boundary), seeding + cleanup discipline, RLS policy testing through
  the authenticated client (never service-role bypass), and
  offline-outbox replay seam testing. Read at Step 3 when the project's
  rules file declares stack `vue-supabase`.
- The acceptance-criteria contract this skill consumes is defined in
  [../designing-architecture/references/plan-format.md](../designing-architecture/references/plan-format.md)
  — the AC quality bar (observable behaviour + verifier pairs) that the
  AC → test mapping in Step 4 is built on.
- The failure doctrine this skill authors *against* lives in
  [../debugging-test-failures/SKILL.md](../debugging-test-failures/SKILL.md)
  — class 2 (a test that can no longer fail is not a test) and class 4
  (determinism / shared state) are the patients this skill's discipline
  prevents; the RLS-silently-returns-empty diagnosis and the
  no-service-role-bypass rule are the security-seam doctrine.
