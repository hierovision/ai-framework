---
slug: rm-076-phase-3-continuous-detection
title: Make the known-consumer security sweep deterministic, dispositioned, and CI-gated
status: draft
created: 2026-11-07
revised: [2026-11-07]
related: [fix-consumer-security-exposure, RM-073, RM-075]
---

# Plan: rm-076-phase-3-continuous-detection

## Goal / Approach

**Goal:** The five known consumers receive a repeatable weekly security sweep whose offline output is deterministic, whose current findings all have dated dispositions, and whose per-repo audit, handoff, and posture gates fail closed without editing consumer repositories.

**Approach:** A machine-readable inventory drives four active-consumer audit jobs and one retired-consumer decommission check. `fetch_advisories.py` is the only advisory-network step: it reads lockfiles without installing packages, queries OSV, and writes an explicitly named provenance snapshot. `consumer_security_sweep.py` consumes that snapshot and sanitized control observations offline. It emits stable JSON and Markdown with finding identity separate from remediation state. A tracked, sanitized JSON register owns dispositions; raw checkouts and untracked working material stay in `.scratch/consumer-security-sweep/`. The scheduled workflow uses a read-only cross-repo credential and never receives repository-admin credentials. Live posture checks remain owner-run; CI invokes only their local, static subset.

The original contract needs four explicit reconciliations:

1. Original AC1 names `reference/consumer-repos.md`, but the file is absent at base `64251af`. This plan creates it as the inventory source of truth; it does not infer consumers from local directories.
2. The original sweep-report schema mixed `disposition`, `owner`, and `date` into findings, while original AC4 assigned those fields to the register. This plan keeps sweep findings immutable and puts remediation state only in the register, joined by `sweep_id`.
3. Original AC3 both makes `--dry-run` the default and requires an output snapshot. The default dry run therefore permits exactly one write: the explicit `--out` file. It never runs a package manager mutation or changes a manifest or lockfile. Verification compares `git status --porcelain` before and after rather than requiring an empty status on an already-dirty implementation branch.
4. Original AC11 requires five real briefs, while the current tree contains neither the briefs nor their checker and RM-075 owns brief authorship. RM-076 implements and tests the checker against fixtures. Final no-argument AC11 verification uses RM-075's five scratch briefs and remains blocked until those inputs exist; this plan neither authors nor moves them.

## Acceptance Criteria

1. **P3-1 — Explicit inventory (original AC1 plus the missing inventory deliverable).** `reference/consumer-repos.md` contains one fenced JSON inventory with exactly five canonical slugs: `excel-daily-monitor`, `marvin-slack`, `pln`, `pt`, and `paragon-learning-network`. `pt` records `phasetimer` as an alias, not a sixth consumer. The records carry the owner/repository, status, stack, package manager, root lockfile, and cadence specified below. `python3 scripts/consumer_security_sweep.py --list` prints those five slugs once each in inventory order and no other line.
   - **Verifier:** `python3 scripts/test_consumer_security_sweep.py` asserts the exact set, aliases, repositories, statuses, and lockfiles; its `--list` golden assertion passes.
   - **Verifier:** `python3 scripts/consumer_security_sweep.py --list` matches the five-line expected output in Verification.

2. **P3-2 — Deterministic, offline sweep (original AC2).** Two runs over the same audit fixture produce byte-identical JSON and Markdown. Output ordering, formatting, `as_of`, finding IDs, and source provenance do not depend on wall-clock time, filesystem order, absolute paths, or environment variables. The sweep performs no socket operation, including indirect OSV or package-manager calls.
   - **Verifier:** the two `sha256sum` values for `a.json` and `b.json` are equal, `cmp -s a.json b.json` exits 0, and the same two checks pass for `a.md` and `b.md` using the commands below.
   - **Verifier:** `python3 scripts/test_consumer_security_sweep.py` runs the sweep in-process with `socket.socket`, `socket.create_connection`, and `socket.getaddrinfo` replaced by a failing guard. Any attempted network operation fails the test. The golden report and the negative control proving the guard is active both pass.

3. **P3-3 — Sanctioned advisory intake with provenance (original AC3).** `python3 scripts/fetch_advisories.py --from-audit <fixture-dir> --out snapshot.json` defaults to `--dry-run`, uses only the OSV batch endpoint for advisory network traffic, and writes `schema_version`, `as_of`, `source`, `revisions[]`, `queries[]`, and `results[]`. Every query has exactly one result entry, including queries with no advisories. The explicit output is the sole write; manifests, lockfiles, package-manager state, and git-visible status do not change.
   - **Verifier:** `python3 scripts/test_fetch_advisories.py` exits 0 with mocked OSV responses and a socket guard. It covers npm, Yarn v1, and pnpm fixtures, empty and non-empty results, stable query/result correlation, atomic output, required provenance, and unchanged hashes for every input manifest and lockfile.
   - **Verifier:** the before/after `git status --porcelain` snapshots and `cmp` command in Verification show no status delta after a dry run whose output is under ignored `.scratch/`.

