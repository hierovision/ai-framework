# Project rules — Phasewave

## Stack
`vue-supabase` — Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase
(Postgres + Auth + RLS), Vitest (unit), Playwright (e2e). Progressive
Web App (offline-capable, service worker).

## Plan artifact
- `plans_dir: .opencode/plans/`
- Plan filename convention: `<slug>.md` (slug derived from the roadmap
  item ID or the feature, lowercase-kebab).
- If a plan already exists for the slug, **revise in place** — preserve
  the existing frontmatter history and prior sections (append changes;
  do not clobber).

## Verification commands (what the verify stage runs)
- Type check: `npm run type-check`
- Lint: `npm run lint`
- Unit/integration: `npm run test`

## Conventions
- Generated DB types live at `types/database.types.ts` — never hand-edit;
  regenerate via `npm run db:types` after schema changes. Schema is the
  source of truth (`db/schema.sql`); code references the generated types.
- Every table with user data gets Row-Level Security; default to
  per-user isolation (`auth.uid() = user_id`).
- Lib / utility modules live under `src/lib/<feature>.ts`. Stores live
  under `src/stores/<name>.ts`. Do not introduce new top-level
  directories for a single feature.
- Offline mutations go through the Pinia store, which queues to
  IndexedDB / localStorage and syncs via the supabase client when back
  online.
- No `as any` — narrow the type. No `waitForTimeout` in e2e; use
  `waitForSelector` / conditions. Register new icons before use.
- Vuetify 3 components and semantic CSS variables over raw CSS.