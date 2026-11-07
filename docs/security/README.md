# Consumer security — continuous detection runbook

This directory is the durable contract for the weekly consumer-security sweep
(RM-076). It replaces a one-off manual audit with a repeatable, sanitized,
CI-gated operation over the five known consumers in
`reference/consumer-repos.md`.

The sweep is point-in-time. It covers the five known repos; it does **not**
enumerate unknown public consumers and never proves the absence of exposure.
The framework propagation controls from Phase 1 are what protect unknown
consumers.

## Commands

```bash
# Inventory (five canonical slugs, inventory order)
python3 scripts/consumer_security_sweep.py --list

# Sanctioned advisory intake — the only network step. Dry-run by default;
# the explicit --out snapshot is the only write.
python3 scripts/fetch_advisories.py --dry-run \
  --from-audit .scratch/consumer-security-sweep/audit \
  --out .scratch/consumer-security-sweep/audit/snapshot.json

# Offline sweep + register coverage + severity gate
python3 scripts/consumer_security_sweep.py \
  --snapshot .scratch/consumer-security-sweep/audit/snapshot.json \
  --controls docs/security/controls.json \
  --out .scratch/consumer-security-sweep/sweep.json \
  --markdown-out .scratch/consumer-security-sweep/sweep.md \
  --check --fail-on high,critical
python3 scripts/check_security_register.py \
  --sweep .scratch/consumer-security-sweep/sweep.json

# RM-075 handoff completeness (five briefs, no-argument defaults)
python3 scripts/check_security_handoffs.py

# Owner-run live posture (never in CI)
python3 scripts/check_repo_posture.py --repo hierovision/ai-framework
python3 scripts/check_repo_posture.py \
  --consumer-inventory reference/consumer-repos.md

# CI-safe posture subset (tracked config only, no gh, no socket)
python3 scripts/check_repo_posture.py --local
```

Every command exits non-zero on a contract failure. `check_repo_posture.py`
exits 2 (not 1) when it could not run — authentication, network, permission,
or unexpected API failures are never suppressible.

## Cadence

- **Weekly** — `.github/workflows/security.yml` runs Monday 07:00 UTC and on
  `workflow_dispatch`. This exceeds the policy minimum.
- **Release** — the owner dispatches the same workflow after any framework
  release that changes a propagation control (`install.sh`, the eval harness, a
  skill script, redaction, or a dependency pin).
- **Quarterly** — at least one dated sweep review, at the ALM review, even if
  the weekly runs stayed green.

The scheduled workflow is deliberately separate from PR evaluation: it has no
`pull_request` trigger and references no provider/eval secret.

## Closed JSON schemas

All contracts are closed: unknown fields fail validation, UTF-8, two-space
indentation, sorted object keys, LF, one trailing newline. Dates are
`YYYY-MM-DD`; timestamps are UTC RFC 3339 with `Z` and whole seconds. Arrays
are sorted by their stated keys.

### Inventory — `reference/consumer-repos.md`

One fenced `json consumer-inventory-v1` block:

| Field | Meaning |
|---|---|
| `slug` | canonical short name; `pt` is `hierovision/phasetimer` |
| `repository` | `owner/name` |
| `aliases` | alternate names only (`phasetimer` for `pt`); never a consumer |
| `status` | `active` or `retired` |
| `stack` | remediation routing hint, not a generated-type contract |
| `package_manager` | `npm`, `yarn`, or `pnpm` |
| `lockfile_paths` | repo-root-relative lockfiles the fetcher may read |
| `sweep_cadence` | `weekly` for active, `decommission-only` for retired |

### Advisory snapshot — `snapshot.json`

`schema_version`, `as_of`, `source` (always
`https://api.osv.dev/v1/querybatch`), `revisions[]` (one 40-hex commit per
active repo), `queries[]`, `results[]`.

- `queries[]` is sorted by `(repo, package, installed, scope, origin,
  lockfile)` and carries a zero-based `query_index` after sorting.
- `results[]` has exactly one entry per query, including empty results.
- Advisory fields are allowlisted: `id`, `aliases`, `severity`, `fixed`.
  Verbose OSV details, references, headers, and response bodies are dropped.
- `scope` is `runtime` or `dev`. Ambiguous/shared reachability is conservatively
  `runtime`.
- `origin` is `framework-propagated` only for an exact name/version match in a
  tracked framework production lockfile; otherwise `consumer-local`. This is
  remediation routing, not exploitability or attribution.

### Controls — `docs/security/controls.json`