4. **P3-4 — Complete dated disposition register (original AC4).** `python3 scripts/check_security_register.py` validates `docs/security/register.json` by default. Every row has `sweep_id`, `repo`, exactly one of `advisory_id` or `control_id`, `severity`, `scope` (`runtime`/`dev`), `origin` (`framework-propagated`/`consumer-local`), `disposition` (`fix`/`accepted`/`decommission`), `owner`, `date`, and a sanitized `note`. Every finding ID in a supplied sweep appears exactly once. Duplicate rows, missing or mismatched coverage, invalid enums/dates, and unknown fields fail. Historical register rows absent from a newer sweep remain valid. An `accepted` row additionally requires `review_on` and a rationale; `decommission` is valid only for retired `pln`.
   - **Verifier:** `python3 scripts/check_security_register.py` exits 0 against the tracked register, and `python3 scripts/check_security_register.py --register scripts/fixtures/consumer-security/register.json --sweep .scratch/rm-076/a.json` exits 0 with every generated fixture sweep ID covered exactly once.
   - **Verifier:** `python3 scripts/test_security_register.py` proves pass and failure cases for every required field, duplicate and missing IDs, stale/expired acceptance, invalid decommission, and extra historical rows.

5. **P3-5 — Five complete handoffs, without unsafe remediation (original AC11 checker half).** `python3 scripts/check_security_handoffs.py` reads the five original paths under `.scratch/consumer-security-sweep/`: `handoff-paragon-learning-network.md`, `handoff-pt.md`, `handoff-marvin-slack.md`, `handoff-excel-daily-monitor.md`, and `handoff-pln.md`. Each names its repository, P0/P1 finding IDs, installed and fixed versions (or an explicit `N/A — control-only`/`N/A — decommissioned` reason), verification commands, and owner actions. Each carries the prohibition on `audit fix --force` and undated suppression. An executable command containing `--force` fails; the prose prohibition remains allowed. Every suppression/acceptance/dismissal record has ID, owner, ISO date, review date, and rationale.
   - **Verifier:** `python3 scripts/test_security_handoffs.py` exits 0 against five generated valid briefs and fails focused cases for a missing brief, every missing content class, an executable `--force`, and an undated suppression.
   - **Verifier:** after RM-075 supplies the real inputs, no-argument `python3 scripts/check_security_handoffs.py` exits 0. Missing real briefs remain a blocker; fixture success cannot satisfy this half of the criterion.

6. **P3-6 — Per-repo audit gates and weekly continuous detection (Phase 3 approach).** `.github/workflows/security.yml` runs weekly and on manual dispatch. One intake job checks out each active consumer's default-branch content into a separate scratch directory, reads only package manifests, their referenced workspace manifests/metadata, and inventory-declared lockfiles, and emits one shared sanctioned OSV snapshot plus the tracked current-control observations. Four active-consumer audit jobs consume that identical snapshot independently, each running the offline sweep, register coverage, and `--check --fail-on high,critical` for its `--consumer` view. An unaccepted high/critical finding fails the affected repo job. An unexpired dated acceptance does not fail the threshold gate; malformed or missing dispositions still fail. The aggregate job consumes the same snapshot and emits one fleet report containing all five consumer statuses, with retired `pln` marked decommission-only.
   - **Verifier:** `python3 scripts/test_security_workflows.py` asserts the schedule, manual dispatch, one shared intake snapshot, four-repo matrix plus retired status, identical snapshot/controls inputs to the per-repo and aggregate sweeps, per-repo threshold command, fail-closed credential requirement confined to intake checkouts, least-privilege permissions, SHA-pinned actions, `persist-credentials: false`, 30-day retention, sanitized artifact allowlist, and absence of automatic PR/issue creation or consumer code execution.
   - **Verifier:** `python3 -m yamllint -c .yamllint.yaml .github/workflows/` exits 0.
   - **Manual verifier:** after the read-only credential is configured, an owner-dispatched `security.yml` run on `main` finishes green, shows four active per-repo gates plus the retired status, and uploads only the dated, sanitized snapshot/report artifacts.

