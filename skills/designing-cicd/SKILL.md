---
name: designing-cicd
description: Design GitHub Actions CI/CD topology — trigger selection (push / pull_request / workflow_run / workflow_dispatch), job sequencing via needs, concurrency (queue vs cancel-in-progress), environment protection rules, secrets vs vars, matrix, caching/artifacts, and required checks. Golden paths test → build → deploy and migrate-before-deploy. Use whenever the user asks "how should CI work", "sequence deploy vs migration", "gate prod", "set up GitHub Actions", or surfaces a release/operate pipeline needing design — even without saying "CI/CD". Routes implementation to implementing-features; pairs with deploying-with-supabase / deploying-to-azure-swa for the deploy step and securing-ci for token/secret safety. Not for writing application code (implementing-features), reviewing a diff (reviewing-code), or authoring tests (the test trio).
---

# Designing CI/CD

Turn a release/operate pipeline into a verifiable GitHub Actions topology
that a separate build session can implement cold. A design pass is **done**
when the workflow topology exists (as a plan artifact and/or a drafted
workflow file), every gate is an observable, checkable rule, and the user
has approved it. The skill is **design-only** — it does not commit, edit
source, or run deployments. It stops at approval; implementation routes to
`implementing-features`.

This skill closes the library's release/operate gap: no other skill
covers CI topology, job DAGs, `concurrency`, `environment` protection, or
deploy-vs-migrate ordering.

## The design pass

Copy this checklist and check off items as you complete them.

```
CI/CD Design Progress:
- [ ] 1. Identify the pipeline's purpose + which triggers fire it
- [ ] 2. Select triggers (push / pull_request / workflow_run / workflow_dispatch)
- [ ] 3. Build the job DAG via `needs`
- [ ] 4. Add `concurrency` (one deploy at a time; queue, don't cancel prod)
- [ ] 5. Add `environment` + protection rules (reviewers / wait timer / deploy branches)
- [ ] 6. Separate secrets from vars
- [ ] 7. Choose matrix dimensions (only where it speeds feedback)
- [ ] 8. Wire caching + artifacts (reuse, don't rebuild)
- [ ] 9. Mark required checks + branch protection
- [ ] 10. Apply the migrate-before-deploy golden path
- [ ] 11. Present topology + approval question; STOP
```

### Step 1 — Identify purpose + trigger set

Name what the pipeline delivers (test gate, preview deploy, prod release,
migration). Pick triggers deliberately — each has a distinct failure mode:

- `push` to `main` — fires on every merge; the usual prod/release trigger.
- `pull_request` — the validation gate (test + build) before merge; never
  the deploy trigger for prod (PR refs can't see protected secrets).
- `workflow_run` — chain a downstream workflow (e.g. deploy) after an
  upstream one (e.g. CI) completes; the correct way to "deploy after CI
  passed" without polluting the PR trigger.
- `workflow_dispatch` — manual promotion / rollback; pairs with an
  `environment` and protection rules.

Do **not** deploy from `pull_request` with production secrets — PRs from
forks/branches must not hold deploy power. Route deploy through
`workflow_run` or `workflow_dispatch`.

### Step 2 — Select triggers

Map each chosen trigger to a job group (see
[references/gh-actions-topology.md](references/gh-actions-topology.md) for
the event/context matrix). A pipeline usually needs: a `pull_request`
validation job, a `push`/`workflow_run` deploy job, and an optional
`workflow_dispatch` promotion job. List the triggers in the plan so an
implementer doesn't guess.

### Step 3 — Build the job DAG via `needs`

Jobs run in parallel by default; `needs:` makes them a DAG. Common shape:

```
test  ─┐
build ─┼─▶ deploy          (deploy waits for both)
migrate─┘
```

Every job a later gate depends on must be named in `needs`. A deploy that
does not `needs:` the migrate job can race it — the cardinal ordering bug.

### Step 4 — Add `concurrency`

Prevent overlapping runs from clobbering the same environment:

```yaml
concurrency:
  group: deploy-prod-${{ github.ref }}
  cancel-in-progress: false   # queue, don't cancel an in-flight prod deploy
```

- **Non-prod / PR validation**: `cancel-in-progress: true` is fine (drop
  stale runs on new pushes).
- **Prod deploy**: `cancel-in-progress: false` — queue new runs behind the
  in-flight one. Cancelling a prod deploy mid-flight leaves a half-shipped
  environment. Use a per-environment `group` so staging and prod don't
  serialize each other.

A topology with no `concurrency` on deploy is a finding (two merges can
ship concurrently and corrupt state).

### Step 5 — Add `environment` + protection rules

Gate prod with a named `environment` so GitHub enforces protection rules:

```yaml
deploy:
  environment:
    name: production
    url: ${{ steps.deploy.outputs.url }}
  needs: [test, build, migrate]
```

Protection rules (set in repo Settings → Environments, referenced here by
name): required reviewers, wait timer, and restricted deployment branches.
The plan should name the environment and which rules apply — an
ungated `production` environment is a finding.

### Step 6 — Separate secrets from vars

- **Secrets** (`${{ secrets.X }}`) — never logged, never echoable. Deploy
  tokens, `SUPABASE_ACCESS_TOKEN`, cloud credentials.
- **Vars** (`${{ vars.X }}`) — non-sensitive config (region, project id,
  static URLs). Safe to print in logs.

The plan lists each value as secret or var; a token placed in `vars` is a
security finding (route to `securing-ci`). Never `echo` a secret; GitHub
redacts secret values in logs but only if they came from `secrets`.

### Step 7 — Choose matrix dimensions

A `matrix` parallelizes (OS × Node version, schema variants). Use it for
the test gate to widen coverage cheaply. Do **not** matrix the deploy job —
exactly one deploy per environment. A matrix deploy is a concurrency
explosion, not parallelism.

### Step 8 — Wire caching + artifacts

- **Caching** (`actions/cache`) — dependency installs (`~/.npm`,
  `node_modules`), build outputs; keyed so hits are real.
- **Artifacts** (`actions/upload-artifact`) — hand a built bundle from
  `build` to `deploy` so deploy doesn't rebuild. The build-once principle:
  the artifact deploy ships is the one tests validated.

A topology that rebuilds in `deploy` what `build` already produced breaks
provenance — a finding.

### Step 9 — Required checks + branch protection

List which jobs are **required status checks** (repo branch protection).
A `pull_request` test job that isn't a required check can be skipped by a
direct push to `main` — gate closed only on paper. The plan names the
required checks so protection rules can be set to match.

### Step 10 — Migrate-before-deploy (golden path)

When a deploy changes schema, the migration **must** complete before the
new code serves traffic:

```
migrate (needs: build-artifact)  ──▶  deploy (needs: migrate)
```

- `migrate` applies forward-only migrations (`supabase db push` / SQL
  migrations) against the target DB.
- `deploy` ships code only after `migrate` is green.
- The reverse order (deploy first, migrate after) serves old code against a
  schema it doesn't expect → breakage. The skill treats deploy-before-migrate
  as a **blocker** in any topology it reviews.
- `migrate` itself needs `concurrency` so two migrations never run at once
  (forward-only `db push` is not safe to parallelize — see
  `deploying-with-supabase`).

### Step 11 — Present topology + approval; STOP

Hand back: the trigger table, the job DAG (as a list or diagram), each
gate's observable rule (concurrency group, environment name + protection,
required checks), and the migrate-before-deploy ordering. End with the
approval question ("Approve this topology, or want revisions?"). Do **not**
write the workflow file into the repo's `.github/` unless the user asks —
design stops at the approved plan; implementation is a separate
`implementing-features` pass (or a drafted workflow the user approves).

## When not to use this skill

- **Writing application code** — that is `implementing-features`.
- **Reviewing a CI diff** — that is `reviewing-code` (it checks the
  topology against this design's plan).
- **Authoring tests** — the test trio (`writing-unit-tests` /
  `writing-integration-tests` / `writing-e2e-tests`) owns the test gate's
  contents; this skill decides *where/whether* e2e runs (e.g. against a PR
  preview from `deploying-to-azure-swa`).
- **The deploy step's cloud specifics** — Supabase → `deploying-with-supabase`;
  Azure SWA → `deploying-to-azure-swa`. This skill designs the topology;
  those skills fill the deploy job.
- **Token / secret safety** — `securing-ci` owns least-privilege and
  SHA-pinning; this skill names the gates, not the credential hardening.

## References

- [references/gh-actions-topology.md](references/gh-actions-topology.md) —
  the trigger/context matrix, `concurrency` forms, `environment` protection
  options, secrets-vs-vars, and the migrate-before-deploy DAG. Read at
  Steps 2–10 when drafting the topology.
- GitHub docs: *Events that trigger workflows*, *Environments*,
  *Concurrency* (the authoritative source for any field this skill
  summarizes — verify against current docs via
  `validating-against-official-docs` when in doubt).