Open observations only: `{repo, control_id, severity, scope, origin}`.
Resolved controls leave this file; their register rows remain as history.
Control IDs start `framework/` or `consumer-local/`, and `origin` must agree
with the prefix.

### Sweep report — `sweep.json`

`schema_version`, `as_of`, `source` (`kind`, `snapshot_sha256`,
`controls_sha256`), `consumers[]`, `findings[]`.

- `as_of` and both hashes come from input bytes, never the clock.
- A full fleet report has all five consumers in inventory order; a missing
  active revision fails instead of emitting a partial fleet report.
- Exactly one of `advisory_id`/`control_id` is set per finding.
- `sweep_id` is the SHA-256 of the canonical compact identity object
  `{repo, advisory_id, control_id, package, installed, severity, scope,
  origin, lockfile}`. It deliberately excludes `fixed`, so a version bump does
  not fork identity.
- Disposition state is **not** in the report. It lives in the register.

### Disposition register — `docs/security/register.json`

`schema_version`, `as_of` (date), `findings[]` sorted by `sweep_id`.
Each row: `sweep_id`, `repo`, exactly one of `advisory_id`/`control_id`,
`severity`, `scope`, `origin`, `disposition` (`fix`/`accepted`/`decommission`),
`owner`, `date`, `review_on`, `note`.

- `fix` and `decommission` require `review_on: null`; `accepted` requires a
  review date later than `date`.
- `decommission` is valid only for retired `pln`.
- Every finding in a supplied sweep must appear exactly once. Rows for older
  findings remain valid as history.
- Expiration is evaluated against the supplied sweep's date; with no sweep, the
  register's own `as_of`.
- `note` is a required sanitized rationale. Package versions and verbose
  advisory text stay out of the tracked summary.

## Severity and gate mapping

| Severity | Gate class |
|---|---|
| `critical` | blocker |
| `high` | major |
| `medium` | minor |
| `low` | nit |
| `unknown` | major until triaged |

`--fail-on high,critical` therefore gates major/blocker findings (and
`unknown`). The gate fails an open finding whose disposition is `fix`,
missing, invalid, or expired. An unexpired `accepted` row and a valid
`decommission` row pass the threshold. Malformed dispositions still fail.

## Acceptance and review policy

- New acceptances default to a `review_on` 90 days after `date`; an owner may
  choose a later date explicitly.
- Acceptance is only for a documented platform-gated feature, a no-fix-upstream
  advisory, or an owner-attested operational residual. It is never a substitute
  for a fix.
- A live feature-unavailable API response is the only platform-gated case the
  consumer posture check may accept; authentication, network, permission, and
  unexpected API failures exit 2 and cannot be suppressed.
- Resolved controls leave `controls.json`; their register rows stay as history.

## Read-only credential boundary

`.github/workflows/security.yml` requires `CONSUMER_SECURITY_READ_TOKEN`:

- stored as an **environment secret** on a `main`-restricted environment
  (`consumer-security`), never a repository-level secret — this repository is
  public, and a repo secret is readable by any workflow that reaches a job;
- a 90-day fine-grained PAT (or an equivalent read-only GitHub App) restricted
  to the four active consumer repositories with **Contents: Read** only;
- no admin, secret-reading, actions-write, or repository-write permission;
- `persist-credentials: false` on every checkout;
- the intake job fails closed when the credential is missing. The run never
  degrades to a silently partial fleet report.

Record the credential's expiry and rotation in
`docs/roadmap-detail/RM-076.md` when it is created.

## Artifacts and retention

Artifacts retain **30 days** and contain only the closed-schema sanitized
files: `advisories-<date>.json`, `sweep-<date>.json`, `sweep-<date>.md`
(per-repo legs prefix the slug). Raw checkouts, `.git`, revisions with local
paths, manifests, lockfiles, native audit output, verbose OSV responses, logs,
environment files, and credentials are never uploaded.

The register, current controls, and public artifacts contain no secret names or
values, environment-file contents, absolute/local paths, raw manifests or
lockfiles, exploit preconditions, or verbose upstream advisory details. Local
work material stays in ignored `.scratch/consumer-security-sweep/`.

## Private disclosure

**Do not open a public issue for a security report.** Use GitHub's private
security advisory for this repository (see `SECURITY.md`). The same rule
applies to a consumer finding: if remediation requires disclosing an
unpatched vulnerability or a live credential, coordinate privately with the
consumer owner first; never paste the raw advisory, exploit path, or secret
into a public PR, issue, or artifact.