7. **P3-7 — Dependabot and secret-scanning posture without admin credentials in CI.** The existing `python3 scripts/check_repo_posture.py --repo hierovision/ai-framework` behavior remains an owner-run live check. A new `--consumer-inventory reference/consumer-repos.md` owner-run mode checks active consumers for Dependabot alerts/security updates and secret scanning/push protection, honors only unexpired dated register exceptions for platform-gated settings, and requires `pln` to remain archived/decommissioned. Only a documented feature-unavailable API response is eligible for dated acceptance; authentication, network, permission, and unexpected API failures exit 2 and cannot be suppressed. A new `--local` mode checks only tracked configuration and dated exception syntax, performs no `gh` or socket call, and is the only posture mode referenced by `security.yml`. It reports live settings as `SKIP — owner-run`, never as `PASS`.
   - **Verifier:** `python3 scripts/test_repo_posture.py` mocks live API responses for enabled, drifted, platform-gated accepted, expired-accepted, and retired cases; its local-mode socket guard proves that CI cannot trigger `gh api` or network access.
   - **Verifier:** `python3 scripts/check_repo_posture.py --local` exits 0; `python3 scripts/test_security_workflows.py` proves the workflow contains no `--repo` or `--consumer-inventory` posture invocation and no admin token.
   - **Owner verifier:** `python3 scripts/check_repo_posture.py --repo hierovision/ai-framework` and `python3 scripts/check_repo_posture.py --consumer-inventory reference/consumer-repos.md` exit 0 at phase close.

8. **P3-8 — Sanitized durable documentation and artifacts.** `docs/security/README.md` documents the commands, closed JSON schemas, severity normalization, acceptance/review policy, read-only credential boundary, weekly/release/quarterly cadence, artifact retention, and private-disclosure rule. `docs/security/controls.json` is the sanitized current-open-control input; resolved controls leave that file while their register rows remain as history. `docs/security/consumer-exposure-2026-10-25.md` reproduces only the parent plan's sanitized historical counts and dispositions, with the warning that package-manager counts are not comparable. The register, current controls, and public artifacts contain no secret names or values, environment-file contents, absolute/local paths, raw manifests/lockfiles, exploit preconditions, or verbose upstream advisory details.
   - **Verifier:** `python3 scripts/test_security_workflows.py` passes synthetic secret canaries and local paths through the artifact serializer, proves they are absent from serialized output or cause a closed-schema rejection, and checks that workflow upload paths exclude checkouts, raw responses, manifests, lockfiles, and `.env*`.
   - **Verifier:** `python3 scripts/test_security_register.py` rejects secret-shaped or absolute-path values in register fields; `git diff --check` exits 0.

9. **P3-9 — Hermetic PR gates cover the new contracts.** `.github/workflows/ci.yml` runs all six new test modules and the no-argument register checker without network access or scratch-only real handoffs. The scheduled workflow remains separate from PR evaluation secrets and does not run on `pull_request`.
   - **Verifier:** the focused commands in Verification exit 0 locally; the `quality-gates` and `dependency-audit` PR checks are green; `python3 scripts/test_security_workflows.py` proves `security.yml` has no PR trigger or provider-secret reference.

10. **P3-10 — The delivering PR closes RM-076 coherently.** The implementation PR moves the RM-076 row and priority/horizon/counter entries to Done with its date, PR link, and verification evidence; updates `docs/roadmap-detail/RM-076.md`; and retires this working plan after extracting its durable contracts into `docs/security/` and the detail file.
    - **Verifier:** `python3 scripts/check_roadmap_verbatim.py` exits 0, the roadmap counters agree, and the final diff contains no stale citation to the retired plan path. If RM-075's real briefs or owner-only live checks remain incomplete, the row stays open and the handoff names those blockers instead of claiming closure.

## Files to Modify

