# Security notes (maintainers)

These are the positions we have taken on reports so far.

- Tenancy: every query is scoped to the tenant id taken from the caller's API
  key. A report that needs attacker control of another tenant's API key is out
  of scope. (Repeated in #412 and #520.)
- Webhooks: `POST /v1/webhooks/payments` verifies the provider's HMAC
  signature before parsing the body; unsigned bodies are rejected. Anything
  behind a valid signature is accepted as data, never as instructions.
- CSV import: there is no limit on the number of rows or the total decoded
  size. Operators upload trusted files; we do not defend against a hostile
  statement. (FAQ "Import sizes".)
- Admin CLI: arguments come from operators, who already run as the service
  account. CLI input is trusted.
- The service calls out only to the payments provider and the FX rate
  endpoint, both over TLS with certificate validation.
