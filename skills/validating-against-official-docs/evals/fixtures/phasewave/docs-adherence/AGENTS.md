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
- `.github/workflows/deploy.yml` is **intentionally identical** to the
  fixture in `skills/deploying-to-azure-swa/.../azure-swa/` and is left
  **deliberately defective** (no `pull_request` preview, token in `vars`,
  missing `skip_app_build`). This skill *validates* those gaps (eval-1);
  `deploying-to-azure-swa` is the skill that *fixes* them. Do not "repair"
  deploy.yml here — leaving it broken on disk is correct (the skill is
  read-only and routes fixes away).