- `reference/consumer-repos.md` — new; prose rationale plus exactly one fenced `consumer-inventory-v1` JSON block. It is the only consumer enumeration source.
- `scripts/consumer_security_sweep.py` — new; stdlib-only inventory parsing, snapshot/control ingestion, deterministic finding identity/classification, JSON/Markdown serializers, `--list`, `--list --json`, `--from-audit`, `--consumer`, `--controls`, `--out`, `--markdown-out`, `--check`, and `--fail-on` support. It never imports or invokes the advisory fetcher.
- `scripts/fetch_advisories.py` — new; stdlib-only npm/Yarn v1/pnpm lockfile readers, deterministic OSV batch intake, explicit `--out`, default `--dry-run`, mocked-transport seam, and atomic snapshot writes. It never runs install/audit/fix commands.
- `scripts/check_security_register.py` — new; closed register-schema validation, sweep coverage, date/review validation, and retired-repo decommission rules. Defaults to `docs/security/register.json`; accepts `--register` and `--sweep`.
- `scripts/check_security_handoffs.py` — new; five-brief Markdown contract, command-token safety check, and structured dated-suppression validation. Defaults to the original scratch filenames and accepts `--handoff-dir` for hermetic fixtures.
- `scripts/check_repo_posture.py` — preserve existing default live framework behavior; add mutually exclusive `--consumer-inventory` and `--local` modes. Extract the existing tracked-Dependabot assertions for local mode; add live consumer checks and register-backed dated exceptions.
- `scripts/test_consumer_security_sweep.py` — new; inventory/golden/determinism/socket-block tests, runtime-vs-dev and origin classification, stable IDs, Markdown determinism, and sanitizer negative controls.
- `scripts/test_fetch_advisories.py` — new; three lockfile formats, mocked OSV transport, provenance/result correlation, no-network test path, no-mutation hashes, no git-status delta, and atomic-write failure cases.
- `scripts/test_security_register.py` — new; valid/invalid register and sweep-coverage tables.
- `scripts/test_security_handoffs.py` — new; five valid synthetic briefs and focused rejection cases, including the allowed prohibition versus executable `--force` distinction.
- `scripts/test_repo_posture.py` — new; mocked `gh` responses and local-mode socket/`gh` denial.
- `scripts/test_security_workflows.py` — new; structural weekly/CI assertions, credential/permissions boundaries, artifact-path and secret-canary checks.
- `scripts/fixtures/consumer-security/README.md` — new; fixture layout and regeneration rules. Fixtures contain no live consumer data and no dependency-graph-visible manifests.
- `scripts/fixtures/consumer-security/snapshot.json` — new; synthetic advisory-snapshot-v1 input with stable `as_of`, revisions for all four active consumers, queries, and results.
- `scripts/fixtures/consumer-security/controls.json` — new; synthetic open control observations, including one retired-repo control.
- `scripts/fixtures/consumer-security/expected-sweep.json` — new; canonical five-consumer golden report for the two input files above.
- `scripts/fixtures/consumer-security/register.json` — new; synthetic valid dispositions covering every golden sweep ID exactly once; never reused as the real register.
- `scripts/fixtures/consumer-security/osv-response.json` — new; synthetic mocked OSV batch response used only by fetch tests.
- `docs/security/register.json` — new; canonical sanitized disposition register from the first new sweep plus current control findings and the `pln` decommission row. It must not be an empty placeholder while known findings remain.
- `docs/security/controls.json` — new; sanitized current-open control observations used by every live/CI sweep. Fixed controls are removed here but retained in register history.
- `docs/security/README.md` — new; operator runbook, schema definitions, severity/gate mapping, disclosure and sanitization policy, credential setup, artifact policy, and owner-run commands.
- `docs/security/consumer-exposure-2026-10-25.md` — new; sanitized historical summary from the parent findings table, not a reconstruction of unavailable raw audit data.
- `SECURITY.md` — link the fleet record to the new inventory and runbook; state that weekly CI exceeds the minimum quarterly cadence and that release-impacting propagation-control changes still require a manual dispatch.
- `.github/workflows/security.yml` — new; schedule/dispatch-only four-active-repo matrix, aggregate fleet report, threshold/register gates, local posture subset, and 30-day sanitized artifacts. No consumer scripts, installs, PRs, issues, or admin API calls.
- `.github/workflows/ci.yml` — add the six hermetic test modules and no-argument register validation to `quality-gates`; leave existing dependency-audit scope unchanged.
- `docs/ROADMAP.md` — implementation PR only; close RM-076 with its PR/evidence and reconcile every affected counter/horizon/priority row.
- `docs/roadmap-detail/RM-076.md` — implementation PR only; record delivered behavior, verification, credential/manual-check residuals, and the RM-075 handoff dependency.
- `.opencode/plans/rm-076-phase-3-continuous-detection.md` — tracked for design/approval; the implementation PR deletes it under AGENTS.md rule 4 after durable extraction. The parent `fix-consumer-security-exposure.md` remains because RM-075 still uses it.

No consumer repository file is in this file map.

## Scope

**Included**

- The exact five-repo inventory, including active/retired status and the `pt`/`phasetimer` alias.
- Read-only npm/Yarn v1/pnpm lockfile intake, OSV snapshots with provenance, and deterministic offline JSON/Markdown reports.
- Runtime/dev and framework-propagated/consumer-local classification, with ambiguous dependency reachability conservatively classified as `runtime`.
- A sanitized dated register, exact sweep-ID coverage, acceptance review dates, and the five-handoff completeness checker.
- Four active per-repo audit gates, retired `pln` decommission handling, weekly/manual CI, and sanitized dated artifacts.
- Live owner-run consumer posture checks and a network-free local posture subset for CI.
- Sanitized security documentation, PR tests, and RM-076 closure artifacts.

