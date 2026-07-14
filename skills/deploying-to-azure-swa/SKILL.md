---
name: deploying-to-azure-swa
description: Deploy a static front end to Azure Static Web Apps from GitHub Actions — preview-per-PR environments, production promotion on push to main, capturing the `static_web_app_url` action output for e2e, `skip_app_build` vs Oryx build, and custom domains. Use whenever the user says "deploy to Azure SWA", "set up Azure Static Web Apps", "preview environment per PR", "azure static web app github action", or surfaces an SWA release needing design — even without saying "Azure". Pairs with designing-cicd (the topology) and writing-e2e-tests (run e2e against the PR preview URL); routes token safety to securing-ci. Not for the CI topology itself (designing-cicd), non-SWA clouds (deploying-with-supabase), or application code (implementing-features).
---

# Deploying to Azure SWA

Turn an Azure Static Web Apps release into a GitHub Actions workflow that a
separate build session can run cold. A deploy pass is **done** when the SWA
workflow exists (a plan artifact and/or a drafted workflow), the preview-
per-PR + production-promotion split is correct, and the user has approved
it. The skill is **gated** for the production promotion: it drafts the
workflow and stops; an `implementing-features` pass (or manual dispatch)
executes the deploy. Implementation of the topology routes to
`designing-cicd`.

This skill fills the **Azure SWA deploy step** for `designing-cicd`'s
topology. It owns SWA-specific mechanics.

## The deploy pass

Copy this checklist and check off items as you complete them.

```
Azure SWA Deploy Progress:
- [ ] 1. Identify the SWA project + the build output location
- [ ] 2. Use the Azure SWA GitHub Action
- [ ] 3. Preview-per-PR: a pull_request job builds a preview env
- [ ] 4. Production promotion: push to main promotes (not the PR)
- [ ] 5. Capture `static_web_app_url` for e2e (link writing-e2e-tests)
- [ ] 6. skip_app_build vs Oryx (own build vs framework auto-build)
- [ ] 7. Custom domains via SWA config / azure CLI (not the action)
- [ ] 8. Secrets: the SWA deployment token from secrets
- [ ] 9. Present workflow + approval question; STOP (don't promote)
```

### Step 1 — Project + build output

The SWA project has an API token (from the SWA portal / `az staticwebapp`),
and the app build outputs to a known location (`dist/`, `build/`). The plan
names both. `app_location` is the source root; `output_location` is the
built asset dir.

### Step 2 — The Azure SWA action

Use `Azure/static-web-apps-deploy@v1`. The wizard-generated workflow is the
canonical shape; the skill's job is to get the **trigger split** and
**build mode** right, not to reinvent the action.

### Step 3 — Preview-per-PR

SWA auto-creates a **preview environment per PR** when the workflow runs on
`pull_request`. The `pull_request` job (or the `if: github.event_name ==
'pull_request'` branch of a shared job) produces an isolated preview URL —
no manual env wiring needed. A workflow with **no `pull_request` trigger**
ships no previews; a finding.

### Step 4 — Production promotion

Production deploys on **`push` to `main`**, never from `pull_request`
(PR refs must not hold the prod deployment token). The `push` job promotes;
the `pull_request` job only previews. A workflow that promotes prod from a
PR is a **blocker** (`securing-ci` territory — untrusted refs with deploy
power).

### Step 5 — Capture `static_web_app_url`

The action emits `static_web_app_url` as a step output. Capture it
(`id: swa` → `steps.swa.outputs.static_web_app_url`) so `writing-e2e-tests`
can run the e2e suite **against the PR preview** — the canonical "run e2e
against the PR preview" setup. The plan notes this handoff so e2e has a
real URL to target.

### Step 6 — `skip_app_build` vs Oryx

- **`skip_app_build: true`** — you run your own build (Vite, Next custom,
  etc.) and hand SWA the `output_location` assets. Required when the app's
  build is not Oryx-auto-detectable or you already build in a prior job.
- **Oryx (default)** — SWA auto-builds supported frameworks if you don't
  skip. Use it only when the framework is Oryx-supported and you want SWA
  to build. A Vite/other app left to Oryx double-builds or misbuilds —
  set `skip_app_build: true`.

### Step 7 — Custom domains

Configure custom domains in the SWA config / Azure CLI, **not** in the
deploy action. The action deploys the app; DNS/CNAME for the domain is a
separate, idempotent `az` step or portal setting. The plan keeps domain
config out of the hot deploy path.

### Step 8 — Secrets

The SWA deployment token (`AZURE_STATIC_WEB_APPS_API_TOKEN` / your named
secret) is a **secret** (`${{ secrets.X }}`). A token in `vars`, or echoed,
is a leak — route to `securing-ci`.

### Step 9 — Present + STOP

Hand back: the trigger split (PR preview / push prod), `skip_app_build`
decision, the `static_web_app_url` capture for e2e, and the secret token
source. End with the approval question. **Do not promote prod** — the user
approves, then an `implementing-features` pass executes the deploy.

## When not to use this skill

- **CI topology / triggers / job DAG** — `designing-cicd`.
- **Token / secret hardening** — `securing-ci`.
- **Non-SWA clouds** — `deploying-with-supabase` (Supabase).
- **Running e2e against the preview** — `writing-e2e-tests` (this skill
  hands it the `static_web_app_url`).
- **Application code** — `implementing-features`.

## References

- [references/azure-swa.md](references/azure-swa.md) — the SWA action
  shape, preview-vs-prod trigger split, `skip_app_build` vs Oryx, and the
  `static_web_app_url` capture. Read at Steps 2–8 when drafting the
  workflow.
- Azure docs: *Build configuration for Azure Static Web Apps*, *Deploy to
  Azure Static Web Apps* (authoritative for any field this skill
  summarizes — verify against current docs via
  `validating-against-official-docs` when in doubt).
