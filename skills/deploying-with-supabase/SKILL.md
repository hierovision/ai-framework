---
name: deploying-with-supabase
description: Deploy to Supabase from CI — `supabase db push` forward-only semantics, "only one db push at a time" concurrency, migrations in CI via session-mode `--db-url` vs `link` + `SUPABASE_ACCESS_TOKEN`, Supabase Branching for preview envs, staging-canary, pgaudit / audit-logging safety, and declarative schemas applied via CLI. Use whenever the user says "run supabase migrations in CI", "set up supabase deploy", "db push in GitHub Actions", "supabase preview environment", or surfaces a Supabase release needing design — even without saying "Supabase". Pairs with designing-cicd (the topology) and securing-ci (token hardening); routes review of the resulting workflow to reviewing-code. Not for the CI topology itself (designing-cicd), application code (implementing-features), or non-Supabase clouds (deploying-to-azure-swa).
---

# Deploying with Supabase

Turn a Supabase release into a CI-safe migration + deploy that a separate
build session can run cold. A deploy pass is **done** when the migration-in-
CI config exists (a plan artifact and/or a drafted workflow), the
forward-only + single-push-at-a-time invariants hold, and the user has
approved it. The skill is **gated**: it does not run `supabase db push`
itself — a migration is stateful and irreversible-ish, so it stops and asks
before any push. Implementation routes to `implementing-features`.

This skill fills the **Supabase-specific deploy step** that `designing-cicd`
designs the topology around. It owns the migration mechanics; it does not
re-decide triggers or job DAGs (that is `designing-cicd`).

## The deploy pass

Copy this checklist and check off items as you complete them.

```
Supabase Deploy Progress:
- [ ] 1. Identify target project ref + environment (staging / prod)
- [ ] 2. Choose migration mode (link + token vs session-mode --db-url)
- [ ] 3. Enforce forward-only migrations (never patch an applied migration)
- [ ] 4. Serialize db push (concurrency: one push at a time)
- [ ] 5. Order migrate-before-deploy (hand off to designing-cicd DAG)
- [ ] 6. Supabase Branching for PR preview envs
- [ ] 7. Staging-canary: staging first, then prod
- [ ] 8. pgaudit / audit logging — keep on, additive only
- [ ] 9. Declarative schemas (config) via CLI, not by hand
- [ ] 10. Secrets: SUPABASE_ACCESS_TOKEN / DB URL from secrets
- [ ] 11. Present config + approval question; STOP (do not push)
```

### Step 1 — Target project ref + environment

Each environment (staging, prod) is a distinct Supabase project with its own
`project-ref` and DB URL. The plan names both. Never point a prod workflow
at a staging ref.

### Step 2 — Choose migration mode

Two ways to authenticate the CLI in CI (see
[references/supabase-ci.md](references/supabase-ci.md) for the exact
invocations):

- **`link` + `SUPABASE_ACCESS_TOKEN`** — the standard CI path. `supabase
  link --project-ref <ref>` then `supabase db push`. The token is a
  **secret** (`${{ secrets.SUPABASE_ACCESS_TOKEN }}`); it must never sit in
  `vars` or be echoed.
- **session-mode `--db-url`** — for ephemeral / preview DBs: `supabase db
  push --db-url "${{ secrets.SUPABASE_DB_URL }}"` without linking. Useful in
  Supabase Branching preview flows.

Pick per environment; document which the plan uses.

### Step 3 — Forward-only migrations

`supabase db push` applies **new** migration files forward-only. The skill's
hard rules:

- Never edit or re-order an already-applied migration — that desyncs the
  `_supabase_migrations` history from the DB.
- To change something a prior migration did, write a **new** migration that
  undoes/alters it.
- A workflow that patches a committed migration file before pushing is a
  **blocker** (it silently corrupts migration history).

### Step 4 — Serialize db push (one at a time)

Two `db push` runs against the same project in parallel corrupt migration
history. The migrate job **must** have `concurrency`:

```yaml
migrate:
  concurrency:
    group: supabase-migrate-${{ env.ENV }}   # one push per env, at a time
    cancel-in-progress: false
```

A migrate job with a `matrix` (parallel pushes across regions) or no
`concurrency` is a finding. Serialize — do not parallelize — the push.

### Step 5 — Migrate-before-deploy

The migrate job is a prerequisite of the deploy job in the DAG
(`designing-cicd` owns this). `deploy` `needs: [migrate]`; new code serves
only after the schema it expects exists. A Supabase deploy that runs
`db push` after `./deploy` is the same cardinal violation as in
`designing-cicd` — **blocker**.

### Step 6 — Supabase Branching for previews

For PR preview environments, use Supabase Branching: create a branch
(`supabase branches create`) per PR, run migrations against the branch DB
(`--db-url` to the branch URL), deploy the preview app there, tear down on
PR close. This keeps prod schema untouched by preview churn. The plan names
the branch lifecycle.

### Step 7 — Staging-canary

Ship schema + code to **staging first**, let it bake (smoke tests, a
canary window), then promote to prod. Two separate `environment`s
(`staging`, `production`) with their own protection rules. A plan that
deploys straight to prod with no staging gate is a major (lost canary
signal) unless the user explicitly opts out.

### Step 8 — pgaudit / audit logging

Keep audit logging **on** in every environment. Do not disable `pgaudit` or
row-level audit triggers to "simplify" a migration — that is a security
finding (`securing-ci` territory). Additive audit changes (new table
tracked) are fine; removing audit coverage is not.

### Step 9 — Declarative schemas (config)

Auth / storage / RLS-policy config lives in `supabase/config.toml` and is
applied via `supabase db push` / the CLI — not hand-clicked in the dashboard
(nothing reproducible survives a dashboard click). The plan treats config
as code; the schema source of truth is the migration files + `config.toml`.

### Step 10 — Secrets

`SUPABASE_ACCESS_TOKEN` and the DB URL/password come from `secrets`. The CLI
printing a token is a leak; GitHub redacts `secrets.*` values but only if
sourced correctly. Route any token-hardening question to `securing-ci`.

### Step 11 — Present + STOP

Hand back: the migration mode per env, the serialized `concurrency` group,
the migrate-before-deploy ordering, the branching/preview lifecycle, and the
staging-canary gate. End with the approval question. **Do not run `supabase
db push`** — a migration is stateful; the user approves, then an
`implementing-features` pass (or a manual dispatch) executes it.

## When not to use this skill

- **CI topology / triggers / job DAG** — that is `designing-cicd`. This
  skill fills the Supabase deploy step, it does not re-pick triggers.
- **Token / secret hardening** — `securing-ci`.
- **Non-Supabase clouds** — `deploying-to-azure-swa` (Azure SWA).
- **Application code** — `implementing-features`.

## References

- [references/supabase-ci.md](references/supabase-ci.md) — exact CLI
  invocations (`link` + token, session-mode `--db-url`), the serialized
  `concurrency` pattern, branching commands, and the forward-only rules.
  Read at Steps 2–9 when drafting the migration config.
- Supabase docs: *CLI Reference*, *Database Migrations*, *Branching*
  (authoritative for any field this skill summarizes — verify against
  current docs via `validating-against-official-docs` when in doubt).