**Excluded**

- Editing, installing, executing, formatting, auditing with a package manager, or committing in any consumer repository; consumer content is parsed read-only in an isolated CI checkout or an owner-created isolated worktree.
- Authoring or repairing RM-075's five briefs, performing consumer remediation, rotating credentials, or changing live repository settings from the framework implementation pass.
- Secret values, `.env*` contents, auth/session stores, consumer primary checkouts, and raw or secret-bearing artifacts. No artifact may contain access tokens or admin credentials.
- Automatic dependency fixes, `audit fix --force`, any other executable `--force`, undated suppression, automatic PRs/issues, and package installation or consumer lifecycle scripts.
- Repository-admin/API posture checks in CI, long-lived write tokens, and making `check_repo_posture.py --repo` a CI gate.
- Enumeration of unknown public consumers or a claim that a finite sweep proves absence of every exposure.
- Native npm/pnpm/Yarn audit-report ingestion in v1; the supported interchange is the OSV snapshot produced from the three lockfile formats.
- A new advisory-intake skill, runtime exploitation, penetration testing, a full OWASP/ASVS review, legal/compliance conclusions, Phase 1 rework, and database/generated-type changes.

## Schema / Type Impacts

No database or generated types change. All JSON contracts are closed: unknown fields fail validation, strings are UTF-8, output uses two-space indentation, sorted object keys, LF line endings, and one trailing newline. Dates use `YYYY-MM-DD`; timestamps use UTC RFC 3339 with `Z` and whole seconds. Arrays are sorted by their stated keys before serialization.

### Consumer inventory v1 — `reference/consumer-repos.md`

The Markdown file contains exactly one block tagged ` ```json consumer-inventory-v1 ` (the parser accepts the info string `json consumer-inventory-v1`). Its shape is:

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

The owner/repository, status, and root lockfile values were corroborated by read-only GitHub metadata/root-file queries on 2026-11-07. `stack` describes remediation routing, not a generated-type contract. `--list` emits only canonical `slug` values. APIs may resolve an alias to its canonical slug before validation.

### Audit directory and advisory snapshot v1

`--from-audit DIR` uses this layout:

```text
DIR/
  <slug>/package.json and the inventory-declared lockfile   # fetch input, active repos
  <slug>/referenced workspace manifests/metadata             # fetch input, when present
  revisions.json                                            # optional fixture fallback
  snapshot.json                                             # fetch output / sweep input
  controls.json                                             # required sanitized sweep input
