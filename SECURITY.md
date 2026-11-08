# Security Policy

## Reporting a vulnerability

**Do not open a public issue for a security report.**

Report privately through [GitHub's private security advisory]
(https://github.com/hierovision/ai-framework/security/advisories/new) for
this repository. Include: the affected file(s) or workflow(s), a
reproduction (commands or a workflow diff), and your assessment of impact.
Expect a first response within 7 days; a fix ships as a normal PR once the
report is triaged.

## In scope

- `install.sh` — the trust boundary every consumer repo executes (the CI
  trust-boundary comments in `eval-behavioral.yml` / `eval-per-change.yml`
  name the risk: running a repo script with broad filesystem access).
- CI token handling — `DEEPSEEK_API_KEY` scoping and redaction
  (ADR-0002), workflow `permissions:`, third-party action SHA-pinning
  (see `skills/securing-ci/SKILL.md`).
- Skill scripts (`scripts/*.py`, `skills/*/scripts/*.py`) — anything a
  consumer agent or harness would execute.
- The eval event-stream persistence path — model outputs + repo content
  are persisted as CI artifacts in a PUBLIC repo (the governance comment
  in the eval workflows); the redaction rule is the compensating control.
- **Consumer fleet (known).** This library's propagation controls reach five
  known consumer repos: `excel-daily-monitor`, `marvin-slack`, `pln`
  (retired/archived 2026-10-25), `pt`/`phasetimer`, and
  `paragon-learning-network`. The authoritative enumeration is
  `reference/consumer-repos.md`. An exposure that traces to a framework control
  (`install.sh`, the eval harness, a skill script, redaction, or a dependency
  pin) is in scope here; repo-local findings are fixed in that consumer's own
  repo. **Sweep cadence:** a dated sweep on every framework release that
  changes a propagation control, and at least quarterly. The weekly
  `security.yml` sweep (Monday 07:00 UTC) already exceeds that minimum;
  release-impacting propagation-control changes still require an owner
  `workflow_dispatch` run. The 2026-10-25 sweep and Phase 0 containment record
  live with the consumer-security plan; the runbook, closed schemas, disposition
  register, and current controls live in `docs/security/` (`README.md`,
  `register.json`, `controls.json`,
  `consumer-exposure-2026-10-25.md`). Unknown public consumers cannot be
  enumerated — the Phase 1 framework controls are what protect them.

## Not in scope

- Model-provider side issues (gateway outages, catalog churn) — tracked in
  `reference/model-routing.md`, not a vulnerability in this repo.
- Vulnerabilities in opencode itself — report upstream.

## Dated exceptions

Suppressions/overrides are honored only with a dated record in the affected
file — a quiet exception is never acceptable (the cardinal rule,
`skills/debugging-test-failures/SKILL.md`).

### Solo-owner approval exception (2026-11-03)

`main` requires a pull request and the `quality-gates`, `pre-commit-check`, and
`dependency-audit` checks; force-push and deletion are denied. Required approvals are 0 because
the owner is the only engineer on this repository and GitHub does not count
the author's own approval. Compensating controls: required CI, secret scanning
+ push protection, Dependabot alerts + security updates, and CodeQL default
setup. Review date: 2027-01-25, or when a second engineer is added.

### Eval-fixture advisories (2026-11-07)

`skills/auditing-supply-chain/evals/fixtures/**` intentionally contains
vulnerable and malicious-looking packages (express, lodash, axios, and the
`lodahs` typosquat shape). The fixtures are inert: npm manifests are stored as
`package.json.fixture` / `package-lock.json.fixture`, so GitHub's dependency
graph and Dependabot never parse them; the eval runner materializes them only
inside a throwaway temp workspace, and nothing installs, resolves, or executes
them. Dependabot alerts on these paths are dismissed as `tolerable_risk`; a
future alert on a fixture path is the same exception. Do not auto-fix a
fixture. Containment contract:
`skills/auditing-supply-chain/evals/fixtures/README.md`; guard:
`scripts/test_eval_workflows.py::test_supply_chain_fixture_manifests_are_inert`.

