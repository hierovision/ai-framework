# Ledger API

Multi-tenant bookkeeping service behind our customer portal and the partner
API. Node 22 + Postgres 16, deployed as one Docker image to our own Kubernetes
cluster. Redis carries the reconciler queue.

## Surfaces

- REST API (`src/server.js`): `POST /v1/entries`, `GET /v1/entries/:id`,
  `POST /v1/exports`, `POST /v1/webhooks/payments`.
- Admin CLI (`bin/ledgerctl`), run by on-call operators by hand.
- Worker (`worker/reconciler.js`): consumes jobs from the Redis queue and
  reconciles them against the payments provider.
- CSV import: operators upload a bank statement and the service parses it.

## Support

API keys are per-tenant. The partner API is the supported integration. The
admin CLI is supported for operators only.