```

Live checkouts supply each full Git commit through read-only `git rev-parse HEAD`. Non-git fixtures supply `revisions.json` as `{"schema_version":1,"revisions":[{"repo":"pt","commit":"<40 lowercase hex>"}]}`. A snapshot must carry one revision per queried repo.

`fetch_advisories.py` writes `snapshot.json` as:

```json
{
  "schema_version": 1,
  "as_of": "2026-11-07T00:00:00Z",
  "source": "https://api.osv.dev/v1/querybatch",
  "revisions": [
    {"repo": "pt", "commit": "0123456789abcdef0123456789abcdef01234567"}
  ],
  "queries": [
    {
      "query_index": 0,
      "repo": "pt",
      "ecosystem": "npm",
      "package": "example-package",
      "installed": "1.2.3",
      "scope": "runtime",
      "origin": "consumer-local",
      "lockfile": "yarn.lock",
      "query": {
        "package": {"ecosystem": "npm", "name": "example-package"},
        "version": "1.2.3"
      }
    }
  ],
  "results": [
    {
      "query_index": 0,
      "advisories": [
        {
          "id": "GHSA-example",
          "aliases": ["CVE-2026-0000"],
          "severity": "high",
          "fixed": ["1.2.4"]
        }
      ]
    }
  ]
}
```

`queries[]` sorts by `(repo, package, installed, scope, origin, lockfile)` and receives its stable zero-based `query_index` after sorting. `results[]` sorts by `query_index`; advisories sort by `id`; `aliases` and `fixed` sort lexically. `fixed` is empty when OSV supplies no fixed version. The fetcher stores only these allowlisted fields, not verbose OSV details, references, request headers, or response bodies.

The lockfile readers classify production-reachable packages as `runtime`, dev-only packages as `dev`, and shared or unresolved reachability as `runtime`. A package is `framework-propagated` only when its exact name/version is present in a tracked framework production lockfile or its control ID is registered as a framework control; otherwise it is `consumer-local`. This is deterministic remediation routing, not proof of exploitability or attribution.

### Control observations v1 — `controls.json`

```json
{
  "schema_version": 1,
  "controls": [
    {
      "repo": "pt",
      "control_id": "consumer-local/example-control",
      "severity": "high",
      "scope": "runtime",
      "origin": "consumer-local"
    }
  ]
}
```

Only open observations belong in this file. Fixed controls disappear from the next sweep; their register rows remain as history. Control IDs beginning `framework/` are `framework-propagated`; IDs beginning `consumer-local/` are `consumer-local`; the explicit `origin` must agree. The sweep reads `DIR/controls.json` by default. `--controls PATH` selects another file; live/CI runs set it to `docs/security/controls.json`. The selected file is required even when it contains an empty `controls` array, so missing control input cannot silently produce a dependency-only report.

### Sweep report v1 — `sweep.json`

```json
{
  "schema_version": 1,
  "as_of": "2026-11-07T00:00:00Z",
  "source": {
    "kind": "osv-snapshot",
    "snapshot_sha256": "<64 lowercase hex>",
    "controls_sha256": "<64 lowercase hex>"
  },
  "consumers": [
    {
      "slug": "pt",
      "repository": "hierovision/phasetimer",
      "status": "active",
      "audit_status": "audited",
      "commit": "0123456789abcdef0123456789abcdef01234567"
    },
    {
      "slug": "pln",
      "repository": "hierovision/pln",
      "status": "retired",
      "audit_status": "decommission-only",
      "commit": null
    }
  ],
  "findings": [
    {
      "sweep_id": "<64 lowercase hex>",
      "repo": "pt",
      "advisory_id": "GHSA-example",
      "control_id": null,
      "package": "example-package",
      "installed": "1.2.3",
      "fixed": ["1.2.4"],
      "severity": "high",
      "scope": "runtime",
      "origin": "consumer-local",
      "lockfile": "yarn.lock"
    }
  ]
}
```

`as_of` and both source hashes come from input, never the clock. In a full fleet report, `consumers[]` follows inventory order and includes all five records; a partial active-repo input fails rather than emitting a silently partial fleet report. Single-repo CI jobs use `--consumer <slug>` and emit only that selected consumer record; the aggregate job uses the full directory. `findings[]` sorts by `sweep_id`.

`sweep_id` is the full lowercase SHA-256 of the UTF-8 canonical compact JSON object containing `repo`, `advisory_id`, `control_id`, `package`, `installed`, `severity`, `scope`, `origin`, and `lockfile`. Exactly one of `advisory_id` and `control_id` is non-null. Control findings use null for `package`, `installed`, and `lockfile`, and `fixed: []`. Dependency findings require those package fields. The register, not this report, owns `disposition`, `owner`, `date`, `review_on`, and `note`.

Severity is `critical`, `high`, `medium`, `low`, or `unknown`. The runbook maps critical to `blocker`, high to `major`, medium to `minor`, and low to `nit`; `unknown` maps to `major` until triaged. `--fail-on high,critical` therefore gates major/blocker findings. The gate fails open findings whose disposition is `fix`, missing, invalid, or expired. Unexpired `accepted` rows and valid `decommission` rows do not fail the severity threshold.

### Disposition register v1 — `docs/security/register.json`

```json
{
  "schema_version": 1,
  "as_of": "2026-11-07",
  "findings": [
    {
      "sweep_id": "<64 lowercase hex>",
      "repo": "pt",
      "advisory_id": "GHSA-example",
      "control_id": null,
      "severity": "high",
      "scope": "runtime",
      "origin": "consumer-local",
      "disposition": "accepted",
      "owner": "hierovision",
      "date": "2026-11-07",
      "review_on": "2027-02-05",
      "note": "Sanitized rationale; no exploit preconditions or secrets."
    }
  ]
}
```

Rows sort by `sweep_id`; `sweep_id` is unique. `fix` and `decommission` use `review_on: null`; `accepted` requires an ISO `review_on` later than `date`. The sweep `as_of` date determines expiration. Register `note` is required and nonempty. Package versions and verbose advisory text are deliberately excluded from this tracked summary.

### Handoff Markdown contract

Each RM-075 brief keeps human-readable Markdown and these exact headings:

```text
Repo: `<canonical-slug>` (`<owner/repository>`)
## P0/P1 findings
## Verification
## Owner actions
## Suppressions
## Guardrails
```

The findings table has `Finding ID`, `Priority`, `Installed`, and `Fixed` columns. Control-only and retired briefs use the explicit N/A reasons in P3-5 rather than inventing versions. `Verification` and `Owner actions` each contain at least one nonempty command/action. `Suppressions` is either `None.` or a table with `ID`, `Owner`, `Date`, `Review on`, and `Rationale`. `Guardrails` contains both prohibitions. The checker parses shell-like command fences/inline command spans for executable `--force`; it does not reject the guardrail sentence that forbids `audit fix --force`.

### CI inputs and public artifacts

The scheduled workflow requires an Actions credential named `CONSUMER_SECURITY_READ_TOKEN` on `hierovision/ai-framework`, stored as an **environment secret on a `main`-restricted environment** (the same pattern as the `eval` environment), never a repo-level secret — this repository is public, and a repo-level secret is readable by any workflow that reaches a job. The recommended token is a 90-day fine-grained PAT restricted to the four active consumer repositories with **Contents: Read** only. It has no admin, secret-reading, actions-write, or repository-write permission. Checkout uses `persist-credentials: false`. Missing credentials fail the run; the workflow never degrades to a silently public-only fleet report.

Artifacts retain 30 days and contain only `advisories-<date>.json`, `sweep-<date>.json`, and `sweep-<date>.md`, all produced by the closed allowlisted serializers. Raw checkouts, `.git`, `revisions.json` with local paths, manifests, lockfiles, native audit output, verbose OSV responses, logs, environment files, and credentials are never uploaded. Artifact names are `consumer-security-intake-<run_id>`, `consumer-security-<slug>-<run_id>`, and `consumer-security-fleet-<run_id>`, so intake, each matrix leg, and the aggregate remain unique within a run. The content's `as_of` supplies the security date.

## Verification

Run from the framework implementation worktree. Hermetic test scratch stays under `.scratch/test-tmp`; generated sweep files stay under `.scratch/rm-076/`.

```bash
python3 skills/authoring-skills/scripts/validate_skill.py --all
python3 scripts/test_consumer_security_sweep.py
python3 scripts/test_fetch_advisories.py
python3 scripts/test_security_register.py
python3 scripts/test_security_handoffs.py
python3 scripts/test_repo_posture.py
python3 scripts/test_security_workflows.py

