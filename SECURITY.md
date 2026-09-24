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

## Not in scope

- Model-provider side issues (gateway outages, catalog churn) — tracked in
  `reference/model-routing.md`, not a vulnerability in this repo.
- Vulnerabilities in opencode itself — report upstream.

## Dated exceptions

Suppressions/overrides are honored only with a dated record in the affected
file — a quiet exception is never acceptable (the cardinal rule,
`skills/debugging-test-failures/SKILL.md`).
