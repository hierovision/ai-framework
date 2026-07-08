# Stack: vue-supabase (unit-testing concerns)

Read this when Step 3 of the authoring pass detects the project stack is
`vue-supabase` (Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase
Postgres + Auth + RLS, Vitest). This file is *unit-testing-time* — the
conventions you apply when authoring unit tests for isolated logic — and
is the complement of the integration-time reference at
[../../writing-integration-tests/references/stacks/vue-supabase.md](../../writing-integration-tests/references/stacks/vue-supabase.md)
(seams) and the e2e-time reference at
[../../writing-e2e-tests/references/stacks/vue-supabase.md](../../writing-e2e-tests/references/stacks/vue-supabase.md)
(user journeys). Project specifics (exact verification commands,
generated-types path) come from the project's rules file (`AGENTS.md` /
`.opencode/agents.md`); this file holds the stack-wide unit-testing
concerns that apply regardless of project.

If the project declares a different stack, do not read this file — read
the matching `references/stacks/<stack>.md`. If no matching reference
exists, proceed generically and flag the gap in the handoff.

## Contents

- Vitest table-driven conventions
- Pinia store testing (fresh pinia per test)
- Composable testing
- No DOM unless the unit is a component contract
- Where this stack trips a unit-test pass

## Vitest table-driven conventions

- Use `describe.each` / `it.each` (or a plain `for` loop over a cases
  array) for table-driven rows — one AC per case array, one row per
  observable input. Keep the case tuples tiny and labelled so a failure
  names the failing input, not just "expected 01:05".
- Co-locate edge cases (empty, boundary, error path) in the same cases
  array as the happy path — they are rows of the same AC, not separate
  tests. A boundary row that fails points at the AC's boundary
  behaviour directly.
- `assert.throws(() => fn(badInput), RangeError)` for the error-path AC
  — assert the thrown type, not just "it throws". A generic `throw`
  passes against a bug that throws the wrong error for the wrong reason.

## Pinia store testing (fresh pinia per test)

Pinia stores are singletons — state leaks across tests produce the
order-dependent flake that `debugging-test-failures` class 4 owns.

- Create a **fresh pinia per test**: `beforeEach(() =>
  setActivePinia(createPinia()))`. Do not share a pinia instance across
  tests in a file; a test that only fails after another is mutating
  shared store state.
- Options-API stores expose `$reset()`; setup-syntax stores do not —
  define a manual reset action and call it in `beforeEach` if the store
  holds state across actions under test.
- `createTestingPinia` mocks actions/getters. That is legitimate when
  the behaviour under test is **not** the store (a component's render
  given a store state), and is **weakening the net** when the behaviour
  under test **is** the store action — mocking the thing you test turns
  a real assertion into a tautology. If the AC is "the store action
  sets `running: true`", test the real action, not a mocked one.
- Assert the observable state change, not the internal call sequence.
  "After `start()`, `store.running === true && store.remainingSeconds
  === duration`" is behaviour; "start() called supabase.from" is
  implementation (and is also a seam — route to
  `writing-integration-tests`).

## Composable testing

- A composable (`use…`) that does not touch the DOM is tested by
  calling it inside a `setup` via `mount` from `@vue/test-utils`, or —
  when it only reads reactive state — by hosting it in a minimal
  `defineComponent` + `mount`. Do not call `useX()` bare at top level
  outside a component context; Pinia/Vue composables rely on the
  active instance.
- Inject faked externals (a clock, a storage primitive) via the
  composable's arguments or a provide/inject boundary — not by
  monkey-patching the composable's internals. The boundary is the seam
  you are allowed to fake; the composable's own logic is not.
- Time-dependent composables: inject a deterministic clock
  (`vi.useFakeTimers()` + `vi.setSystemTime`, or a passed-in `now`
  function). `Date.now()` in the asserted path is a class 4 patient.

## No DOM unless the unit is a component contract

- A pure function, a store action, a composable without DOM output —
  test in-process, no mount. Mounting the DOM for logic that does not
  render is an integration test in unit clothing; route it to
  `writing-integration-tests`.
- A component's *contract* (given these props + this store state, it
  renders this accessible output) is a legitimate unit — mount with
  `@vue/test-utils`, assert on the rendered output via role/accessible
  queries, and fake the store at the boundary (provide testing pinia
  with seeded state). Assert what the user observes (rendered text,
  emitted events), not the internal template structure — class names
  and wrapper hierarchies are implementation, not behaviour.
- Do not assert on CSS class names tied to Vuetify internals — they
  break on the next Vuetify version. Use the rendered accessible output.

## Where this stack trips a unit-test pass

- **Mocking the store action under test with `createTestingPinia`.**
  Turns the real assertion into a tautology — cardinal-rule weakening,
  authored in. Test the real action; mock only true externals.
- **Sharing a pinia across tests.** Order-dependent flake; class 4.
  Fresh pinia per test.
- **Asserting `supabase.from(...)` was called inside a store action.**
  That is a seam (store + client), not unit behaviour — route to
  `writing-integration-tests`. The unit assertion is the observable
  state change.
- **Mounting the DOM for a pure function.** Slower, brittle, and the
  wrong layer — test in-process.
- **`Date.now()` / `Math.random()` in the asserted path.** Class 4
  patient authored on purpose — inject a deterministic clock / seeded
  RNG.

Each of these is a vacant-or-flaky test dressed up as coverage — the
meaningfulness proof (Step 6) and the right-layer check (Step 2) catch
them before they reach the suite.
