---
name: writing-e2e-tests
description: Author e2e tests for user journeys via Playwright — behaviour only observable as a user journey through the real UI. Selectors by role/accessible-name/testid, never bare CSS; condition waits, NEVER waitForTimeout; auth via a fixture. Use whenever the user says 'write e2e for X', 'add e2e for the checkout flow', or surfaces a journey needing a real browser — even without saying 'e2e'. Maps steps to ACs when a plan is in play; meaningfulness is red-first (natural failure) pre-implementation or break->restore->green post-implementation — real-browser, deferred to a structural proxy without one. Routes wrong-layer to siblings — isolated logic -> writing-unit-tests; a store+client/DB+policy seam -> writing-integration-tests. Not for diagnosing failing tests (debugging-test-failures), implementing features (implementing-features), or authoring plans (designing-architecture).
---

# Writing E2E Tests

The verify stage's authoring side for the **e2e layer**: turn acceptance
criteria whose behaviour is only observable as a user journey through
the real UI into Playwright specs that drive the journey and assert on
user-observable outcomes. A pass is **done** when the spec maps each AC
to a step, uses role/accessible-name/testid selectors, waits on
conditions (never timeouts), sets up auth via a fixture, runs the
structural verifier green, and the handoff records the AC → step mapping
plus the real-browser validation status. **In red-first mode** (called
pre-implementation) the journey does not exist yet, so the pass closes
on "spec authored + proven red for the right reason + mode recorded",
not on a green structural verifier — real-browser green is the caller's
downstream job (`implementing-features` Step 7).

This skill is the consumer of `designing-architecture`'s acceptance
criteria — see
[../designing-architecture/references/plan-format.md](../designing-architecture/references/plan-format.md)
for the AC contract (link it, never duplicate it). It is the sibling of
`writing-unit-tests` (isolated logic) and `writing-integration-tests`
(seams); the right-layer check (Step 2) routes between the three.

**Meaningfulness honesty.** A test never seen red proves nothing — and
for e2e the proof has **two independent axes** that must not be collapsed
into one:

- **When the test goes red** (the mode axis): **red-first** (called
  pre-implementation — the natural failure IS the proof; confirm it
  names the missing UI behaviour, not a harness defect) vs
  **coverage-expansion/standalone** (code already exists — break the
  guarded journey, restore, see green).
- **Whether a browser is available to observe it** (the real-browser
  axis): with a real browser, prove the spec goes red when the guarded
  UI behaviour breaks and green when it holds; where no browser is
  available (CI sandbox, eval harness), the objective check is
  structural — the spec asserts on user-observable outcomes via awaited
  web-first assertions that *would* go red if the behaviour broke.

A red-first e2e spec *still* needs the real-browser-vs-structural-proxy
distinction for *its* proof (layered under the red-first framing) —
run the spec against the pre-feature fixture; a real browser observes a
real red, a structural proxy observes the expected non-passing
structural signal. Real-browser red is a deferred validation, documented
honestly — never silently skipped, in either mode.

## The authoring pass

Copy this checklist and check off items as you complete them.

```
E2E-test Progress:
- [ ] 1. Identify the input (plan ACs, or an untested user journey)
- [ ] 2. Right-layer check (route wrong-layer requests to a sibling)
- [ ] 3. Detect stack & load the matching stack reference
- [ ] 4. Map ACs to journey steps (AC -> step; one journey per spec)
- [ ] 5. Write the spec (role selectors, condition waits, auth fixture)
- [ ] 6. Meaningfulness (mode-branched: red-first natural failure, or break->red->restore->green; and real-browser or structural proxy on either)
- [ ] 7. Determinism + additive-to-the-net check
- [ ] 8. Run the suite green; handoff; STOP
```

### Step 1 — Identify the input

Two entry shapes:

- **A plan artifact is in play** — read it first (frontmatter status,
  then `## Acceptance Criteria`). E2e ACs name a user journey: a
  verifier that needs a real browser (`npm run e2e` in a spec file, a
  Playwright selector). Each AC maps to one or more steps in the
  journey. Do not invent steps for behaviour outside the plan's
  `Included` scope; out-of-scope behaviour is a follow-up, the
  `implementing-features` posture.
- **No plan — an untested journey** — the input is a behaviour only a
  user taking the real UI journey can observe. If the behaviour is
  isolated logic, route to `writing-unit-tests` (Step 2); if it lives
  at a seam, route to `writing-integration-tests`.

### Step 2 — Right-layer check

Before writing, classify the behaviour. Each skill in the trio carries
this same table:

| Behaviour only observable when… | Right layer |
|---|---|
| Logic computable in isolation (pure function, store action with externals faked, composable) | **unit** → `writing-unit-tests` |
| Two collaborators meet at a seam (store + client, DB + policy, outbox + replay) | **integration** → `writing-integration-tests` |
| A user journeys through the real UI to see the outcome | **e2e** (this skill) |

