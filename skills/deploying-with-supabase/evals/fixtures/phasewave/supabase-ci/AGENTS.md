# Project rules — Phasewave (supabase-ci slice)

## Stack
`vue-supabase` — Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase
(Postgres + Auth + RLS), Vitest (unit), Playwright (e2e). This is a fixture
for the `deploying-with-supabase` skill: the runnable stubs are plain YAML
under `.github/workflows/` so the deploy pass can read and rewrite them.

## Plan artifact
- `plans_dir: .opencode/plans/`
- Plan filename convention: `<slug>.md` (lowercase-kebab).

## Conventions
- Supabase migrations run via `supabase db push` in CI.
- Prod deploys must migrate before serving traffic.
- `SUPABASE_ACCESS_TOKEN` is a secret; `SUPABASE_PROJECT_REF` is a var.
