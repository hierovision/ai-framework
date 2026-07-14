# CI Hardening Reference

Read this at `securing-ci` Steps 2–8 when drafting the hardened workflow.
Field-level detail behind the skill's steps; loaded only when needed. One
level deep.

## Contents

- Secret inventory
- OIDC over PATs
- Environment-secret scoping
- Never log secrets
- Least-privilege token scopes
- Minimal `permissions:`
- Branch protection on required checks
- SHA-pinning third-party actions
- Common findings

## Secret inventory

List every `secrets.X` / `vars.X`, what it unlocks, and its required scope.
An un-inventoried secret is an un-reviewed risk.

## OIDC over PATs

```yaml
permissions:
  id-token: write   # enables OIDC exchange
  contents: read
steps:
  - uses: azure/login@v1
    with:
      client-id: ${{ vars.AZURE_CLIENT_ID }}
      tenant-id: ${{ vars.AZURE_TENANT_ID }}
      # no client-secret — OIDC mints a short-lived token
```

OIDC mints a short-lived token at run time. A static `secrets.*` PAT that
OIDC could replace is a finding.

## Environment-secret scoping

Put deploy tokens in **environment secrets** (repo Settings → Environments
→ `production` → Environment secrets), readable only by jobs that
reference `environment: production`. Repo-wide secrets are readable by
every workflow/job — a finding for prod tokens.

## Never log secrets

`echo "token is ${{ secrets.X }}"` prints cleartext — GitHub redacts
`secrets.*` only when used as a value, not when concatenated/echoed. A
workflow that echoes a secret is a blocker. Use a masked dry-run or skip
logging the token entirely.

## Least-privilege token scopes

- Supabase: use the **deploy** token, not a full admin/service token.
- Cloud: a scoped deploy role, not owner.
A token broader than the step needs is a finding.

## Minimal `permissions:`

```yaml
permissions:
  contents: read
  id-token: write     # only if OIDC
  packages: write     # only if publishing
```

`permissions: write-all` is a blanket grant a compromised step can abuse —
**blocker**. Default is `read-all`; grant only what the workflow needs.

## Branch protection on required checks

Required status checks in branch protection must list the `pull_request`
validation jobs. If a direct push to `main` can bypass the test gate, the
check isn't required — a finding.

## SHA-pinning third-party actions

```yaml
# SHA-pinned (gold standard)
- uses: actions/checkout@<40-char-sha> # v4.2.0
# Acceptable: major tag
- uses: actions/checkout@v4
# Forbidden: floating ref
- uses: actions/checkout@main      # supply-chain risk
```

Pin to a commit SHA (with a `# vX.Y.Z` comment) or, at minimum, a major
tag. `@main` / `@master` / `@latest` runs whatever upstream publishes next
— **blocker**. First-party `actions/*` is pinned too.

## Common findings (red flags this skill catches)

| Finding | Severity |
|---|---|
| `echo` of a `secrets.*` value (cleartext leak) | blocker |
| `permissions: write-all` (blanket grant) | blocker |
| Third-party action pinned to `@main`/`@master`/`@latest` | blocker |
| Static PAT where OIDC is available | major |
| Prod token in repo-wide secrets (not environment-scoped) | major |
| Token broader than the step needs (admin vs deploy) | major |
| Required check bypassable by direct push (not branch-protected) | major |
