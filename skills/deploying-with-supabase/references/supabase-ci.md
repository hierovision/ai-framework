# Supabase CI Reference

Read this at `deploying-with-supabase` Steps 2–9 when drafting the
migration config. Field-level detail behind the skill's steps; loaded only
when needed. One level deep.

## Contents

- Migration modes (link + token vs session-mode --db-url)
- Serialized db push (concurrency)
- Forward-only rules
- Supabase Branching (preview envs)
- Staging-canary
- pgaudit / audit-logging safety
- Declarative schema via CLI
- Common findings

## Migration modes

**link + SUPABASE_ACCESS_TOKEN (standard CI):**

```yaml
env:
  SUPABASE_ACCESS_TOKEN: ${{ secrets.SUPABASE_ACCESS_TOKEN }}
steps:
  - run: supabase link --project-ref ${{ vars.SUPABASE_PROJECT_REF }}
  - run: supabase db push
```

The token is a secret. `vars.SUPABASE_PROJECT_REF` is non-sensitive config
(safe in `vars`). Never echo the token.

**session-mode --db-url (ephemeral / preview):**

```yaml
steps:
  - run: supabase db push --db-url "${{ secrets.SUPABASE_DB_URL }}"
```

No `link` needed — pointed straight at a DB URL (branch URL in preview
flows). Use for Supabase Branching previews.

## Serialized db push (concurrency)

```yaml
migrate:
  concurrency:
    group: supabase-migrate-${{ env.ENV }}
    cancel-in-progress: false
```

One push per environment at a time. A `matrix` on the migrate job (parallel
pushes across regions) corrupts migration history — **forbidden**. No
`concurrency` on migrate = two merges push concurrently = corrupt history.

## Forward-only rules

- `supabase db push` applies new migration files forward-only.
- Never edit/reorder an applied migration; write a new one to alter.
- Patching a committed migration before pushing = blocker (history desync).

## Supabase Branching (preview envs)

```yaml
steps:
  - run: supabase branches create preview-${{ github.event.pull_request.number }} || true
  - run: supabase db push --db-url "${{ secrets.PREVIEW_DB_URL }}"
```

Create a branch per PR, migrate it, deploy the preview app, tear down on PR
close (`supabase branches delete ...`). Prod schema stays untouched by
preview churn.

## Staging-canary

Two `environment`s — `staging` then `production`. Migrate + deploy staging,
bake (smoke tests / canary window), then promote prod. No staging gate
(straight-to-prod) is a major unless the user opts out.

## pgaudit / audit-logging safety

Keep `pgaudit` and row-level audit triggers **on** in every environment.
Do not disable audit logging to simplify a migration — security finding.
Additive audit changes (track a new table) are fine; removing coverage is
not.

## Declarative schema via CLI

`supabase/config.toml` (auth / storage / RLS config) is applied via the CLI
/ `db push` — not hand-clicked in the dashboard. Config is code; the schema
source of truth is the migration files + `config.toml`.

## Common findings (red flags this skill catches)

| Finding | Severity |
|---|---|
| `db push` with no `concurrency` (parallel pushes possible) | blocker |
| `matrix` on the migrate job (parallel pushes) | blocker |
| `deploy` lacks `needs: [migrate]` (migrate-before-deploy violated) | blocker |
| Edit/reorder an applied migration before push | blocker |
| `SUPABASE_ACCESS_TOKEN` in `vars` / echoed | blocker → `securing-ci` |
| No staging-canary gate (straight to prod) | major |
| pgaudit / audit logging disabled in a migration | blocker |
| Config changed via dashboard, not `config.toml` | minor |
