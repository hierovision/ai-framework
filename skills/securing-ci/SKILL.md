---
name: securing-ci
description: Harden CI/CD pipelines for least-privilege and supply-chain safety — prefer OIDC over long-lived PATs, scope secrets to environments, never log secrets, minimize workflow `permissions:`, enforce branch protection on required checks, and SHA-pin third-party actions. Use whenever the user says "secure the CI", "harden github actions", "why is this token exposed", "pin third-party actions", "least-privilege CI", or surfaces a pipeline-credential/security concern — even without saying "security". Pairs with designing-cicd (the topology it hardens) and the Supabase/Azure deploy skills (their tokens); routes design-only review of a diff to reviewing-code. Not for the CI topology itself (designing-cicd), application code (implementing-features), or multi-lens council review (shipped as `agents/council.md`; defaults to free models, paid opt-in).
---

# Securing CI

Turn a CI/CD pipeline's credential and supply-chain posture into a hardened
configuration a separate build session can implement cold. A hardening pass
is **done** when every token is least-privilege, no secret can leak through
logs, third-party actions are pinned, and required checks are branch-
protected — and the user has approved it. The skill is **read-mostly /
gated**: it reviews the workflow, proposes the hardened version, and stops
at approval; it does not rewrite source or run deployments. Implementation
routes to `implementing-features`.

This skill owns the **security posture** of the pipelines `designing-cicd`
designs and `deploying-with-supabase` / `deploying-to-azure-swa` fill.

## The hardening pass

Copy this checklist and check off items as you complete them.

```
CI Security Progress:
- [ ] 1. Inventory every secret/token the workflow uses
- [ ] 2. Prefer OIDC over long-lived PATs (no static credentials in secrets)
- [ ] 3. Scope secrets to environments (env-level, not repo-wide)
- [ ] 4. Never log secrets; rely on secrets.* redaction
- [ ] 5. Least-privilege token scopes (deploy token, not admin token)
- [ ] 6. Minimize workflow `permissions:` (default read; grant only needed)
- [ ] 7. Branch protection on required checks (can't be skipped)
- [ ] 8. SHA-pin third-party actions (not @main / @v1 floating)
- [ ] 9. Present hardened workflow + findings; STOP
```

### Step 1 — Inventory secrets

List every `secrets.X` / `vars.X` the workflow reads and what each unlocks
(deploy, cloud login, registry push). An un-inventoried secret is an
un-reviewed risk. The plan names each.

### Step 2 — OIDC over PATs

Prefer **OIDC** (`permissions: id-token: write` + a cloud OIDC provider) so
the workflow gets a short-lived token at run time — no long-lived PAT
stored in `secrets`. A static `secrets.*` credential that OIDC could
replace is a finding. Where OIDC isn't available, the static token must be
least-privilege and rotated.

### Step 3 — Scope secrets to environments

Put deploy tokens in **environment secrets**, not repo-wide secrets, so
only the gated `production` environment (with its reviewers + wait timer)
can read them. A prod token readable by every job in every workflow is a
finding.

### Step 4 — Never log secrets

`echo "${{ secrets.X }}"` prints the value in cleartext (GitHub redacts
`secrets.*` only when the value is *used as a value*, not when you string-
concatenate and echo it). A workflow that echoes a secret is a **blocker**.
Route any "debug the token" urge to a masked/short-lived log or a dry-run.

### Step 5 — Least-privilege token scopes

A Supabase deploy needs the **deploy** token, not a full admin token; a
cloud deploy needs a scoped role, not owner. A token with broader scope
than the step needs is a finding (`deploying-with-supabase` /
`deploying-to-azure-swa` own the token choice — this skill checks its
scope).

### Step 6 — Minimize `permissions:`

Workflows default to `read-all`; a top-level `permissions: write-all` is a
blanket grant a compromised step can abuse. Set an explicit minimal block
(`contents: read`, `id-token: write` for OIDC, `packages: write` only if
publishing). `permissions: write-all` is a **blocker**.

### Step 7 — Branch protection on required checks

A `pull_request` test job that isn't a **required status check** can be
skipped by a direct push to `main`. The hardening pass names which jobs
must be required so branch protection matches the DAG (`designing-cicd`
owns the DAG; this step enforces the gate can't be bypassed).

### Step 8 — SHA-pin third-party actions

A third-party action pinned to `@main` / `@head` / `@latest` runs
**whatever the upstream publishes next** — a supply-chain risk. Pin to a
**commit SHA** (`uses: owner/repo@<sha>` with a `# vX.Y.Z` comment) or, at
minimum, a major tag. `@main` / `@head` / `@latest` is a **blocker**.
First-party `actions/*` still gets pinned to a major or SHA.

### Step 9 — Present + STOP

Hand back: the secret inventory + each token's privilege, the OIDC
decision, environment scoping, the `permissions:` block, required-check
enforcement, and the action-pin list. End with the approval question. Do
**not** rewrite the workflow into `.github/` or run anything — the user
approves, then an `implementing-features` pass applies it (or a
`reviewing-code` pass checks the diff against this design).

## When not to use this skill

- **CI topology / triggers / job DAG** — `designing-cicd`.
- **The deploy step's cloud specifics (tokens)** — `deploying-with-supabase`
  / `deploying-to-azure-swa` (this skill audits their privilege/scope).
- **Reviewing a CI diff** — `reviewing-code` (checks the hardened workflow
  against this design's plan).
- **Application code** — `implementing-features`.
- **Multi-lens council review** — `agents/council.md` (shipped,
  defaults to free models with a paid opt-in); this skill is
  single-discipline security hardening.

## References

- [references/ci-hardening.md](references/ci-hardening.md) — OIDC setup
  sketch, environment-secret scoping, the `permissions:` minimal block,
  SHA-pinning format, and the required-check enforcement. Read at Steps
  2–8 when drafting the hardened workflow.
- GitHub docs: *Security hardening for GitHub Actions* (authoritative for
  any field this skill summarizes — verify against current docs via
  `validating-against-official-docs` when in doubt).
