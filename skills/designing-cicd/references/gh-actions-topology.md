# GitHub Actions Topology Reference

Read this at `designing-cicd` Steps 2–10 when drafting the workflow
topology. It is the field-level detail behind the skill's steps; the skill
body stays terse by linking here. One level deep, loaded only when needed.

## Contents

- Trigger / context matrix
- Job DAG via `needs`
- `concurrency` forms (queue vs cancel)
- `environment` + protection rules
- Secrets vs vars
- Caching vs artifacts
- Required checks + branch protection
- Migrate-before-deploy DAG
- Common findings (the red flags this skill catches)

## Trigger / context matrix

| Trigger | Fires on | Sees prod secrets? | Use for |
|---|---|---|---|
| `push` (to `main`) | every merge to main | yes | prod/release deploy, main validation |
| `pull_request` | open/update of a PR | no (PR refs are untrusted) | validation gate: test + build only |
| `workflow_run` | another workflow completed | yes (downstream) | deploy *after* CI passed; chain pipelines |
| `workflow_dispatch` | manual button | yes | promotion, rollback, one-off |

Rule: **never deploy prod from `pull_request`** — PR contexts cannot hold
protected secrets and must not have deploy power. Chain via `workflow_run`
(its `needs` is implicit: the upstream job completed) or gate a manual
`workflow_dispatch` behind an `environment`.

## Job DAG via `needs`

```yaml
jobs:
  test:    { runs-on: ubuntu-latest, steps: [ ... ] }
  build:   { runs-on: ubuntu-latest, needs: [test], steps: [ ... ] }
  migrate: { needs: [build], steps: [ ... ] }
  deploy:  { needs: [migrate], environment: production, steps: [ ... ] }
```

`needs` is a hard prerequisite — the dependent job waits. A missing
`needs: [migrate]` on `deploy` lets it race the migration. Each job the
next gate consumes (build artifact, migration result) must be in `needs`.

## `concurrency` forms

```yaml
# Non-prod / PR validation — drop stale runs
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

# Prod deploy — queue, never cancel mid-flight
concurrency:
  group: deploy-prod
  cancel-in-progress: false
```

- `cancel-in-progress: true` cancels the older in-flight run when a newer
  one starts. Right for throwaway PR validation; wrong for prod (leaves a
  half-shipped environment).
- `cancel-in-progress: false` queues the newer run behind the in-flight
  one (only one runs at a time per `group`). Use for any stateful deploy.
- Per-environment `group` (`deploy-prod` vs `deploy-staging`) so the two
  don't serialize each other.

A deploy job with no `concurrency` is a finding: two merges can ship
concurrently and corrupt shared state.

## `environment` + protection rules

```yaml
deploy:
  environment:
    name: production
    url: ${{ steps.deploy.outputs.url }}
```

`environment.name` must match a repo Environment whose protection rules
apply: **required reviewers**, **wait timer** (minutes), **deployment
branches** (restrict which refs may deploy). Set these in repo Settings →
Environments; the skill's plan *names* the environment + rules, the
implementer wires them. An ungated `production` environment is a finding.

## Secrets vs vars

- `${{ secrets.X }}` — encrypted, never logged, never echo-able. Deploy
  tokens, `SUPABASE_ACCESS_TOKEN`, cloud creds.
- `${{ vars.X }}` — plaintext config (region, project id, static URLs).
  Safe to print.

A credential placed in `vars` is a leak vector — route to `securing-ci`.
GitHub redacts secret *values* in logs only when sourced from `secrets`;
`echo "${{ vars.TOKEN }}"` prints it in cleartext.

## Caching vs artifacts

- **Cache** (`actions/cache`) — speed reinstalls: `~/.npm`, `node_modules`,
  build dirs. Keyed so a hit is real (don't share across incompatible
  versions).
- **Artifact** (`actions/upload-artifact` / `download-artifact`) — hand a
  *built bundle* from `build` to `deploy`. Deploy ships the exact artifact
  `test` validated (build-once). Rebuilding in `deploy` breaks provenance —
  a finding.

## Required checks + branch protection

The jobs that must block merge are **required status checks** in branch
protection. If the `pull_request` test job isn't *required*, a direct push
to `main` bypasses it. The plan names required checks so protection rules
match the DAG.

## Migrate-before-deploy DAG

```yaml
migrate: { needs: [build], concurrency: { group: migrate-prod, cancel-in-progress: false } }
deploy:  { needs: [migrate], environment: production }
```

- `migrate` runs **forward-only** migrations against the target DB, with
  its own `concurrency` (two `db push` runs must not overlap).
- `deploy` serves only after `migrate` is green.
- Deploy-before-migrate = old code against a new/old-mismatched schema →
  breakage. The skill treats it as a **blocker**.

## Common findings (red flags this skill catches)

| Finding | Severity |
|---|---|
| Prod deploy triggered from `pull_request` | blocker |
| `deploy` lacks `needs: [migrate]` (migrate-before-deploy violated) | blocker |
| Deploy job has no `concurrency` | major |
| Prod `concurrency.cancel-in-progress: true` (cancels in-flight deploy) | major |
| `production` environment ungated (no protection rules) | major |
| Token/credential stored in `vars` instead of `secrets` | blocker → `securing-ci` |
| Test gate not a required status check | major |
| Deploy rebuilds the artifact `build` already produced | minor |
| Matrix on the deploy job (parallel deploys) | major |
