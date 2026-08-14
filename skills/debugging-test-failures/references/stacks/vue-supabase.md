# Stack: vue-supabase (debugging-time concerns)

Read this when Step 2 of the debug pass detects the project stack is
`vue-supabase` (Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase
Postgres + Auth + RLS, Vitest + Playwright). This file is
*debugging-time* — the diagnosis concerns you apply when a verification
command is failing and won't converge — and is the complement of the
design-time reference at
[../../designing-architecture/references/stacks/vue-supabase.md](../../designing-architecture/references/stacks/vue-supabase.md)
(planning) and the implement-time reference at
[../../implementing-features/references/stacks/vue-supabase.md](../../implementing-features/references/stacks/vue-supabase.md)
(editing). Project specifics (exact verification commands,
generated-types path, plans_dir) come from the project's rules file
(`AGENTS.md` / `.opencode/agents.md`); this file holds the stack-wide
debugging concerns that apply regardless of project.

If the project declares a different stack, do not read this file — read
the matching `references/stacks/<stack>.md`. If no matching reference
exists, proceed generically and flag the gap to the user in the
handoff.

## Contents

- E2E wait discipline (no fixed timeouts)
- Playwright trace + screenshot as evidence
- Pinia state isolation between tests
- Supabase RLS silently returns empty rows
- Generated-types drift after schema changes
- Where this stack trips a debug pass

## E2E wait discipline (no fixed timeouts)

Playwright e2e on this stack waits on **selectors and conditions**, not
fixed timeouts. When an e2e test is failing or flaky, the wait
discipline is the first suspect:

- `await expect(page.getByText(/completed/i)).toBeVisible()` and
  `await page.waitForSelector(...)` poll on a condition and settle
  automatically when the UI catches up. A test using these that fails
  is failing because the condition never became true — investigate the
  condition, not the wait.
- `await page.waitForTimeout(<ms>)` does **not** wait on anything — it
  sleeps. In a failing or flaky e2e, a `waitForTimeout` is a prime
  nondeterminism suspect: it passes when the machine is fast enough and
  fails when CI is slow. The fix is class 4 (environment): replace the
  fixed timeout with a condition wait on the actual UI state the test
  depends on. Do **not** lengthen the timeout — that hides the flake
  for one more CI cycle.
- A test that "passes locally, fails in CI" almost always has a
  `waitForTimeout` or an unwaited async update in its path. Reproduce
  by rerunning under `playwright test --repeat-each=10` or by
  throttling CPU; the discriminating experiment is the rerun, not a
  longer sleep.

## Playwright trace + screenshot as evidence

On this stack, a failing e2e is a perception problem as much as a
logic problem — the assertion tripped at some UI state you did not
observe. Use Playwright's evidence primitives as the discriminating
experiment in Step 4:

- `playwright test --trace=on` (or `retain-on-failure`) produces a
  trace: DOM snapshots at each step, network log, console errors. Open
  it with `npx playwright show-trace <path>`. The trace at the failing
  step shows the DOM the assertion actually saw — often different from
  the DOM you assumed.
- `await page.screenshot({ path: ... })` at the suspect step, or
  `expect(...).toHaveScreenshot()` for a visual regression baseline.
  For a "the dialog isn't there" failure, the screenshot tells you
  whether the dialog never rendered vs. rendered and was dismissed vs.
  rendered off-screen.
- Console errors in the trace are a frequent root cause: a Supabase
  query throwing, a Vuetify component failing to register an icon
  (renders silently blank), a Pinia action rejecting. The assertion
  fails downstream; the error is upstream in the console log.

Treat the trace as the experiment whose outcome discriminates "the UI
never reached the state" from "the UI reached it but the assertion was
wrong" (class 1 vs class 2).

## Pinia state isolation between tests

Pinia stores are singletons. A test that mutates store state and a
later test that reads it produce **order-dependent** failures — the
canonical class 4 shared-state flake. On this stack:

- Reset store state between tests. In Vitest, `afterEach(() =>
  activePinia.state.value = {})` or per-store `$reset()` (Options-API
  stores have `$reset`; setup-syntax stores do not — define a manual
  reset). A test that only fails when run after another is mutating
  shared store state the other reads.
- `createTestingPinia` mocks actions/getters; that is legitimate when
  the behavior under test is **not** the store (a component's rendering
  given a store state), and is **weakening the net** when the behavior
  under test **is** the store action. Classify carefully: mocking the
  thing you are testing turns a real assertion into a tautology.
