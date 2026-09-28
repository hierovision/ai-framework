# edge-gateway

API gateway in front of our internal services. Terminates TLS, validates
customer JWTs, and routes to services over mTLS. Per-route rate limits live
in Redis. An admin plane runs on a separate port behind a static bearer
token. A plugin registry loads WASM modules that can rewrite headers and
route decisions.

## Status

Design is frozen; implementation starts next quarter. The docs below are what
we have.
