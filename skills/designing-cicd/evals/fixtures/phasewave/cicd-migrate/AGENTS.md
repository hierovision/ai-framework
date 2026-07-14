# Project rules — Phasewave (cicd-migrate slice)

## Stack
`vue-supabase` — Vue 3 + TypeScript + Pinia + Vuetify 3, Supabase
(Postgres + Auth + RLS), Vitest (unit), Playwright (e2e). This is a
fixture for the `designing-cicd` skill: the runnable stubs are plain YAML
text under `.github/workflows/` so the design pass can read and rewrite
them.

## Plan artifact
- `plans_dir: .opencode/plans/`
- Plan filename convention: `<slug>.md` (lowercase-kebab).

## Verification commands (what the verify stage runs)
- Type check: `npm run type-check`
- Lint: `npm run lint`
- Unit/integration: `npm run test`

## Conventions
- CI topology lives in `.github/workflows/ci.yml`.
- Prod deploys must never run from `pull_request`; migrations must run
  before the deploy that serves traffic.
- Secrets come from `secrets.*`; non-sensitive config from `vars.*`.
