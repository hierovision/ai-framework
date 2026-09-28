# checkout-service

The checkout API behind the storefront. Ships as an npm package to the internal
registry and runs in the production web tier.

Build: `npm install && node server.js`. The release workflow publishes tagged
commits from `.github/workflows/release.yml`.

Dependencies are listed in `package.json`; a lockfile is committed at the repo
root. The Docker image is the deploy artifact.
