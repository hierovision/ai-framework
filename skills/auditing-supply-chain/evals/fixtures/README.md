# Supply-chain eval fixtures — containment contract

These directories are deliberately vulnerable audit targets. Nothing here is
installed, resolved, executed, or fetched by this repository, by CI, or by the
eval harness.

## Manifest storage

npm manifests are stored with a `.fixture` suffix:

- `package.json.fixture`
- `package-lock.json.fixture`

GitHub's dependency graph and Dependabot scan only the real filenames
(`package.json`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`,
`npm-shrinkwrap.json`), so the fixtures never enter the repository's
dependency graph and never generate Dependabot alerts or security-update PRs.

The eval runner
(`skills/authoring-skills/scripts/run_behavioral_eval.py`) materializes each
`.fixture` source under its real name **inside the per-run temp workspace**.
The evaluated agent sees a normal repository; the source tree stays inert.

**Do not rename these files back.** The regression guard is
`scripts/test_eval_workflows.py::test_supply_chain_fixture_manifests_are_inert`.

## Additional inertness

- The lockfiles carry missing or placeholder integrity values, so `npm ci`
  fails rather than installing them.
- `lodahs` (a typosquat shape) resolves to npm's security-holder package, not
  a live version; `^1.0.0` cannot resolve.
- `github:acme/internal-auth#main` points at a non-existent repository.
- The vendor drop's beacon host is under the reserved `.invalid` TLD.
- The vendor drop's postinstall is never executed; the fixture is read as
  untrusted data.

Any Dependabot alerts on these paths are dismissed as `tolerable_risk` and
recorded in `SECURITY.md` (dated exception, 2026-11-07). Do not auto-fix a
fixture.
