# Known consumer repositories

This reference is the single enumeration source for the framework's known
consumer fleet. Tooling (`scripts/consumer_security_sweep.py`,
`scripts/fetch_advisories.py`, `scripts/check_security_register.py`,
`scripts/check_repo_posture.py`) reads the fenced block below; no consumer is
inferred from a local directory, an environment variable, or a glob.

Five canonical slugs are known. `pt` is the short slug for
`hierovision/phasetimer`; `phasetimer` is an alias, not a sixth consumer. `pln`
is retired (archived 2026-10-25) and receives the decommission check only — it
is never audited for dependency exposure again.

The `stack` field describes remediation routing (which stack reference an
agent should load when a finding becomes a fix), not a generated-type
contract. `lockfile_paths` are repository-root relative; they are the only
files the advisory fetcher reads besides `package.json` and the workspace
manifests those files reference.

Confirmation record: owner/repository, archived/active state, default branch,
and root lockfile values were read from read-only GitHub metadata and
root-file queries on 2026-11-07. No consumer working tree, secret, or primary
checkout was read.

```json consumer-inventory-v1
{
  "schema_version": 1,
  "consumers": [
    {
      "slug": "excel-daily-monitor",
      "repository": "hierovision/excel-daily-monitor",
      "aliases": [],
      "status": "active",
      "stack": "node-playwright",
      "package_manager": "npm",
      "lockfile_paths": ["package-lock.json"],
      "sweep_cadence": "weekly"
    },
    {
      "slug": "marvin-slack",
      "repository": "hierovision/marvin-slack",
      "aliases": [],
      "status": "active",
      "stack": "node-slack",
      "package_manager": "npm",
      "lockfile_paths": ["package-lock.json"],
      "sweep_cadence": "weekly"
    },
    {
      "slug": "pln",
      "repository": "hierovision/pln",
      "aliases": [],
      "status": "retired",
      "stack": "legacy-node",
      "package_manager": "yarn",
      "lockfile_paths": ["yarn.lock"],
      "sweep_cadence": "decommission-only"
    },
    {
      "slug": "pt",
      "repository": "hierovision/phasetimer",
      "aliases": ["phasetimer"],
      "status": "active",
      "stack": "vue-supabase",
      "package_manager": "yarn",
      "lockfile_paths": ["yarn.lock"],
      "sweep_cadence": "weekly"
    },
    {
      "slug": "paragon-learning-network",
      "repository": "Stonegate-Software/paragon-learning-network",
      "aliases": [],
      "status": "active",
      "stack": "nextjs-supabase",
      "package_manager": "pnpm",
      "lockfile_paths": ["pnpm-lock.yaml"],
      "sweep_cadence": "weekly"
    }
  ]
}
```

## Regenerating an entry

An inventory change is a reviewed commit: update the fenced block, run
`python3 scripts/test_consumer_security_sweep.py` (exact-set and alias
assertions), and run `python3 scripts/consumer_security_sweep.py --list` to
confirm the five-line output. Adding a sixth consumer is a fleet change, not a
config edit — it needs an owner decision and the corresponding audit job.
