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
- `.github/workflows/deploy.yml` is **intentionally identical** to the
  fixture in `skills/validating-against-official-docs/.../docs-adherence/`
  and is seeded **deliberately defective** (no `pull_request` preview,
  token in `vars`, missing `skip_app_build`). This skill *fixes* those gaps;
  `validating-against-official-docs` is the skill that *validates* them
  read-only. The shared defective workflow is a deliberate cross-skill
  coupling, not a copy-paste accident.