If the request names isolated logic or a seam, **route to the sibling
and stop** — do not spin up a real browser to test a pure function or a
client seam. A browser-driven test of a pure slugify utility adds the
browser's flakiness and run time to a check the function's own return
already provides — a slow, brittle wrong-layer test. Name the sibling,
give the one-line reason, and stop. Wrong-layer authoring is
additive-to-the-net in reverse — it adds a test that costs more and
verifies less.

### Step 3 — Detect stack & load the matching stack reference

Identify the project stack from the rules file (`AGENTS.md` /
`.opencode/agents.md`). If this skill bundles a matching stack
reference under `references/stacks/` (resolved against this skill's own
directory — not the project's), read it now and apply its e2e concerns.
If none exists, proceed generically and flag the gap in the handoff.

Available stack references:

- vue-supabase → [references/stacks/vue-supabase.md](references/stacks/vue-supabase.md)
  Read when the project is Vue 3 + Pinia + Supabase with Playwright.
  Applies the selector/condition-wait discipline, auth-fixture session
  setup, PWA/offline testing via `context.setOffline`, service-worker
  caveats, and trace-on-failure evidence.

### Step 4 — Map ACs to journey steps; one journey per spec

Before writing selectors, list the AC → step mapping. Each e2e AC
becomes a step (or steps) in one journey: navigate, act, observe. Write
the mapping as `// AC` comments in the spec as you go — it is the
handoff artifact. One journey per spec file: a spec that bundles three
journeys hides which journey failed and couples their setup. Split
additional journeys into sibling spec files.

No AC is left unverified without an explicit note (e.g. "AC5 is a
unit-layer observable — routed to writing-unit-tests").

### Step 5 — Write the spec (the e2e discipline)

- **Selectors by role / accessible name / data-testid, in that
  preference order.** `getByRole`, `getByLabelText`, `getByTestId`,
  `getByText` — NOT bare CSS (`locator('.btn')`, `page.$('.foo')`).
  Role selectors survive markup refactors and double as an accessibility
  check; CSS tied to classes breaks on the next UI change and bypasses
  the a11y signal. If a role/testid is genuinely unavailable, add a
  `data-testid` to the component rather than reaching for CSS.
- **Waits on conditions and selectors, NEVER `waitForTimeout`.**
  `await expect(locator).toBeVisible()` and `await getByRole(...).click()`
  poll on a condition and settle when the UI catches up.
  `waitForTimeout` sleeps — it masks flakiness and is the canonical
  `debugging-test-failures` class 4 patient authored into the suite. A
  test that "passes locally, fails in CI" almost always has a
  `waitForTimeout` in its path.
- **Authenticated session via a fixture, not login-UI replay per test.**
  Replay the login UI in every test and every journey couples to the
  auth flow and burns run time. Set up the session once via a fixture
  (a storage state, an `addInitScript` that seeds the auth token) and
  inject the authenticated page. A spec that fills a password field is
  authoring the auth flow, not the journey under test.
- **Await every web-first assertion and every page action.** A bare
  `expect(locator).toBeVisible()` without `await` does not wait — it is
  a no-op that passes regardless of the UI state. `await expect(...)`.
  Likewise `await page.goto(...)`, `await getByRole(...).click()`.
- **Assert on user-observable outcomes.** Visible text, visible
  indicators, the URL — what the user observes. Not internal store
  state, not a component's private fields, not the call sequence. The
  journey verifies the user sees the outcome; the lower layers verify
  the mechanics.

### Step 6 — Meaningfulness (mode-branched; real-browser or structural proxy)

Prove the spec can fail. The proof **branches on an explicit
caller-stated mode**; the real-browser vs structural-proxy axis applies
within either mode:

- **Red-first mode (pre-implementation).** A caller —
  `implementing-features` at its Step 5, explicitly saying this is a
  red-first call, or a user authoring ahead of an unbuilt journey — is
  invoking this skill *before the UI behaviour exists*. There is nothing
  to break yet, so the post-implementation break/restore does not apply.
  The proof is: **run it; it MUST fail; the natural failure IS the
  red**. Confirm it fails **for the right reason** — read the actual
  failure and confirm it names the *missing UI behaviour* (a selector
  that does not resolve because the element is absent; a navigation that
  404s on a not-yet-built route). A failure from a broken test
  **setup** — a typo, a bad auth-fixture import, a wrong base URL — is
  red for the **wrong** reason: a trap, not a proof. Fix the spec's own
  setup (not the feature, which does not exist yet) and re-run until it
  names the missing UI behaviour. Once it does, the proof obligation is
  **satisfied** — a spec born red-first does not need a later
  break/restore to re-prove its authoring; it already went red against
  real absence. This is not a `debugging-test-failures` scenario: no
  working code ever existed to regress from, so word the trap
  consistently with that skill's class 2 but do not invoke it.
- **Coverage-expansion / standalone mode (post-implementation).** Code
  already exists. With a real browser: break the guarded UI behaviour
  (revert the feature, hide the indicator), run the spec, observe
  **RED**; restore, observe **GREEN**. A spec that has never been seen
  red may pass against a page that never rendered the outcome. The same
  proof is reused by `implementing-features`' Step 8 coverage gate to
  re-confirm Step-5 AC journey specs are still meaningful once real code
  exists and to prove any coverage-expansion spec added at that gate.

Either mode: where no browser is available, the objective check is
structural — the spec asserts on user-observable outcomes via awaited
web-first assertions that *would* go red if the behaviour broke. Run the
project's structural verifier if one exists (e.g. `npm run test` parsing
the spec). A red-first spec, run structurally against the pre-feature
fixture, produces an expected non-passing structural signal (a missing
selector, an unresolved assertion) — document real-browser red-first as
the **same kind** of deferral already in place, not a new one.
Real-browser red is a deferred validation — honest deferral, not a
silent skip, in either mode. This is the authoring-side mirror of
`debugging-test-failures` class 2: author so the spec genuinely guards
observable behaviour, not a no-op.

Record which mode ran in the handoff so an orchestrating caller can fold
the evidence into its own records without re-deriving it.

### Step 7 — Determinism + additive-to-the-net check

- **Deterministic by construction**: seeded data, injected clocks, no
  order dependence, waits on conditions never durations. E2e state
  that leaks across specs (a logged-in session, a cached page)
  produces the order-dependent flake `debugging-test-failures` class 4
  owns — isolate via fixtures and `test.use({ storageState })`.
- **Additive to the net**: never delete or weaken an existing test to
  make a new one fit. The cardinal-rule posture from
  `debugging-test-failures` applies on the authoring side — refuse by
  default; if the user explicitly orders a weakening, comply only with a
  dated record (what was weakened, why, what restoring it takes).

### Step 8 — Run the suite green; handoff; STOP

Run the project's full verification suite from the rules file. Where a
real browser is available, `npm run e2e` is the closure signal — exit
0, never intent. Where the browser is deferred, run the structural
verifier and document the real-browser validation as deferred. **In
red-first mode the suite is intentionally red** (the journey does not
exist yet): closure is "spec authored + proven red for the right reason
+ mode recorded", not a green structural verifier — real-browser green
is the caller's downstream job (`implementing-features` Step 7).

Hand off, concisely: **spec files added**; **AC → step mapping**;
**mode note — one line** (which meaningfulness mode ran: red-first
pre-implementation, or coverage-expansion/standalone break→restore) and
the real-browser-vs-structural-proxy status of its proof, so an
orchestrating caller can fold the evidence in; **selector/wait
discipline confirmed** (role selectors, no `waitForTimeout`, awaited
assertions); **auth-fixture usage**; **suite status** (structural
verifier exit 0; real-browser deferred or green); **follow-ups**. Then
**STOP**. Do not commit, push, or open a PR unless the user asks. Do not
move to unit/integration on your own — those are sibling skills the user
invokes separately. This skill never cascades into its siblings on its
own initiative; the one documented, intentional caller that
orchestrates a trio skill is `implementing-features`, at its Step 5
(red-first) and Step 8 (coverage gate) — that is a sibling skill driving
the call, not this skill choosing to chain.

## When not to use this skill

- **Isolated logic** (pure function, store action, composable) — that is
  `writing-unit-tests`. Driving a real browser to test a pure function
  is a wrong-layer e2e.
- **Behaviour at a seam** (store + client, DB + policy, outbox +
  replay) — that is `writing-integration-tests`. A browser-driven seam
  test is slower and less precise than driving the seam directly.
- **Diagnosing a failing test** — that is `debugging-test-failures`;
  this skill authors new specs, it does not fix flaky existing ones.
- **Implementing a feature** — that is `implementing-features`; this
  skill adds the verify-stage net, it does not ship code.
- **Authoring or revising the plan** — that is `designing-architecture`.

## References

- [references/stacks/vue-supabase.md](references/stacks/vue-supabase.md)
  — e2e concerns for Vue 3 + Pinia + Supabase + Playwright stacks:
  selector/condition-wait discipline, auth-fixture session setup,
  PWA/offline testing via `context.setOffline`, service-worker caching
  caveats, and trace-on-failure evidence. Read at Step 3 when the
  project's rules file declares stack `vue-supabase`.
- The acceptance-criteria contract this skill consumes is defined in
  [../designing-architecture/references/plan-format.md](../designing-architecture/references/plan-format.md)
  — the AC quality bar (observable behaviour + verifier pairs) that the
  AC → step mapping in Step 4 is built on.
- The failure doctrine this skill authors *against* lives in
  [../debugging-test-failures/SKILL.md](../debugging-test-failures/SKILL.md)
  — class 2 (a test that can no longer fail is not a test; the
  red-on-broken proof) and class 4 (determinism: `waitForTimeout` as a
  flake suspect, shared-state isolation) are the patients this skill's
  discipline prevents.
