# Design

```text
customer ──TLS──> gateway ──mTLS──> service A
                       │──mTLS──> service B
operator ──> admin plane (separate port, static token)
plugin registry ──> WASM plugins (header rewrite, routing)
gateway ──> Redis (rate-limit counters)
```

- JWT validation: issuer and audience pinned; algorithm allowlist is a build
  setting. Rotation cadence for signing keys is not decided yet.
- Rate limits: Redis counters per route per customer. The failure mode when
  Redis is unreachable is not decided.
- Admin plane: static bearer token, checked per request; where it is stored
  and whether it rotates is not decided.
- Plugins: WASM modules from the registry run in a sandbox. What a plugin may
  see of request data (headers, body, customer identity) is not decided. The
  registry is an internal service; its trust level is not written down.
- Multi-region: gateways run in two regions. How signing keys and Redis
  counters are shared across regions is not decided.
- Logging: access logs are planned to include method, path, status, and
  customer id.
