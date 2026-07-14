# Project rules — Phasewave (docs-adherence slice)

## Stack
`vue-supabase` — Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase
(Postgres + Auth + RLS), Vite build to `dist/`, Azure Static Web Apps
deploy. This is a fixture for the `validating-against-official-docs` skill:
the runnable stubs are a frozen doc copy + a workflow under
`.github/workflows/` so the validation pass can compare them.

## Plan artifact
- `plans_dir: .opencode/plans/`
- Plan filename convention: `<slug>.md` (lowercase-kebab).

## Conventions
- Validation is read-only on the artifact; emit `ADHERENCE.md`, don't edit.
- The frozen `official-docs.md` stands in for the live vendor doc (dated).