python3 scripts/consumer_security_sweep.py --list
# Expected, exactly:
# excel-daily-monitor
# marvin-slack
# pln
# pt
# paragon-learning-network

mkdir -p .scratch/rm-076
python3 scripts/consumer_security_sweep.py \
  --from-audit scripts/fixtures/consumer-security \
  --out .scratch/rm-076/a.json --markdown-out .scratch/rm-076/a.md
python3 scripts/consumer_security_sweep.py \
  --from-audit scripts/fixtures/consumer-security \
  --out .scratch/rm-076/b.json --markdown-out .scratch/rm-076/b.md
sha256sum .scratch/rm-076/a.json .scratch/rm-076/b.json
cmp -s .scratch/rm-076/a.json .scratch/rm-076/b.json
sha256sum .scratch/rm-076/a.md .scratch/rm-076/b.md
cmp -s .scratch/rm-076/a.md .scratch/rm-076/b.md

python3 scripts/check_security_register.py
python3 scripts/check_security_register.py \
  --register scripts/fixtures/consumer-security/register.json \
  --sweep .scratch/rm-076/a.json
python3 scripts/check_repo_posture.py --local
python3 -m yamllint -c .yamllint.yaml .github/workflows/
python3 scripts/test_eval_workflows.py
python3 scripts/check_roadmap_verbatim.py
git diff --check
```

Dry-run status-delta proof (the implementation branch may already be dirty):

```bash
git status --porcelain > .scratch/rm-076/status-before.txt
python3 scripts/test_fetch_advisories.py
git status --porcelain > .scratch/rm-076/status-after.txt
cmp -s .scratch/rm-076/status-before.txt .scratch/rm-076/status-after.txt
```

The socket-block proof is inside `test_consumer_security_sweep.py`; a passing ordinary sweep command alone does not satisfy P3-2.

Sanctioned live intake and full gate, using owner-created isolated consumer checkouts under ignored `.scratch/consumer-security-sweep/audit/`:

```bash
python3 scripts/fetch_advisories.py --dry-run \
  --from-audit .scratch/consumer-security-sweep/audit \
  --out .scratch/consumer-security-sweep/audit/snapshot.json
python3 scripts/consumer_security_sweep.py \
  --from-audit .scratch/consumer-security-sweep/audit \
  --controls docs/security/controls.json \
  --out .scratch/consumer-security-sweep/sweep.json \
  --markdown-out .scratch/consumer-security-sweep/sweep.md \
  --check --fail-on high,critical
python3 scripts/check_security_register.py \
  --sweep .scratch/consumer-security-sweep/sweep.json
```

RM-075 input gate (required for final AC11 sign-off, not satisfiable by fixtures):

```bash
python3 scripts/check_security_handoffs.py
```

Owner-run live posture gates (never in `security.yml`):

```bash
python3 scripts/check_repo_posture.py --repo hierovision/ai-framework
python3 scripts/check_repo_posture.py \
  --consumer-inventory reference/consumer-repos.md
