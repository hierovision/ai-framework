# Azure SWA Reference

Read this at `deploying-to-azure-swa` Steps 2–8 when drafting the workflow.
Field-level detail behind the skill's steps; loaded only when needed. One
level deep.

## Contents

- The SWA action shape
- Preview-per-PR vs production promotion (trigger split)
- Capturing `static_web_app_url`
- `skip_app_build` vs Oryx
- Custom domains
- Secrets
- Common findings

## The SWA action shape

```yaml
- uses: Azure/static-web-apps-deploy@v1
  id: swa
  with:
    azure_static_web_apps_api_token: ${{ secrets.SWA_TOKEN }}
    repo_token: ${{ secrets.GITHUB_TOKEN }}
    action: "upload"
    app_location: "/"
    output_location: "dist"
    skip_app_build: true
```

Pin the action to a major tag (`@v1`), not a floating `@main` — see
`securing-ci` on SHA/tag pinning.

## Preview-per-PR vs production promotion

```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
jobs:
  deploy:
    steps:
      - uses: Azure/static-web-apps-deploy@v1
        with:
          # SWA auto-detects event_name: PR -> preview env, push -> promote
          azure_static_web_apps_api_token: >-
            ${{ github.event_name == 'pull_request'
                && secrets.SWA_PREVIEW_TOKEN
                || secrets.SWA_TOKEN }}
```

SWA gives **one preview URL per PR** automatically when the workflow fires
on `pull_request`. Production promotes only on `push` to `main`. A workflow
that promotes prod from a PR (holds the prod token in an untrusted PR
context) is a blocker.

## Capturing `static_web_app_url`

```yaml
- id: swa
  uses: Azure/static-web-apps-deploy@v1
  # ...
# later job (e.g. e2e):
- run: echo "Preview URL ${{ steps.swa.outputs.static_web_app_url }}"
```

Hand `steps.swa.outputs.static_web_app_url` to `writing-e2e-tests` so the
e2e suite runs against the PR preview — the canonical "e2e against the PR
preview" wiring.

## `skip_app_build` vs Oryx

- `skip_app_build: true` — you build yourself (Vite, custom Next, etc.) and
  hand SWA `output_location`. Set this for non-Oryx or already-built apps.
- Oryx (default, no `skip_app_build`) — SWA auto-builds Oryx-supported
  frameworks. A Vite app left to Oryx misbuilds — set `skip_app_build:
  true`.

## Custom domains

Configure via SWA config / `az staticwebapp hostname` — **not** in the
deploy action. Domain setup is idempotent and lives outside the hot deploy
path.

## Secrets

The deployment token is `${{ secrets.SWA_TOKEN }}` (or a named secret).
Never `vars`, never echo. `repo_token` is `secrets.GITHUB_TOKEN`.

## Common findings (red flags this skill catches)

| Finding | Severity |
|---|---|
| No `pull_request` trigger (no preview-per-PR) | major |
| Prod promoted from `pull_request` (token in untrusted context) | blocker |
| `skip_app_build` missing for a Vite/non-Oryx app (Oryx misbuilds) | major |
| `static_web_app_url` not captured (e2e can't target preview) | minor |
| SWA token in `vars` / echoed | blocker → `securing-ci` |
| Action not pinned to a major tag (`@main`) | major → `securing-ci` |
