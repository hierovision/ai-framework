# checkout-service release artifacts

A SOC 2 auditor asked for the SBOM and the build provenance for our released
artifact. What we have is in this folder:

- `sbom.cdx.json` — generated once by hand for the components we remembered.
- `release/checkout-service-3.4.1.tar.gz` — the shipped artifact.
- `Dockerfile` — the image consumers build from.

There are no `.sig`, `.intoto`, or checksum files beside the artifact.
