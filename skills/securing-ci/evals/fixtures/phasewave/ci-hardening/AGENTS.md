# Project rules — Phasewave (ci-hardening slice)

## Stack
`vue-supabase` — Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase
(Postgres + Auth + RLS), Vite build, Vitest (unit), Playwright (e2e).
This is a fixture for the `securing-ci` skill: the runnable stub is plain
YAML under `.github/workflows/` so the hardening pass can read and rewrite
it.

## Plan artifact
- `plans_dir: .opencode/plans/`
- Plan filename convention: `<slug>.md` (lowercase-kebab).

## Conventions
- CI must not expose credentials; third-party actions are pinned.
- Prod deploy tokens are environment secrets, not repo-wide.
