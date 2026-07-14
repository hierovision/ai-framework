# Azure Static Web Apps — authoritative excerpts (retrieved 2026-07-14)

> Frozen subset used by the validating-against-official-docs fixture. Stands
> in for the live vendor doc; a real pass would web-fetch and re-date it.

## Preview environments
- A preview environment is created per pull request ONLY when the workflow
  runs on the `pull_request` trigger. Without a `pull_request` trigger, no
  preview environment is generated.

## Deployment token
- The deployment token must be provided via `secrets` (for example
  `secrets.AZURE_STATIC_WEB_APPS_API_TOKEN`). It must NEVER be placed in
  `vars` and must not be echoed in logs.

## Build
- When the app is built by its own toolchain (for example Vite), set
  `skip_app_build: true` and provide `output_location`; otherwise Oryx
  rebuilds the app and may misbuild a non-Oryx framework.
