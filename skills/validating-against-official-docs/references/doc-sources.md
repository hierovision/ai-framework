# Doc Sources Reference

Read this at `validating-against-official-docs` Step 2 when picking the
authoritative source. The vendor's own docs — not blogs or Q&A. URLs are
dated references; re-fetch when a deprecation or version change is
suspected (see `reference/model-routing.md` Deprecation watch for the
cadence habit). One level deep.

## Contents

- GitHub Actions
- Supabase
- Azure Static Web Apps
- What each validates

## GitHub Actions

- *Events that trigger workflows* — which triggers fire a workflow and
  what context/secrets they expose (PR refs are untrusted; prod secrets
  live behind `push` / `workflow_run` / `workflow_dispatch`).
- *Environments* — `environment:` + protection rules (required reviewers,
  wait timer, deployment branches).
- *Concurrency* — `group` + `cancel-in-progress` semantics (queue vs
  cancel an in-flight deploy).
- *Security hardening for GitHub Actions* — OIDC vs PAT, `permissions:`
  minimization, secret logging, SHA-pinning third-party actions.

## Supabase

- *CLI Reference* — `supabase link`, `supabase db push`, `supabase
  branches` invocations.
- *Database Migrations* — forward-only semantics; never edit an applied
  migration.
- *Branching* — per-branch preview DBs for PR previews.

## Azure Static Web Apps

- *Build configuration for Azure Static Web Apps* — `app_location`,
  `output_location`, `skip_app_build` vs Oryx.
- *Deploy to Azure Static Web Apps* — the `Azure/static-web-apps-deploy`
  action, preview-per-PR, `static_web_app_url` output, deployment token.

## What each validates

| Source | Validates |
|---|---|
| GitHub *Events that trigger workflows* | trigger/secret trust boundary (no prod deploy from PR) |
| GitHub *Concurrency* | one-deploy-at-a-time, queue-not-cancel for prod |
| GitHub *Environments* | prod gated by protection rules |
| GitHub *Security hardening* | OIDC, minimal `permissions:`, no secret echo, pinned actions |
| Supabase *Database Migrations* | forward-only; serialized `db push` |
| Supabase *Branching* | preview DBs per PR |
| Azure SWA *Build configuration* | `skip_app_build` for own-build apps |
| Azure SWA *Deploy* | preview-per-PR, push-promotion, token-in-secrets |
