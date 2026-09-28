# Design

```text
Portal (tenant user) ──> REST API ──> Postgres (queries scoped by tenant id)
Partner (server-to-server) ──> REST API (API key per tenant, bcrypt at rest)
Payments provider ──> webhook ──> REST API ──> Redis queue ──> reconciler
reconciler ──> provider API (idempotency key = job id)
Operators ──> admin CLI ──> Postgres directly
Import path: operator ──> REST API ──> CSV parser ──> Postgres
```

- API keys are issued per tenant and stored bcrypt-hashed.
- The reconciler job body is written by the webhook handler (after signature
  verification) and read by the worker. Jobs carry a charge id and an amount.
- Exports are generated on request and streamed back to the caller; the
  export template is fixed, only the tenant id and date range vary.