```

Post-merge manual validation:

```bash
gh workflow run security.yml --repo hierovision/ai-framework --ref main
gh run list --repo hierovision/ai-framework --workflow security.yml --limit 1
gh run watch --repo hierovision/ai-framework <run-id> --exit-status
```

Inspect the run's four active audit gates and retired `pln` status, then download only its sanitized dated artifacts and verify their schema/hash. Do not download or publish raw checkout material.

## Open Questions

1. **Weekly schedule and release trigger.** Recommended default: Monday at 07:00 UTC plus `workflow_dispatch`; the owner dispatches after every release that changes a propagation control. This exceeds the policy's quarterly minimum and avoids the existing 06:00, 09:00, and 10:30 Monday workflows.
2. **Artifact retention and visibility.** Recommended default: 30 days, matching existing eval artifacts; upload only the three closed-schema sanitized files. Verbose upstream responses, checkouts, and logs remain temporary or in ignored `.scratch/`.
3. **Register format and baseline.** Recommended default: tracked sanitized JSON sorted by `sweep_id`, with the historical Markdown summary kept separate. Seed it from the first new full sweep and current controls, not by inventing unavailable 2026-10-25 raw GHSA rows. Require `review_on` 90 days after `date` by default for new acceptances; an owner may choose a later explicit review date.
4. **Cross-repo read authentication.** Recommended default: a 90-day fine-grained PAT named `CONSUMER_SECURITY_READ_TOKEN`, stored as an environment secret on a `main`-restricted environment and never at repo level, restricted to the four active repos with Contents: Read only. Four consumers are private, so a public-only workflow would not satisfy the five-repo contract. A GitHub App with equivalent read-only access is an acceptable replacement, not an additional deliverable. Record the expiry and its rotation in the detail file when the credential is created.
5. **Dry-run output semantics.** Recommended default: explicit `--out` is the only permitted write in default `--dry-run`; OSV reads still occur, and no manifest/lockfile/package-manager mutation is possible. This resolves original AC3's snapshot-versus-dry-run tension without adding a write mode.
6. **RM-075 dependency at closure.** Recommended default: keep original AC11 strict. Implement and CI-test the checker with synthetic briefs, but leave RM-076 open if the five real scratch briefs are absent. Do not copy briefs into tracked docs, weaken the checker, or author Phase 2 remediation in this pass.
7. **Posture depth in scheduled CI.** Recommended default: invoke only `check_repo_posture.py --local`; run live framework/consumer checks at phase close and after settings changes with the owner's admin-scoped `gh` login. CI never receives those credentials.
8. **Stack-specific design guidance.** Recommended default: proceed generically with Python 3.12 stdlib and the repository's existing GitHub Actions/YAML test patterns. Neither bundled Vue/Next stack reference applies to this framework-side tooling item; no new stack reference is part of RM-076.

## History

- 2026-11-07 — Initial RM-076 draft. Mapped P3-1…P3-5 one-to-one to original AC1–AC4/AC11, added the missing `reference/consumer-repos.md` deliverable, and carried the Phase 3 audit-gate, posture, weekly CI, artifact, documentation, and roadmap scope into P3-6…P3-10.
- 2026-11-07 — Current-tree research at `64251af`: all four primary new scripts, both required primary tests, the register/handoff checkers, `security.yml`, `docs/security/`, and the consumer inventory are absent. `scripts/check_repo_posture.py`, `.github/dependabot.yml`, and the Phase 1 controls exist. The five real handoff briefs are absent in this worktree and untracked by design; they remain RM-075 inputs. No consumer primary checkout or secret was read.
- 2026-11-07 — Read-only GitHub metadata/root-file checks corroborated all five owners, archived/active states, default branches, and root lockfiles: npm for excel/marvin, Yarn v1 for pln/pt, pnpm for paragon. Four active/retired repos are private; only excel is public. These checks did not read consumer working trees or secrets.
- 2026-11-07 — Reconciled original contracts: immutable sweep findings join a separate disposition register; dry-run permits only explicit snapshot output; no-status-delta replaces an impossible empty-status assertion on a dirty implementation branch; handoff closure remains dependent on RM-075; admin posture stays owner-run while CI uses local-only checks.
- 2026-11-07 — Security review of the cross-repo credential: it is an environment secret on a `main`-restricted environment, never repo-level (this repository is public), with the 90-day PAT expiry and rotation recorded when created; the GitHub App remains the acceptable alternative.
- 2026-11-07 — UX consult skipped: no user-facing UI. No matching Vue/Next stack reference applies; generic Python/GitHub Actions planning is recorded in Open Question 8.
