# Stack: vue-supabase (implementation-time concerns)

Read this when Step 3 of the implement pass detects the project stack is
`vue-supabase` (Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase Postgres
+ Auth + RLS, Vitest + Playwright). This file is *implementation-time* —
the editing conventions you apply when changing code under an approved
plan — and is the complement of the design-time reference at
[../../designing-architecture/references/stacks/vue-supabase.md](../../designing-architecture/references/stacks/vue-supabase.md)
which governs planning. Project specifics (exact verification commands,
generated-types path, plans_dir) come from the project's rules file
(`AGENTS.md` / `.opencode/agents.md`); this file holds the stack-wide
concerns that apply regardless of project.

If the project declares a different stack, do not read this file — read
the matching `references/stacks/<stack>.md`. If no matching reference
exists, proceed generically and flag the gap to the user in the handoff.

## Contents

- Generated DB types
- Row-Level Security on edits
- Offline / outbox wiring
- Vuetify components + semantic CSS variables
- Pinia store + composable patterns
- E2E selector / condition discipline (no fixed timeouts)
- TypeScript hygiene
- Where this stack trips an implement pass

## Generated DB types

`types/database.types.ts` (path per rules file) is a **build artifact**.
The design stage's plan is the source for whether the schema changes;
the edit discipline on the implement side is:

- If the plan's `Schema / Type Impacts` section is `None.`, **do not
  touch the generated types file**. Editing it by hand introduces drift
  between schema and types that the next `db:types` regen surfaces as a
  failing `git diff` in verification.
- If the plan touches the schema, regenerate the types with the
  project's regen command from the rules file (commonly
  `npm run db:types`) — do **not** hand-edit even what looks like a
  one-line missing field. Hand-edits survive the regen, mask the schema
  drift, and break the audit trail.
- A criterion that requires a hand-edit of generated types to pass is a
  contract-breaking deviation (Step 4 of the skill) — the plan should
  have named the regen; route back to design rather than hand-edit.

## Row-Level Security on edits

The plan is the source for whether a new table is added and what policy
shape it gets. On the implement side:

- If the plan's `Schema / Type Impacts` says `None.`, do not edit
  `db/schema.sql` or any policy. An implement pass is not the place to
  add "just one more RLS policy I noticed was missing" — that is a
  follow-up, recorded in `### Follow-ups`, not a silent fix.
- When the plan does add a table with a per-user policy, prefer the
  project's existing policy shape (`auth.uid() = user_id` or whatever
  the existing tables use) over a new shape. Consistency here reduces
  the review surface.
- Service-role bypass (`service_role` in client code) is not the answer
  on this stack — if an in-scope edit "needs" it, that is a contract-
  breaking deviation. Route to design.

## Offline / outbox wiring

For an item that routes mutations through the offline outbox, the
project convention (per rules file) is: mutations go through the Pinia
store, which queues to IndexedDB / localStorage and replays via the
supabase client on reconnect. Implementation-time discipline:

- A new mutation in scope routes through the outbox; do not call
  `supabase.from(...).insert/update` directly from a component that
  the plan names as going offline. The plan's `Files to Modify` notes
  should say which path.
- Queued entries must persist (localStorage or IndexedDB), not hold in
  memory — an in-memory queue is a cache, not an outbox. The verifier
  on this stack commonly checks for a storage primitive.
- If the plan's `Excluded` list defers replay-on-reconnect wiring, do
  not wire it anyway — record the gap if a manual validation step
  depends on it, but stay in scope.

## Vuetify components + semantic CSS variables

Prefer Vuetify 3 components and the theme's semantic CSS variables over
raw CSS / custom components:

- Use Vuetify components (`v-btn`, `v-card`, `v-dialog`, etc.) instead
  of hand-rolling native elements styled to match — the design system
  carries accessibility and theming that hand-rolled markup loses.
- For color / spacing / typography, use Vuetify's semantic CSS variables
  (e.g. `var(--v-theme-primary)`, `var(--v-theme-surface)`) and the
  theme's spacing scale, not raw hex values or hardcoded `padding: 13px`.
  Raw values break when the theme switches (dark mode, brand override).
- Register new icons before use — Vuetify's icon set is opt-in per
  icon, and an unregistered icon renders silently blank instead of
  erroring, which is a hard-to-spot regression.
- Out-of-scope cosmetic polish (different button colour, extra spacing)
  is scope creep even when "trivial" — record it as a follow-up, do
  not edit it in.

## Pinia store + composable patterns

Follow existing patterns rather than introducing a new style:

- If the project uses Options-API stores (`defineStore('name', { state,
  actions })`), match that — do not switch to setup-syntax stores mid-
  pass. The reverse applies symmetrically. A mixed codebase is the
  audit-trail-breaker.
- State, getters, actions: mirror the naming and shape of the
  neighbouring stores. A new store that diverges in style will be
  flagged in review and is out of scope to refactor.
- Composables (`use…`) encapsulate reusable logic; route shared logic
  through a composable rather than importing a helper from a store file
  not meant to export one. If the plan does not name a new composable,
  do not introduce one — record the urge as a follow-up.

## E2E selector / condition discipline (no fixed timeouts)

Playwright e2e on this stack waits on **selectors and conditions**, not
fixed timeouts:

- `await expect(page.getByText(/completed/i)).toBeVisible()` and
  `await page.waitForSelector(...)` — these poll on a condition and
  settle automatically when the UI catches up.
- `await page.waitForTimeout(<ms>)` does not wait on anything — it
  sleeps, masking flakiness and inflating run time. Treat
  `waitForTimeout` as a defect if you encounter it in files the plan
  names; out-of-scope instances are a follow-up, not a drive-by fix.
- Prefer role-based / accessible selectors (`getByRole`,
  `getByLabelText`) over CSS selectors — they survive markup refactors
  and double as an accessibility check. CSS selectors tied to class
  names break on the next Vuetify version.

## TypeScript hygiene

- No `as any` — narrow the type. If a type from generated `database.types.ts`
  does not fit, that is a schema/types gap, not a cast (route to design).
- Favor early returns over deep nesting; `??` over `||` (the latter
  coerces 0 / '' / false which is rarely intended).
- Don't suppress errors with `// @ts-ignore` or `// eslint-disable-*` to
  get verification green — a suppressed failure is a deferred contract
  break. If a verifier cannot pass without a suppression, treat it as a
  contract-breaking deviation (Step 4 of the skill).

## Where this stack trips an implement pass

- **Hand-editing generated types to make type-check pass.** Drifts the
  schema↔types contract; regen instead, or stop and route to design.
- **`waitForTimeout` in a passing-but-flaky e2e.** Passes today, fails
  on a slow CI; replace with `waitForSelector` / `expect().toBeVisible()`
  when the spec is in Files to Modify.
- **Direct `supabase.from(...)` from a component the plan routes through
  the outbox.** Bypasses offline; the queue criteria will fail. Route
  through the store.
- **Implementing the "Excluded" replay-on-reconnect wiring because the
  code told you to.** Out of scope; record the follow-up and stop.
- **Refactoring the neighbouring store mid-pass.** Scope creep; record
  and stop.

Each of these is a scope-discipline failure dressed up as helpfulness —
the plan's `Files to Modify` + `Included`/`Excluded` lists are the
authority, not the code's ambient invitations.