- A test that sets `running: true` and never resets it will leak into
  the next test's `expect(store.running).toBe(false)`. The fix is
  isolation (reset), not "run my test first" (order-coupling is the
  symptom, not the fix).

## Supabase RLS silently returns empty rows

A defining trap of this stack: a Row-Level Security policy that denies
a row does **not** error — it returns an empty result set. A test that
asserts "the inserted row appears" fails with "got 0 rows, expected 1",
which looks like the insert failed. The insert succeeded; the policy
hid the row from the selecting client.

- When a "data disappeared" assertion fails, the discriminating
  experiment is: select the same row with the service role (bypasses
  RLS) or as the owning user. If the row appears under the service role
  but not the anon/auth client, the root cause is the RLS policy, not
  the insert — class 1 (the code), where "the code" is the policy in
  `db/schema.sql`, not the application code.
- Check `auth.uid()` wiring: a policy `using (auth.uid() = user_id)`
  returns nothing if the test client is not authenticated, or if
  `user_id` was not set on the inserted row. A row inserted without
  `user_id` is invisible to every policy that keys on it — the insert
  returns success, the row is silently gone.
- Supabase errors are often returned in the `{ error }` field, not
  thrown — `const { data, error } = await supabase.from(...).select()`
  with `error` unchecked swallows the failure. A test that proceeds
  past an unchecked `error` is reading empty `data` and asserting
  against a silent failure. The fix: surface the error, then decide
  whether the error is the bug (class 1) or the test's expectation of
  success was wrong (class 2).
- Do NOT "fix" an RLS-hidden-row test by querying with the service role
  in the test — that mocks away the security behavior under test
  (cardinal rule). Fix the policy or the `user_id` wiring.

## Generated-types drift after schema changes

`types/database.types.ts` (path per rules file) is a build artifact
regenerated from the schema. After a schema change, drift between the
generated types and the schema produces type errors that look like code
bugs but are actually a stale artifact:

- A type error "Property `foo` does not exist on type `...Insert`"
  right after a column was added is **not** a code bug — it is the
  generated types being stale. The fix is to regen (`npm run db:types`
  or the project's regen command), **never** to hand-edit the generated
  types file. Hand-edits survive the next regen and mask the drift.
- A test that inserts a row with a column the types don't have is
  failing because the types haven't been regenerated since the column
  was added. Confirm by reading `db/schema.sql` (source of truth) and
  comparing to `types/database.types.ts`: if the schema has the column
  and the types don't, regen.
- If a plan touched the schema, the plan's `Schema / Type Impacts`
  section names the regen. A type error in the implement pass's
  verification that the regen would fix is a mechanical deviation (the
  implement skill proceeds with the regen). A type error the regen
  does **not** fix is a real code bug — now you are in class 1.
- `git diff --exit-code -- types/` (the project's drift check) failing
  is a signal that someone hand-edited the generated types, or that the
  regen was run and not committed. Read the diff before "fixing" it.

## Where this stack trips a debug pass

- **A `waitForTimeout` in a flaky e2e.** Passes locally, fails on slow
  CI. Replace with a condition wait; do not lengthen.
- **RLS returns empty rows for an unauthenticated or mis-`user_id`'d
  insert.** Looks like "the insert failed"; the insert succeeded, the
  policy hid the row. Select with the service role to discriminate.
- **A Pinia store leaking state between tests.** Order-dependent
  failure; isolate with `$reset` / state reset, do not pin order.
- **Stale generated types after a schema change.** A type error on a
  column that exists in `db/schema.sql`. Regen; never hand-edit.
- **An unchecked Supabase `error` field.** The test reads empty `data`
  and asserts against a silent failure; the error is upstream, in the
  unhandled `error`.
- **Mocking the store action under test.** Turns a real assertion into
  a tautology — cardinal-rule weakening, not a fix.
- **`[Vue warn]: Unhandled error during execution of component event
  handler / transition hook`** (console-visible defect class). These
  dev-mode warnings are runtime defects production builds strip; they
  fire on close/teardown paths only when the journey closes what it
  opens. Run the Step-1 scripted-browser repro (pageerror/console
  listeners, walk the flow including the close) before hypothesizing —
  the stack trace + state dump is ground truth in one run.

Each of these is a class-4 or class-1 trap dressed up as "the test is
flaky" or "the data disappeared" — the discriminating experiment (a
service-role select, a trace, a regen, a rerun) is what separates the
real root cause from the surface symptom.
