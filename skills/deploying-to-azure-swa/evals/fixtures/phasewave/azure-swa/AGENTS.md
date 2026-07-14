# Project rules — Phasewave (azure-swa slice)

## Stack
`vue-supabase` — Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase
(Postgres + Auth + RLS), Vite build → `dist/`, Vitest (unit), Playwright
(e2e). This is a fixture for the `deploying-to-azure-swa` skill: the
runnable stubs are plain YAML under `.github/workflows/` so the deploy pass
can read and rewrite them.

## Plan artifact
- `plans_dir: .opencode/plans/`
- Plan filename convention: `<slug>.md` (lowercase-kebab).

## Conventions
- Front end builds with Vite to `dist/` (own build — not Oryx).
- Deploy target is Azure Static Web Apps.
- The SWA deployment token is a secret; the Vite build runs before deploy.
