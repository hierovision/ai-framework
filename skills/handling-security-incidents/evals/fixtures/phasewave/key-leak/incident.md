# Confirmed: release signing key leaked

The signing key `release-signer-2025` was found in a public CI log and is
confirmed compromised. It was used to sign the release artifacts below.

- `checkout-service-1.4.0` (signed 2026-09-21)
- `checkout-service-1.4.1` (signed 2026-09-27)

The key is still active in the signing pipeline. The last known-good artifact
signed before the leak is `checkout-service-1.3.9`.
