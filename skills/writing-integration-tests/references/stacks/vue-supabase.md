# Stack: vue-supabase (integration-testing concerns)

Read this when Step 3 of the authoring pass detects the project stack is
`vue-supabase` (Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase
Postgres + Auth + RLS). This file is *integration-testing-time* — the
conventions you apply when authoring tests for seams — and is the
complement of the unit-time reference at
[../../writing-unit-tests/references/stacks/vue-supabase.md](../../writing-unit-tests/references/stacks/vue-supabase.md)
(isolated logic) and the e2e-time reference at
[../../writing-e2e-tests/references/stacks/vue-supabase.md](../../writing-e2e-tests/references/stacks/vue-supabase.md)
(user journeys). Project specifics come from the project's rules file
(`AGENTS.md` / `.opencode/agents.md`); this file holds the stack-wide
integration-testing concerns.

If the project declares a different stack, do not read this file — read
the matching `references/stacks/<stack>.md`. If no matching reference
exists, proceed generically and flag the gap in the handoff.

## Contents

- The supabase test-client pattern (faked transport at the edge)
- Seeding + cleanup discipline
- RLS policy testing without service-role bypass
- Offline-outbox replay seam testing
- Where this stack trips an integration-test pass

## The supabase test-client pattern (faked transport at the edge)

Real Postgres is not available in the test process, so the supabase
client — the transport at the outermost boundary — is faked. Everything
behind it (the store, the outbox, the policy evaluation) is real.

- Build a fake `createClient` that applies the project's RLS policies
  (read from `db/` / the migration files) to seeded rows, given the
  client's `authUid`. It returns the same `{ data, error }` shape the
  real client returns, so the store under test is unchanged.
- The fake enforces the policy; it does not enforce nothing. A fake
  that returns all rows regardless of `authUid` is a stub, not a fake
  transport — it vacates every isolation assertion run through it.
- Wire the real store to the faked client at the seam (dependency
  injection of the client into the store). Do not mock the store; the
  store is the behaviour under test.

## Seeding + cleanup discipline

- Seed per test, deterministically. Shared seeded state across tests is
  the order-dependent flake `debugging-test-failures` class 4 owns.
- Prefer pre-provided seed fixtures over seeding inside the test, so the
  test never needs a service-role bypass to set up rows the user could
  not create. If a test must seed through a service role, do the seeding
  in setup, then assert isolation through the user's authenticated
  client — never through the service role.
- Reset collaborator state between tests (`$reset`, a `_reset` helper,
  a fresh fake client per test). A queue, cache, or store that leaks
  state from one test into the next produces a test that only fails
  when run after another.
- Supabase errors arrive in `{ error }`, not thrown. A test that
  proceeds past an unchecked `error` reads empty `data` and asserts
  against a silent failure — surface the error before asserting on
  `data`.

## RLS policy testing without service-role bypass

RLS is the security boundary on this stack; the integration test is
where that boundary is verified. The doctrine (shared with
`debugging-test-failures`' RLS-silently-returns-empty diagnosis):

- Assert isolation through the **authenticated client as the user**
  (`createClient({ authUid: 'the-user', seed })`). The canonical shape:
  the wrong user querying the table gets **zero rows** of the owner's
  data.
- Never assert isolation through a service-role bypass
  (`serviceRole: true`). The service role skips RLS; a test that uses it
  to prove "user B gets zero rows" is testing the bypass, not the
  policy. This is the cardinal-rule weakening applied to a security
  seam — it manufactures a false guarantee.
- A policy that denies does not error — it returns an empty set. So the
  isolation assertion is "zero rows of the other user," not "an error
  was thrown." A test that expects RLS to throw is asserting against
  behaviour the stack does not have.
- Do not edit the policy to make the test pass. The policy is the system
  under test; the test verifies it, not the reverse.

## Offline-outbox replay seam testing

On this stack, offline mutations queue in an outbox and replay through
the supabase client on reconnect. The seam (outbox + client) is an
integration test:

- Drive the real store's offline path (queue mutations) and its sync
  path (replay) through a faked client that records what it received.
  Assert the **observable**: every queued mutation reached the client,
  in the order queued, and the outbox is empty after replay.
- Assert the outcome, not the call count. "The client received all N
  mutations in order" is behaviour; "replay called insert exactly N
  times" is implementation — it breaks on a behaviour-preserving
  refactor that batches or coalesces.
- Reset the outbox between tests so one test's queued mutations do not
  leak into the next.
- Persistence (IndexedDB / localStorage) is a separate concern from
  replay — the replay seam test does not need to verify persistence
  unless an AC names it.

## Where this stack trips an integration-test pass

- **Mocking the store under test instead of faking the transport.** The
  store is the behaviour; mocking it vacates the assertion. Fake the
  client, keep the store real.
- **Asserting RLS isolation through the service role.** Bypasses the
  security behaviour under test — a false guarantee. Assert through the
  authenticated client.
- **A fake transport that returns all rows regardless of `authUid`.** A
  stub, not a fake — vacates every isolation assertion. The fake must
  apply the policy.
- **Shared seeded state across tests.** Order-dependent flake; class 4.
  Seed per test, reset between.
- **Asserting the call sequence between collaborators.** Brittle; locks
  the interaction. Assert the observable outcome.
- **An unchecked Supabase `error` field.** The test reads empty `data`
  and asserts against a silent failure; surface the error first.

Each of these is a vacant-or-flaky test dressed up as coverage — the
meaningfulness proof (Step 6) and the right-layer check (Step 2) catch
them before they reach the suite.
