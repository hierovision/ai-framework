# Consumer exposure record — 2026-10-25

> Sanitized historical summary. It reproduces only the counts, dispositions,
> and decisions already recorded in
> `.opencode/plans/fix-consumer-security-exposure.md`; it is **not** a
> reconstruction of raw audit output, which is not available in this
> repository and must not be re-published.
>
> **Package-manager counts are not comparable.** Yarn v1 reports one advisory
> per resolution path, npm and pnpm report per installed package, and a single
> advisory can appear in several repos. Summing these numbers is meaningless.

## Why this record exists

The 2026-10-25 sweep found that the highest-severity exposures were credential
and CI exposures, not CVEs. Phase 0 contained the live credentials, Phase 1
hardened the framework's propagation controls, and Phase 3 (RM-076) makes the
next sweep a repeatable CI-gated operation. This file keeps the dated
historical picture next to the machine-readable register without inventing
advisory IDs that were never recorded.

## Findings and dispositions

| Repo | Status | Acute exposure (sanitized) | Dependency exposure | Disposition |
|---|---|---|---|---|
| `pln` | retired, archived 2026-10-25 | Duplicate copies of another consumer's live cloud/DB credentials; prod secrets on dev/PR paths; a committed dev password; feature-branch auto-deploy; Actions still enabled. | 195 unique GHSAs: 12 critical / 91 high (yarn audit). | Decommissioned: Actions disabled, duplicate secrets deleted, runs cleared, issues closed, archive. Shared infrastructure retained; no shared key rotated. |
| `paragon-learning-network` | active, production | Preview `workflow_run` executed PR-head code with dev DB/service-role secrets plus a repo-wide deploy token; production migration ungated; 0 approvals under the solo-owner exception. | 15 advisories / 7 packages: 2 critical, 5 high. Criticals latent (no `next/image`, no `use cache`, no Server Actions) but present in the deployed framework. | Preview/prod secrets split, production environment `main`-only, migration gated, dedicated preview token. Dependency upgrade tracked. |
| `pt` / `phasetimer` | active | Tag-pinned production actions, production environment without reviewers, migration before tests, static cloud credential instead of OIDC, production service-role key in a local env file (0644). | 109 unique GHSAs (9 critical / 210 high path entries), **0 runtime-reachable**; remaining are dev/build/test. | Toolchain upgrades, SHA-pinned actions, OIDC, env-scoped prod secrets; local file cleaned and `0600`, production key removed, dev key retained under dated acceptance. |
| `marvin-slack` | active, local service | No CI/alerting, Slack tokens in a local env file, no secret scan. | 2 high packages, both transitive and not reachable (`body-parser`, `undici`). | Overrides planned, local audit/secret hook added, files `0600`. |
| `excel-daily-monitor` | active, public | `main` unprotected; failure artifacts (console/network logs, screenshots) uploaded from a public repo. | 0 findings; Playwright resolved above the advisory's fixed version. Declared floor stale. | Floor bump, `main` ruleset blocks force-push/deletion, failure artifacts redacted. |
| `ai-framework` (this repo) | public supply-chain root | `main` unprotected at the time; Dependabot/secret scanning/push protection/CodeQL off; secret-bearing eval job ran PR-head code. | 4 high in an unused plugin dependency. | Phase 1 hardening delivered (RM-073); RM-076 now keeps detection continuous. |

## What is tracked where

- The dated, per-control disposition rows live in
  `docs/security/register.json` (rows are joined to findings by `sweep_id`).
- Current open control observations live in `docs/security/controls.json`.
- The consumer inventory is `reference/consumer-repos.md`.
- The operator runbook and closed schemas are `docs/security/README.md`.
