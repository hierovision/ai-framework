---
slug: fix-consumer-security-exposure
title: Remediate the 2026-10-25 consumer security exposure sweep and make it repeatable
status: approved
created: 2026-10-25
revised: [2026-10-25, 2026-11-03, 2026-11-06]
related: [RM-012, RM-015, RM-073]
---

# Plan: fix-consumer-security-exposure

> **Roadmap ID note (2026-11-06):** `RM-072` is assigned to the
> delegation-observer milestone-noise row (`docs/roadmap-detail/RM-072.md`).
> This plan's Phase 1 row is **RM-073** (`docs/roadmap-detail/RM-073.md`), added 2026-11-06.

## Goal / Approach

**Goal:** Every security exposure found in the 2026-10-25 sweep of ai-framework
and its five known consumer repos is fixed, explicitly accepted with a date, or
decommissioned — and the next sweep is a repeatable, CI-gated operation rather
than a manual audit.

**Approach:** Four phases, because the findings split by who can fix them:

- **Phase 0 — owner containment (same day, not code).** Revoke/decommission
  the retired `pln` credential store; split the shared preview/production SWA
  token; add human gates to production environments; protect `main` and enable
  secret scanning on this public repo. These are the only findings that are
  live credentials, and they must not wait for a plan approval.
- **Phase 1 — framework hardening (this repo, one implement pass).** Close the
  framework's own consumer-propagation gaps: PR-branch code no longer reaches
  provider secrets without a gate; redaction covers secret shapes beyond three
  env values; the eval child env is allowlisted; the auth/session store is no
  longer an agent read root; skill-local dependencies are pinned and never
  resolved through a consumer repo; untrusted content is fenced as data.
- **Phase 2 — per-consumer remediation (one pass per consumer repo).** Five
  handoff briefs carry exact versions, commands, and verification. Each runs in
  its own repo under `reference/cross-repo-isolation.md` (worktree, never the
  primary checkout). This plan does not edit consumer repos.
- **Phase 3 — continuous detection.** A sanctioned advisory snapshot step, an
  offline sweep tool, per-repo audit gates, Dependabot/secret-scanning posture,
  and a dated register. "Latest" becomes a weekly command, not a one-off.

If Phase 1 exceeds one implement checkpoint, split at a phase boundary (CI
isolation, then tooling, then dependencies); every commit keeps the full
verification suite green.

The sweep is point-in-time. It covers the five known consumers on this machine
(`excel-daily-monitor`, `marvin-slack`, `pln`, `pt`/phasetimer,
`paragon-learning-network`). Unknown public consumers of this library cannot be
enumerated; the Phase 1 framework controls are what protect them. No finite
sweep proves "all" — the plan makes the next sweep cheap, dated, and repeatable.

### Findings register (2026-10-25)

Acute, non-dependency findings first. Full detail:
`.scratch/consumer-security-sweep/{consumer-posture,paragon-deps,consumer-deps}.md`.

| Repo | Acute exposure | Dependency exposure | Disposition |
|---|---|---|---|
| `pln` (retired, **repo archived 2026-10-25**) | 22 repo secrets, many duplicate copies of paragon's live Azure/Supabase credentials; prod secrets passed to dev/PR-preview jobs; committed dev password; feature-branch auto-deploy; Actions still enabled. **Step 0 found the `pln` resource group, `pln-prod` SWA, `pln-insights`, and the `pln-dev`/`pln-prod` Supabase projects are paragon's live infrastructure.** | 195 unique GHSAs: 12 critical / 91 high (yarn audit) | Repo decommissioned: Actions disabled, 22 duplicate secrets deleted, runs cleared, issues closed, archive. Shared resources retained; no shared key rotated. Residuals: shared dev password and Porkbun/Pulumi provider keys; legacy SPs and Pulumi stacks removed. Runbook: `.scratch/consumer-security-sweep/pln-decommission-runbook.md`. |
| `paragon-learning-network` (active, production) | Preview `workflow_run` checks out PR-head code and executes it with dev DB/service-role secrets plus a repo-wide SWA token that also deploys production; `migrate-prod` ungated; 0 approvals is accepted under the solo-owner exception, but required checks/no-force-delete must still be enforced. **Uses the legacy `pln-dev`/`pln-prod` Supabase projects and the `pln-prod` SWA; the `pln` repo holds duplicate credentials for them.** | 15 advisories / 7 packages: 2 critical (`next` 16.3.8, min fixed 16.4.1), 5 high (`next`, `sharp`, `vite`, `zod`, `source-map-js`). Next criticals are latent (no `next/image`, no `use cache`, no Server Actions) but in the deployed framework. | P0 Next 16.4.3; split preview/prod secrets; 0 approvals + dated solo-owner exception + required checks; CI audit gate. |
| `pt` / phasetimer (active) | Tag-pinned actions on the prod path (`static-web-apps-deploy@v1`, `supabase/setup-cli@v1` + `version: latest`, `azure/login@v2`); production env no reviewers; `migrate-prod` before tests; static Azure SP instead of OIDC; prod service-role key in local `.env` (0644) | 109 unique GHSAs (9 critical / 210 high path entries) but **0 runtime-reachable**; remaining are dev/build/test | Batch toolchain upgrades; SHA-pin actions; OIDC; env-scoped prod secrets; verify before migrate. |
| `marvin-slack` (active, local service) | No CI/alerting; Slack tokens in local `.env` (0600); no secret scan | 2 high packages, both transitive and not reachable (Socket Mode; undici used only as WebSocket): `body-parser` 2.3.0, `undici` 7.29.1 | Add npm overrides; add local audit/secret hook; harden systemd. |
| `excel-daily-monitor` (active, public) | `main` unprotected; failure artifacts (console/network logs, screenshots) uploaded from a public repo | 0 findings; Playwright resolved 1.63.0 (advisory fixed 1.55.1); declared floor `^1.49.0` is stale | Bump floor; protect main; redact artifacts; enable CodeQL. |
| `ai-framework` (this repo, public supply-chain root) | `main` unprotected; Dependabot/secret scanning/push protection/CodeQL all off; secret-bearing eval job runs PR-head `install.sh` and runner; redaction only 3 env keys; `log_run.py` has no redaction; 7 agents have no permission block; auth/session store is a read root; bundled Playwright lockfile is untracked and `auditing-accessibility` resolves `axe-core` from the consumer's CWD `node_modules`; unpinned `pip install pyyaml/yamllint`; `skills/validating-ui/node_modules` locally symlinks into paragon | 4 high in unused `@opencode-ai/plugin` 1.18.1 (`effect`, `toml`, `zod`) | Phase 1 hardening; remove unused plugin; enable repo security settings. |

**The headline:** the highest-severity findings are credential and CI
exposures, not CVEs. Dependency counts are not comparable across package
managers; yarn v1 counts one advisory per resolution path.

### Phase 0 containment checklist (owner, before plan approval)

Do these first; they are live-credential exposures, not code changes.

- `hierovision/pln`: follow
  `.scratch/consumer-security-sweep/pln-decommission-runbook.md` — disable
  Actions, delete the 22 duplicate repo secrets, clean caches/runs, archive
  (or delete) the repo. **Do not delete the `pln` resource group, the
  `pln-prod` SWA, `pln-insights`, or the `pln-dev`/`pln-prod` Supabase
  projects; do not reset the `pln-prod` SWA token or rotate the shared
  Supabase keys without updating paragon; do not run `pulumi destroy` or
  `terraform destroy`.** Rotate the committed dev password only with
  paragon's dev environment in the loop.
- `Stonegate-Software/paragon-learning-network`: rotate the repo-wide
  `AZURE_STATIC_WEB_APPS_API_TOKEN`; create a separate preview SWA + token;
  move dev/prod secrets to environment secrets; restrict `production` to
  `main` with a wait timer; add `environment: production` to `migrate-prod`;
  record the solo-owner exception (0 approvals) and keep required checks +
  no force/delete.
- `hierovision/phasetimer`: remove production service-role keys from local
  `.env*` and `chmod 600`; rotate the shared SWA token; move prod secrets to
  the `production` environment; restrict it to `main` + wait timer; record the
  solo-owner exception; replace `AZURE_CREDENTIALS` with OIDC.
- `hierovision/ai-framework`: protect `main` (PR + required checks, no
  force/delete); record the solo-owner exception; enable Dependabot alerts +
  security updates, secret scanning + push protection, and CodeQL.
- `hierovision/excel-daily-monitor`: add a `main` ruleset (PR + required
  checks, no force/delete); record the solo-owner exception; redact or drop
  `console.log`/`network.log` from public failure artifacts.
- `hierovision/marvin-slack`: `chmod 600 .env`; add a local pre-commit secret
  scan; rotate Slack tokens only if the file left the host.

### Phase 0 execution record (2026-11-03)

Every GitHub setting below was read back from the API after the write. "Plan"
means the repository's GitHub plan rejects the feature (403/422); "privacy"
means a secret value cannot be read or moved through the API.

| Repo | Applied | Blocked | Owner-run residual |
|---|---|---|---|
| `hierovision/ai-framework` | `main` requires a PR + `quality-gates` + `pre-commit-check`, enforce admins, no force/delete, conversation resolution; secret scanning + push protection; Dependabot alerts + security updates; CodeQL default setup; dated solo-owner exception ([PR #142](https://github.com/hierovision/ai-framework/pull/142), merged `1a88483`) | — | — |
| `Stonegate-Software/paragon-learning-network` | Dependabot alerts + security updates; secret scanning + push protection; `production` main-only; [PR #52](https://github.com/Stonegate-Software/paragon-learning-network/pull/52) merged `85170424` (`migrate-prod` gated); fork guards merged `a1467546` ([PR #53](https://github.com/Stonegate-Software/paragon-learning-network/pull/53)); dedicated preview SWA `pln-preview` with its own token, role assignment, docs, and verified preview/close path ([PR #55](https://github.com/Stonegate-Software/paragon-learning-network/pull/55), merged `134b82ce`) | wait timer (422, plan); CodeQL (403, Code Security not enabled) | — |
| `hierovision/excel-daily-monitor` | `main` ruleset blocks force-push and deletion; secret scanning + push protection (already on); Dependabot alerts; CodeQL; [PR #9](https://github.com/hierovision/excel-daily-monitor/pull/9) merged `693488da` (drops `console.log`/`network.log` from failure artifacts and documents the policy) | PR requirement + required status checks: the scheduled `daily-summary` workflow commits data to `main` with `GITHUB_TOKEN` and that commit is the deployment path; the Actions integration cannot be a ruleset bypass actor on this personal repo (422), and no PR CI exists | — |
| `hierovision/marvin-slack` | Dependabot alerts + security updates; `.env` already `0600`; pre-commit secret scan [PR #13](https://github.com/hierovision/marvin-slack/pull/13) merged `533baf8f` (21 scanner tests + 217/217 suite) | branch protection/rulesets (403, private free plan); secret scanning (422, private free plan) | hook installed 2026-11-06 (`core.hooksPath=.githooks`, scanner smoke test passed; `.env` 0600); Slack token rotation only if the file left the host |
| `hierovision/phasetimer` | Dependabot alerts + security updates; `production` main-only; GitHub OIDC app + main federated credential + `Phasetimer SWA Provisioner` role + repo vars; `azure-dns-config.yml` uses OIDC; static `AZURE_CREDENTIALS` deleted; SWA token rotated and preview-verified; `SECURITY.md` exception; Playwright jobs pinned to `ubuntu-24.04` ([PR #52](https://github.com/hierovision/phasetimer/pull/52), merged `b85ad30b`); manual OIDC check green | branch protection/rulesets (403, private free plan); wait timer (422, plan); secret scanning (422, private free plan) | Local env cleaned 2026-11-06: `~/repos/pt/.env.local` and `.env.test.local` are now 0600 and no longer contain `SUPABASE_SERVICE_ROLE_KEY_PROD`; the dev `SUPABASE_SERVICE_ROLE_KEY` is retained for local access. They contain no `PROD_SUPABASE_DB_URL`/DB password; the new DB password is only the GitHub `production` secret. Owner attests the keys never left the host; no rotation performed (dated acceptance). |
| `hierovision/pln` | already decommissioned and archived 2026-10-25 | — | — |

Facts confirmed before the pass: ai-framework `main` was unprotected and every
security feature was off; excel `main` was unprotected; paragon `main` already
required `verify` with no force/delete; paragon's `production` environment
already restricted deployments to `main`.


### Revised 2026-11-06 — Phase 0 closed; Phase 1 reconciled with the OpenCode V2 tree

Phase 0 is closed: ai-framework protections and security features, paragon's
fork guards + preview/prod token split + rotated production token +
environment-scoped production secrets, excel's force-push/deletion ruleset,
phasetimer's OIDC + rotated token + environment-scoped DB secret + CLI pin,
marvin's installed pre-commit secret scan, and pln's decommission.

Phase 1 is the framework's own propagation controls, on the V2 tree:

- `eval-per-change` still runs the `evals` job on same-repo PR-head code with
  repository provider keys. P1-1 makes the secret-bearing eval **main-only**,
  moves the provider keys to the `eval` environment, and keeps the PR path on
  the no-secret `pre-commit-check`/`plan` jobs. OQ12 resolved main-only.
- Redaction is value-match on three env keys and `log_run.py` does not redact;
  P1-2 makes it pattern-based.
- `sandbox_env` is a deny-list of `GITHUB_*`/`RUNNER_*`, not an allowlist;
  P1-3 allowlists the child env.
- `dispatch-profiles.json` still grants `$HOME/.local/share/opencode` to four
  profiles; P1-4 removes it. The V2 leaf agents deny `subagent`.
- `reference/untrusted-content.md` does not exist; P1-5 adds it and cites it
  from the five input-handling skills.
- `playwright` is a caret range, the lockfile is untracked, and
  `auditing-accessibility` resolves `axe-core` from `NODE_PATH`/skill-local;
  P1-6 pins and contains them.
- CI `pip install` lines are unpinned; P1-7 adds `scripts/ci-requirements.txt`
  with hashes.
- Phase 0's repo settings are live but not checker-enforced and
  `.github/dependabot.yml` is absent; P1-8 adds both.
- `install.sh` has no manifest/`--check`; P1-9 adds the interim manifest.
- `.opencode/package.json` still pins the unused V1 `@opencode-ai/plugin`
  1.18.1; P1-10 removes it (the V2 plugins are `plugins/*`).
- `SECURITY.md` does not name the consumer fleet/sweep cadence; P1-11 records
  it.

Phase 3 tooling (sweep/advisory/register/handoff/`security.yml`) and Phase 2
consumer remediation are **not** this pass; the original AC1–AC4 and AC11
remain Phase 3/2. The Phase 1 row is RM-073.


## Acceptance Criteria

1. The consumer inventory is explicit and machine-readable —
   `python3 scripts/consumer_security_sweep.py --list` prints exactly the five
   slugs in `reference/consumer-repos.md`, and
   `python3 scripts/test_consumer_security_sweep.py` asserts the set and each
   repo's status (`active` / `retired`).

2. The offline sweep is deterministic — running
   `python3 scripts/consumer_security_sweep.py --from-audit <fixture-dir> --out a.json`
   twice produces byte-identical output (`sha256sum` equal), and the same test
   blocks sockets so any network call fails the test.

3. Advisory intake is a separate, user-approved step with provenance —
   `python3 scripts/fetch_advisories.py --out snapshot.json` writes `as_of`,
   `source`, `queries[]`, and `results[]`; the default is `--dry-run`;
   `git status --porcelain` is empty after a dry run (no lockfile or manifest
   mutation). `python3 scripts/test_fetch_advisories.py` exits 0.

4. Every finding carries a disposition — `python3 scripts/check_security_register.py`
   exits 0 against the register; each row has repo, advisory/control ID,
   severity, runtime/dev, framework-propagated/consumer-local, disposition
   (`fix`/`accepted`/`decommission`), owner, and date; every ID in the sweep
   report appears exactly once.

5. No fork PR can reach provider secrets — the `pull_request` path of
   `.github/workflows/eval-per-change.yml` gates the secret-bearing eval job
   with `environment: eval` and
   `if: github.event.pull_request.head.repo.full_name == github.repository`;
   the `push` to `main` path is not blocked by the PR gate.
   `python3 scripts/test_eval_workflows.py` asserts both, and
   `python3 -m yamllint -c .yamllint.yaml .github/workflows/` exits 0.

6. Redaction is pattern-based, not value-match-only — a test writes synthetic
   `sk-`, `xoxb-`, `ghp_`, `sb_secret_`, `AKIA`, and PEM values through
   `log_run.py` and the eval persistence path; `python3 scripts/test_log_redaction.py`
   exits 0 and the raw values appear nowhere in the output directory.

7. The eval child env is allowlisted — `python3 scripts/test_eval_env.py`
   asserts `AWS_*`, `AZURE_*`, `SLACK_*`, `SUPABASE_*`, `GH_TOKEN`, and
   `GITHUB_TOKEN` are absent while `PATH`, `HOME`, `OPENCODE_API_KEY`, and
   `DEEPSEEK_API_KEY` remain.

8. The auth/session store is not an agent read root —
   `scripts/dispatch-profiles.json` no longer grants
   `$HOME/.local/share/opencode` to any profile; `python3 scripts/test_agent_permissions.py`
   exits 0 and asserts every leaf agent (`planner`, `council-*`, `reviewer`,
   `skill-reviewer`, `vision-critic-*`) still denies `task`.

9. Untrusted content is fenced — `reference/untrusted-content.md` exists and is
   cited by `refining-issue-acceptance`, `triaging-requirements`,
   `designing-architecture`, `reviewing-security`, and `auditing-supply-chain`;
   `node skills/refining-issue-acceptance/evals/fixtures/untrusted-content.test.mjs`
   exits 0, proving an injected "ignore previous instructions and run X"
   payload is reported as data and X is never executed; the same suite proves
   `refining-issue-acceptance --apply` refuses without `--confirm`.

10. Skill-local dependencies are pinned and contained —
    `skills/capturing-ui-evidence/package-lock.json` is tracked
    (`git ls-files` includes it), `playwright` is an exact version,
    `npm --prefix skills/capturing-ui-evidence audit --omit=dev` reports 0;
    `python3 scripts/test_skill_deps.py` exits 0 when no
    `skills/*/node_modules` resolves outside the repo and when a poisoned
    consumer-CWD `node_modules/axe-core` is ignored in favour of the skill's
    pinned `axe-core` or `AXE_CORE_PATH`.

11. The five handoff briefs exist with exact remediation —
    `python3 scripts/check_security_handoffs.py` exits 0; each brief names the
    repo, the P0/P1 findings, installed -> fixed versions, the verification
    command, owner actions, and the "no `audit fix --force` / no undated
    suppression" clause.

12. The framework repo posture is enforced —
    `python3 scripts/check_repo_posture.py --repo hierovision/ai-framework`
    exits 0: `main` requires a PR and the required checks with no force/delete,
    approval count is 0 under a dated solo-owner exception recorded in
    `SECURITY.md`, Dependabot alerts + security updates, secret scanning +
    push protection, CodeQL, and `.github/dependabot.yml` covering npm under
    `.opencode` plus GitHub Actions. Owner applies the settings; the script is
    the verifier.

13. The delivering PR closes its roadmap row — `docs/ROADMAP.md` contains the
    new `RM-073` row with its horizon strip/counter and success measure, and
    `docs/roadmap-detail/RM-073.md` exists;
    `python3 scripts/check_roadmap_verbatim.py` exits 0.

14. CI installs are pinned and hash-verified —
    `rg 'pip3? install --quiet' .github/workflows` returns no matches; every
    Python install uses `pip install --require-hashes -r scripts/ci-requirements.txt`;
    `pip install --require-hashes -r scripts/ci-requirements.txt` exits 0 in a
    clean venv; the requirements file pins `pyyaml` and `yamllint` with hashes.


### Revised 2026-11-06 — Phase 1 acceptance criteria (current tree)

The Phase 1 set below supersedes AC5–AC10, AC12 and AC14 for the current
tree; AC13 is delivered by the RM-073 row/detail in this pass. The original
AC1–AC4 and AC11 remain Phase 3/2.

P1-1 **Main-only secret-bearing eval + eval environment.** The `evals` job in
`.github/workflows/eval-per-change.yml` runs only on `push` to `main` and
declares `environment: eval`; the `pull_request` path keeps the no-secret
`pre-commit-check` and `plan` jobs and never starts `evals`. The provider
keys are `eval` environment secrets, not repository secrets. The `eval`
environment's branch policy is `main`. — Verifier:
`python3 scripts/test_eval_workflows.py` asserts the `evals` event guard (no
`pull_request`), the environment, the push-main path and the no-secret PR
jobs; the owner sets the `eval` environment secrets and `gh api
repos/hierovision/ai-framework/environments/eval/secrets` lists them; a main
run is green and a PR run has no `evals` job; `python3 -m yamllint -c
.yamllint.yaml .github/workflows/` exits 0.


P1-2 **Pattern redaction.** `log_run.py` redacts free-text `detail` before
append and the eval persistence redacts `sk-`, `xoxb-`, `ghp_`,
`github_pat_`, `sb_secret_`, `AKIA…`, PEM headers and provider-key values; a
synthetic value never appears in the output. — Verifier:
`python3 scripts/test_log_redaction.py` exits 0 and greps the output
directory for the raw values.

P1-3 **Eval child env allowlist.** `sandbox_env` returns only the allowlisted
keys (PATH, HOME, PWD/TMPDIR, XDG, `OPENCODE_API_KEY`, `DEEPSEEK_API_KEY`,
`OPENCODE_LOG_LEVEL`, `OPENCODE_DB`, `OPENCODE_CONFIG_CONTENT`); `AWS_*`,
`AZURE_*`, `SLACK_*`, `SUPABASE_*`, `GH_TOKEN`, `GITHUB_TOKEN` are absent. The
runner's own `BEVAL_*` config stays in the parent process, not the child. —
Verifier: `python3 scripts/test_eval_env.py` exits 0.

P1-4 **Auth/session store is not a read root.** No profile in
`scripts/dispatch-profiles.json` grants `$HOME/.local/share/opencode`; every
leaf agent (planner, council-*, reviewer, skill-reviewer, vision-critic-*)
denies `subagent`. — Verifier: `python3 scripts/test_agent_permissions.py`
exits 0.

P1-5 **Untrusted content fence.** `reference/untrusted-content.md` exists and
is cited by refining-issue-acceptance, triaging-requirements,
designing-architecture, reviewing-security and auditing-supply-chain. —
Verifier:
`node skills/refining-issue-acceptance/evals/fixtures/untrusted-content.test.mjs`
exits 0; the five skill files contain the citation.

P1-6 **Skill deps pinned/contained.** `skills/capturing-ui-evidence/package-lock.json`
is tracked; `playwright` is exact; `npm audit --omit=dev` reports 0;
`skills/auditing-accessibility` resolves `axe-core` from `AXE_CORE_PATH` or
its own pinned install, never the consumer CWD. — Verifier:
`python3 scripts/test_skill_deps.py` exits 0.

P1-7 **CI installs pinned.** No `pip install --quiet` in the workflows; every
Python install uses `--require-hashes -r scripts/ci-requirements.txt`;
`pyyaml` and `yamllint` are hash-pinned. — Verifier:
`rg 'pip3? install --quiet' .github/workflows` returns nothing;
`pip install --require-hashes -r scripts/ci-requirements.txt` exits 0 in a
clean venv.

P1-8 **Posture/dependabot enforced.** `python3 scripts/check_repo_posture.py
--repo hierovision/ai-framework` exits 0 against the Phase 0 settings;
`.github/dependabot.yml` covers npm under `.opencode`, `plugins/*`,
`skills/capturing-ui-evidence` (and `skills/auditing-accessibility` if it
gains a package) plus GitHub Actions. — Verifier: the script exits 0; the
workflow YAML passes `yamllint`.

P1-9 **Install manifest.** `install.sh` writes
`~/.config/opencode/.ai-framework-install.json` (repo path, HEAD SHA, dirty
flag, timestamp) and supports `--check`/`--require-clean` without changing
symlink semantics. — Verifier: `bash scripts/test_install_sh.sh` exits 0 in a
temp HOME.

P1-10 **No unused V1 plugin pin.** `.opencode/package.json` no longer pins
`@opencode-ai/plugin` 1.18.1; the V2 plugins are `plugins/*` on
`@opencode/plugin` 2.2.5. — Verifier:
`grep -R '@opencode-ai/plugin' .opencode/package.json` is empty;
`plugins/*/package.json` shows the V2 pin.

P1-11 **Consumer fleet/sweep record.** `SECURITY.md` names the five known
consumers and the sweep cadence. — Verifier: `grep` of `SECURITY.md` shows
the five slugs and the cadence; `python3 scripts/check_roadmap_verbatim.py`
exits 0.


## Files to Modify

Framework (this repo):

- `reference/consumer-repos.md` — new; the five known consumers, owner/slug,
  active/retired, stack, lockfile path, sweep cadence.
- `reference/untrusted-content.md` — new; data-fence + confirmation contract
  for issue bodies, pasted backlogs, repo content, and child-agent results.
- `docs/security/README.md` — new; cadence, severity mapping (CVSS/OSV to
  blocker/major/minor/nit), disclosure rule, dated-acceptance rule.
- `docs/security/consumer-exposure-2026-10-25.md` — new; sanitized register
  (no secret names/values, no exploit preconditions).
- `scripts/consumer_security_sweep.py` — new; enumerate consumers, ingest
  npm/pnpm/yarn audit JSON or an advisory snapshot, classify
  framework-propagated vs consumer-local and runtime/dev, emit deterministic
  JSON + Markdown.
- `scripts/fetch_advisories.py` — new; the only network step (OSV), dry-run
  by default, provenance snapshot, no package/lockfile mutation.
- `scripts/check_security_register.py` — new; register schema + coverage check.
- `scripts/check_security_handoffs.py` — new; handoff completeness check.
- `scripts/check_repo_posture.py` — new; `gh api` assertions for the framework
  repo (owner-run; not a CI gate).
- `scripts/test_consumer_security_sweep.py` — new; golden fixture + socket
  block.
- `scripts/test_fetch_advisories.py` — new; provenance + no-mutation test.
- `scripts/test_log_redaction.py` — new; synthetic secret shapes.
- `scripts/test_eval_env.py` — new; allowlist assertions.
- `scripts/test_agent_permissions.py` — new; leaf deny + no auth-store root.
- `scripts/test_skill_deps.py` — new; lockfile tracked + no external symlink +
  poisoned-CWD `axe-core` ignored.
- `scripts/ci-requirements.txt` — new; hash-pinned `pyyaml` + `yamllint` for
  every workflow install.
- `scripts/test_install_sh.sh` — new; temp-HOME install, manifest write,
  `--check` drift detection, `--require-clean` failure on a dirty tree.
- `skills/authoring-skills/scripts/run_behavioral_eval.py` — pattern redaction;
  child-env allowlist; redact `OPENCODE_CONFIG_CONTENT`.
- `skills/observing-runs/scripts/log_run.py` — redact free-text `detail`
  before append; no behavior change to the schema.
- `.github/workflows/eval-per-change.yml` — fork guard + `environment: eval`
  on the secret-bearing job; exclude raw `eval-streams/**` from PR artifacts
  (redacted streams only).
- `.github/workflows/ci.yml` — run the new hermetic suites; add the
  dependency-audit job for `.opencode` and `skills/capturing-ui-evidence`;
  replace unpinned `pip install` lines with `--require-hashes -r
  scripts/ci-requirements.txt`.
- `.github/workflows/security.yml` — new; weekly OSV/audit sweep against the
  consumer inventory, uploads the dated snapshot + report, opens no PRs;
  hash-pinned Python installs.
- `.github/workflows/eval-behavioral.yml` + `.github/workflows/eval-per-change.yml`
  — replace unpinned `pip install --quiet pyyaml` with the hash-pinned
  requirements file; no secret-echo change.
- `.github/dependabot.yml` — new; npm (`.opencode` and
  `skills/capturing-ui-evidence`) + GitHub Actions, weekly.
- `.opencode/package.json` + `.opencode/package-lock.json` — remove the unused
  `@opencode-ai/plugin` dependency (no import exists in the repo); if a plugin
  is added later, pin and audit it.
- `scripts/dispatch-profiles.json` — remove `$HOME/.local/share/opencode` from
  `allow_dirs` (auth/session store); keep the repo roots.
- `install.sh` — write `~/.config/opencode/.ai-framework-install.json`
  (repo path, HEAD SHA, dirty flag, timestamp); add `--check` and
  `--require-clean`; no change to symlink semantics.
- `.gitignore` — stop ignoring `skills/capturing-ui-evidence/package-lock.json`
  and `skills/auditing-accessibility/package-lock.json` (keep `node_modules/`
  ignored).
- `skills/capturing-ui-evidence/package.json` + `package-lock.json` — pin
  `playwright` exact; commit the lock; update `SKILL.md` dependency-resolution
  guidance to `npm ci` / `NODE_PATH`, never an ad-hoc install into the
  framework checkout.
- `skills/validating-ui/SKILL.md` — same dependency guidance; remove the
  cross-repo `node_modules` symlink assumption.
- `skills/auditing-accessibility/scripts/audit.mjs` — resolve `axe-core` from
  `AXE_CORE_PATH` or the skill's pinned install, never the consumer CWD;
  `skills/auditing-accessibility/package.json` + `package-lock.json` — new;
  pin `playwright` + `axe-core` exact.
- `skills/refining-issue-acceptance/SKILL.md` — cite
  `reference/untrusted-content.md`; require explicit confirmation for `--apply`.
- `skills/triaging-requirements/SKILL.md` — cite the fence for pasted backlogs.
- `skills/designing-architecture/SKILL.md` — cite the fence for roadmap/issue
  input.
- `skills/reviewing-security/SKILL.md` — cite the fence for repo content.
- `skills/auditing-supply-chain/SKILL.md` + `references/method.md` — add the
  `known-advisory` signal class (consumes a supplied snapshot as data), a
  severity-normalization subsection, and a
  `framework-propagated`/`consumer-local` triage column.
- `docs/ROADMAP.md` + `docs/roadmap-detail/RM-073.md` — add the Now row and
  detail file; close them in the delivering PR.
- `SECURITY.md` — add the consumer fleet and sweep cadence to "In scope".

Scratch-only (not committed):

- `.scratch/consumer-security-sweep/handoff-{paragon-learning-network,pt,marvin-slack,excel-daily-monitor,pln}.md`
  — per-repo briefs generated from the three sweep reports and this register.


### Revised 2026-11-06 — Phase 1 files (current tree)

- `.github/workflows/eval-per-change.yml` — `environment: eval` on `evals`;
  fork guard; keep the push-main path; V2 install/env unchanged.
- `skills/authoring-skills/scripts/run_behavioral_eval.py` — pattern
  redaction; `sandbox_env` allowlist; redact `OPENCODE_CONFIG_CONTENT`.
- `skills/observing-runs/scripts/log_run.py` — redact `detail`.
- `scripts/test_log_redaction.py` — new.
- `scripts/test_eval_env.py` — new.
- `scripts/test_eval_workflows.py` — fork guard/environment/push assertions.
- `scripts/dispatch-profiles.json` — remove `$HOME/.local/share/opencode`.
- `scripts/test_agent_permissions.py` — new; V2 `subagent` deny + no auth
  store.
- `reference/untrusted-content.md` — new.
- `skills/refining-issue-acceptance/SKILL.md`,
  `skills/triaging-requirements/SKILL.md`,
  `skills/designing-architecture/SKILL.md`,
  `skills/reviewing-security/SKILL.md`,
  `skills/auditing-supply-chain/SKILL.md` — cite the fence.
- `skills/refining-issue-acceptance/evals/fixtures/untrusted-content.test.mjs`
  — the fence test.
- `skills/capturing-ui-evidence/package.json` + `package-lock.json` — exact
  `playwright`, tracked lock, `npm ci`.
- `skills/capturing-ui-evidence/SKILL.md` — dependency-resolution guidance.
- `skills/auditing-accessibility/package.json` + lock (if absent, add);
  `scripts/audit.mjs` — `AXE_CORE_PATH`/skill-local axe, never the consumer
  CWD.
- `skills/validating-ui/SKILL.md` — same guidance; `skills/validating-ui/package.json`
  + `package-lock.json` — new (n2 deviation: the pinned `playwright` install
  that replaces the cross-repo `node_modules` symlink `smoke.mjs` relied on).
- `scripts/test_skill_deps.py` — new.
- `.gitignore` — stop ignoring the two skill lockfiles.
- `scripts/ci-requirements.txt` — new; hash-pinned `pyyaml`/`yamllint`.
- `.github/workflows/ci.yml` — new suites; dependency-audit job; hash-pinned
  Python installs.
- `.github/workflows/eval-behavioral.yml`, `.github/workflows/eval-per-change.yml`
  — hash-pinned Python installs.
- `.github/dependabot.yml` — new; npm `.opencode`, `plugins/*`,
  `skills/capturing-ui-evidence` (and auditing-accessibility if applicable);
  GitHub Actions.
- `scripts/check_repo_posture.py` — new; owner-run.
- `install.sh` — manifest, `--check`, `--require-clean`.
- `scripts/test_install_sh.sh` — new.
- `.opencode/package.json` — remove the V1 plugin pin (host/ignored).
- `SECURITY.md` — consumer fleet/sweep cadence.
- `docs/ROADMAP.md` + `docs/roadmap-detail/RM-073.md` — the row/detail.


## Scope

**Included**

- Phase 0 owner actions with exact targets and commands (the user executes;
  the plan records them).
- Phase 1 framework hardening, sweep tooling, register, and handoff briefs.
- Per-consumer remediation instructions with exact versions and verification.
- Continuous detection: weekly sweep, CI audit gates, Dependabot config, repo
  posture checks.
- Roadmap row and detail file for the program.

**Excluded**

- Editing any consumer repo in this pass. Each consumer change runs in its own
  repo, on its own branch/worktree, with its own verification and PR.
- Rotating or reading secret values. The plan names secret locations/types
  only; the owner revokes and rotates.
- A full agent permission matrix for the seven unconstrained personas — that
  is RM-008 (encoded boundary manifest); this plan only removes the
  auth/session-store read root and preserves leaf `task: deny`.
- Changing the symlink delivery model to tagged/pinned worktrees — that is
  RM-015; this plan adds the install manifest and `--check` as the interim
  control.
- A new skill for advisory intake. The script + reference contract is the
  smallest coherent change; a skill wrapper is a follow-up if the sweep proves
  repeatable.
- Runtime exploitation, penetration testing, and a full OWASP/ASVS review of
  consumer applications.
- Legal/compliance conclusions and vendor-side model-provider issues.


### Revised 2026-11-06 — Phase 1 scope

**Included:** P1-1…P1-11; the framework's own propagation controls; the
interim install manifest; the posture/dependabot configuration; the
`SECURITY.md` fleet record; the RM-073 row/detail.

**Excluded:** Phase 2 consumer remediation and handoff briefs; Phase 3 sweep,
advisory snapshot, register, handoff checker and weekly `security.yml`; the
OpenCode V2 upgrade; model routing/lane policy; consumer-repo code; a full
RM-008 agent permission matrix; the tagged-worktree install (RM-015); an
`eval` environment required reviewer if that requires a second user (Open
Question 12).


## Schema / Type Impacts

No database, Supabase, or generated-type changes.

New shared JSON contracts (documented in `docs/security/README.md`, validated
by the new scripts):

- Sweep report v1: `schema_version`, `as_of`, `source`, `consumers[]`,
  `findings[]` (`repo`, `advisory_id`, `package`, `installed`, `fixed`,
  `severity`, `scope` = runtime/dev, `origin` =
  framework-propagated/consumer-local, `disposition`, `owner`, `date`).
- Install manifest v1: `repo_path`, `commit`, `dirty`, `installed_at`.

The run-log schema is unchanged; only the `detail` value is redacted before
persistence.


### Revised 2026-11-06 — Phase 1 type/contract impacts

No database or generated types. The install manifest is a new JSON contract
v1 (`repo_path`, `commit`, `dirty`, `installed_at`) documented in
`docs/security/README.md` (Phase 3) and validated by
`scripts/test_install_sh.sh`; the Phase 3 sweep/register/handoff schemas
remain as originally specified. The eval run-log schema is unchanged; only
`detail` is redacted.


## Verification

```bash
python3 skills/authoring-skills/scripts/validate_skill.py --all
python3 scripts/test_consumer_security_sweep.py
python3 scripts/test_fetch_advisories.py
python3 scripts/test_log_redaction.py
python3 scripts/test_eval_env.py
python3 scripts/test_agent_permissions.py
python3 scripts/test_skill_deps.py
python3 scripts/test_eval_workflows.py
python3 scripts/test_dispatch_agent.py
node skills/refining-issue-acceptance/evals/fixtures/untrusted-content.test.mjs
python3 scripts/check_security_register.py
python3 scripts/check_security_handoffs.py
bash -n install.sh
bash scripts/test_install_sh.sh
python3 -m yamllint -c .yamllint.yaml .github/workflows/
npm ci --prefix skills/capturing-ui-evidence
npm --prefix skills/capturing-ui-evidence audit --omit=dev
npm ci --prefix skills/auditing-accessibility
npm --prefix skills/auditing-accessibility audit --omit=dev
pip install --require-hashes -r scripts/ci-requirements.txt
python3 scripts/check_repo_posture.py --repo hierovision/ai-framework   # owner-run
```

After Phase 2 (program exit, not this pass):

```bash
python3 scripts/consumer_security_sweep.py --check --fail-on high,critical
```


### Revised 2026-11-06 — Phase 1 verification (current tree)

- `python3 skills/authoring-skills/scripts/validate_skill.py --all`
- `python3 scripts/test_log_redaction.py`
- `python3 scripts/test_eval_env.py`
- `python3 scripts/test_agent_permissions.py`
- `python3 scripts/test_skill_deps.py`
- `python3 scripts/test_eval_workflows.py`
- `python3 scripts/test_dispatch_agent.py`
- `python3 scripts/check_v2_config.py && python3 scripts/check_v2_config.py --baseline main`
- `python3 scripts/check_v2_surfaces.py`
- `node scripts/verify.mjs`
- `python3 skills/authoring-skills/scripts/test_runner.py`
- `python3 scripts/test_typed_evals.py`
- `python3 scripts/test_session_guard.py`
- `python3 scripts/test_watch_agent.py`
- `python3 scripts/test_observe_completion.py`
- `python3 scripts/test_model_policy.py`
- `python3 scripts/test_registry.py`
- `python3 scripts/test_changed_files.py`
- `python3 scripts/test_quarantine.py`
- `python3 scripts/test_stall_timeout.py`
- `python3 scripts/test_eval_report.py`
- `node skills/refining-issue-acceptance/evals/fixtures/untrusted-content.test.mjs`
- `bash -n install.sh`
- `bash scripts/test_install_sh.sh`
- `python3 -m yamllint -c .yamllint.yaml .github/workflows/`
- `npm ci --prefix skills/capturing-ui-evidence && npm --prefix skills/capturing-ui-evidence audit --omit=dev`
- `npm ci --prefix skills/auditing-accessibility && npm --prefix skills/auditing-accessibility audit --omit=dev`
- `pip install --require-hashes -r scripts/ci-requirements.txt`
- `gh api repos/hierovision/ai-framework/environments/eval/secrets --jq '.secrets[].name'` (owner-run; lists the eval keys)
- `python3 scripts/check_repo_posture.py --repo hierovision/ai-framework` (owner-run)
- `python3 scripts/check_roadmap_verbatim.py`


## Open Questions

1. **Consumer set — confirmed 2026-10-25.** The five repos are the full set:
   `excel-daily-monitor`, `marvin-slack`, `pln`, `pt`/phasetimer,
   `paragon-learning-network`. `pln` is decommission-only; unknown public
   consumers are covered by Phase 1 only.
2. **`pln` disposition.** Decommission (revoke all 22 secrets, disable Actions,
   archive) vs patch-and-retain. Default: decommission — no deployment since
   2024 and the domain now serves paragon.
3. **Paragon preview gate.** Separate preview SWA + token + fork guard vs
   environment reviewer on every preview. Default: separate preview app/token,
   fork guard, environment reviewer for non-owner PRs.
4. **Framework PR eval secrets.** `environment: eval` with a required reviewer
   on same-repo PRs (slower, safer) vs main-only secret-bearing evals. Default:
   environment reviewer; fork PRs never receive secrets.
5. **Delivery model.** Install manifest + `--check` now (this plan) vs pinned
   tag/worktree now (RM-015). Default: manifest now; RM-015 owns pinning.
6. **Agent permissions.** Narrow fix (remove the auth/session-store root) now
   vs the full RM-008 matrix. Default: narrow fix.
7. **Tracked register detail.** Sanitized summary tracked in
   `docs/security/` vs the full register untracked in `.scratch/`. Default:
   sanitized tracked summary; full register stays untracked.
8. **Solo-owner approval policy — resolved 2026-10-25.** The owner is the
   only engineer on all six repos (five consumers + this framework). GitHub
   never counts the PR author's own approval, and environment required
   reviewers must be a different user or team; requiring 1 would lock every
   merge and deploy. Adopt the solo-owner exception everywhere: 0 approvals +
   required status checks + no force/delete + environment branch policy
   (`main` only) + wait timer, with a dated exception in `SECURITY.md` (this
   repo) and each consumer's security/ops doc. Compensating controls: required
   CI, secret scanning + push protection, no PR-head code in a privileged job,
   and the preview/production token split. Review date 2027-01-25 or when a
   second engineer is added.
9. **`pln` incident triage.** If any `pln` secret was exposed beyond the repo
   (CI logs, artifacts, a copied `.env`), open a dated
   `handling-security-incidents` record before revoking, so the timeline and
   blast radius are captured. Default: assume exposure until the secret's
   usage log proves otherwise; revoke first, record in parallel.


### Revised 2026-11-06 — Phase 1 open questions

12. **Eval environment reviewer vs main-only.** **Resolved 2026-11-06 —
    main-only.** The `evals` job runs only on `push` to `main`, carries
    `environment: eval` with a `main` branch policy, and the provider keys are
    environment secrets; the PR path keeps the no-secret checks. Rationale:
    no second account exists; the same-repo PR-head secret path is the last
    exposure; the pre-merge eval signal moves to main. A second-account
    reviewer remains the upgrade if one is added. This supersedes original
    Open Question 4.


13. **`sandbox_env` allowlist contents.** **Resolved 2026-11-06:** the child
    allowlist is PATH, HOME, PWD/TMPDIR, XDG, `OPENCODE_API_KEY`,
    `DEEPSEEK_API_KEY`, `OPENCODE_LOG_LEVEL`, `OPENCODE_DB` and
    `OPENCODE_CONFIG_CONTENT`; everything else is stripped. The runner's
    `BEVAL_*` stays in the parent process, not the child.
14. **Dependabot scope.** **Resolved 2026-11-06:** all tracked npm surfaces —
    `.opencode`, `plugins/*`, `skills/capturing-ui-evidence`,
    `skills/auditing-accessibility` (if it gains a package) — plus GitHub
    Actions.
15. **Posture checker cadence.** **Resolved 2026-11-06:** owner-run at phase
    close and after any repo-settings change; not a CI gate (the token needs
    admin-only scopes).
16. **Phase 3 timing.** **Resolved 2026-11-06:** a separate design pass after
    Phase 1 lands; AC1–AC4/AC11 and `security.yml` wait.


## History

- 2026-11-06 — **Phase 1 implemented and delivered** on
  `feat/rm-073-consumer-security-phase-1`
  ([PR #144](https://github.com/hierovision/ai-framework/pull/144)):
  P1-1…P1-11 (main-only eval on the `eval` environment with a `main` branch
  policy, shared pattern redaction, eval child-env allowlist, auth-store read
  root removed, untrusted-content fence + `--confirm`, pinned/contained skill
  deps, hash-pinned CI, Dependabot + owner-run posture checker, install
  manifest, V1 plugin pin removed, consumer fleet record). Verification: the
  full Phase 1 list green locally; `quality-gates`, `pre-commit-check` and
  `dependency-audit` green on the PR and `evals` skipped there. RM-073 closed
  same-PR (row in Done, detail closure record). Owner residuals: move the
  provider keys to the `eval` environment and delete the repo copies, prove a
  green main eval, write the host manifest post-merge.
- 2026-11-06 — **n1 (allowlist scope).** `sandbox_env` keeps seven POSIX basics
  beyond Open Question 13's list — `LANG`, `LC_ALL`, `LC_CTYPE`, `TERM`,
  `SHELL`, `USER`, `LOGNAME` — so the child behaves like an ordinary
  non-interactive shell. Everything else (cloud, tracker, `GITHUB_*`,
  `RUNNER_*`, `BEVAL_*`) is stripped; the value set is asserted by
  `scripts/test_eval_env.py`.
- 2026-11-06 — **n2 (deviation).** `skills/validating-ui` gains a tracked
  `package.json` + `package-lock.json` pinning `playwright` 1.63.0. It is not
  in the original Files list: removing the cross-repo `node_modules` symlink
  (P1-6) would otherwise break `smoke.mjs`'s `import('playwright')`. One exact
  pin, covered by Dependabot and the CI dependency audit.

- 2026-11-06 — owner approved the Phase 1 plan (P1-1…P1-11; OQ12 main-only;
  OQ13–16 defaults). Implementation handed to the implementer; the PR carries
  the RM-073 row/detail and the Phase 1 code/tests.

- 2026-11-06 — Phase 1 revised against the OpenCode V2 tree: P1-1…P1-11
  (main-only eval/`eval` environment, pattern redaction, child-env allowlist,
  auth-store read root, untrusted-content fence, pinned skill deps,
  hash-pinned CI, posture/dependabot, install manifest, V1 plugin removal,
  consumer fleet record), the current file map and verification, and Open
  Questions 12–16; OQ13–16 closed with the objective defaults and
  OQ12 resolved main-only. The roadmap row is RM-073. UX consult skipped: no
  user-facing UI. No matching vue/next stack reference; proceeds generically
  (original Open Question 8). Open Questions 13–16 closed with the objective
  defaults; OQ12 resolved main-only.

- 2026-11-06 — Phase 0 closed. marvin's pre-commit secret scan is merged
  (`533baf8f`) and installed (`core.hooksPath=.githooks`, smoke test passed;
  `.env` 0600); the phasetimer local env is cleaned (`_PROD` removed, 0600,
  dev key retained, owner attests no exposure); paragon has the fork guards,
  separate preview SWA/token, rotated production token, and environment-scoped
  production secrets; excel has the force-push/deletion ruleset; ai-framework
  has the protections/security features; phasetimer has OIDC, the rotated SWA
  token, the production DB secret, and the CLI pin. Platform-gated residuals
  are recorded (private-free branch protection/wait timer/secret scanning;
  paragon CodeQL; `VITE_SUPABASE_*_PROD` are publishable repo-level values).
  Phase 1 (**RM-073**) is next.

- 2026-10-25 — initial draft from the 2026-10-25 sweep: five consumer repos,
  four delegated lenses (`council-security`, dependency triage, CI/secret
  posture, security-skill review), plus local npm/pnpm/yarn audits and OSV
  metadata. UX consult skipped: no user-facing UI. Headline: credential/CI
  exposures outrank dependency CVEs; `pln` and the paragon preview path are the
  two acute items. Phase 0 is owner containment; Phase 1 is this repo; Phase 2
  is five per-repo handoffs; Phase 3 is continuous detection. Added after the
  skill review: unpinned `pip install` lines in CI and CWD-relative `axe-core`
  resolution in `auditing-accessibility`.
- 2026-10-25 — consumer set confirmed by the owner (five repos; `pln`
  decommission-only). Added the pln decommission runbook. Solo-owner approval
  policy resolved: the owner is the only engineer on all six repos, so every
  repo uses 0 approvals + required checks + no force/delete + environment
  branch policy/wait timer, with a dated exception and a 2027-01-25 review.
- 2026-10-25 — Step 0 investigation corrected the pln decommission scope:
  `pln-prod` SWA is linked to the paragon repo, `pln-insights` and
  `plntfstate3fd93671` are live paragon resources, and `pln-dev`/`pln-prod`
  Supabase projects are paragon's dev/prod. The pln repo is a stale credential
  copy, not a standalone stack; retain the shared resources and delete only
  the duplicate secrets.
- 2026-10-25 — `pln` decommission executed: Actions disabled, 22 duplicate
  secrets deleted, 3 runs deleted, 6 issues closed, repo archived. Paragon
  verified unchanged (5 secrets, `pln-prod` SWA link, `pln-insights`,
  `plntfstate3fd93671`, live site 200, both Supabase projects healthy). Local
  clone kept intact for asset harvesting; only env-file permissions changed.
- 2026-10-25 — pln-specific Azure cleanup completed: the two legacy app
  registrations/service principals and their subscription-wide Contributor
  assignments were removed. The Pulumi `dev`/`prod` stacks referenced deleted
  resource groups (`pln-dev361d0bbb`, `pln-prod3bb1622d`), not the live
  `pln-prod` in RG `pln`; state was exported and the stacks removed with
  `pulumi stack rm --force --preserve-config`, not `destroy`.
  Residuals: shared dev-user password and Porkbun/Pulumi provider keys; no
  provider key was rotated. Legacy pln SPs removed and Pulumi stacks removed
  after state export.
- 2026-11-04 — excel correction: the first pass applied classic branch
  protection requiring a PR to `main`, which broke the scheduled
  `daily-summary` data commit (GH006). Twelve scheduled runs failed between
  13:05Z and 15:47Z; the last successful data commit was 02:47Z. Classic
  protection was removed at ~15:52Z; the repo now carries a ruleset blocking
  only force-push and deletion, which a normal fast-forward data commit can
  pass. A PR requirement needs the workflow changed first; the Actions
  integration is not an allowed bypass actor on a personal repository (422).
  PR #9's `SECURITY.md` and the workflow comment now state the constraint.
  The push path is verified: `github-actions[bot]` committed at 15:53:40Z,
  16:09:03Z, and 17:49:56Z. Pages deploys succeeded at 17:08Z, 17:19Z, and
  17:57Z; the live site's `last-modified` is 17:57Z. PR #9 merged at 17:44Z
  (`693488da`); its deploy was superseded by the newer data deploy through the
  workflow's `cancel-in-progress` concurrency. Push-to-main audit: excel is
  the only protected repo with a scheduled commit to `main`; ai-framework and
  paragon have no `git push` or `contents: write` workflow steps.
- 2026-11-05 — paragon token split delivered. `pln-preview` (RG `pln`, East
  US 2, Free) was created with its own deployment token
  (`AZURE_STATIC_WEB_APPS_API_TOKEN_PREVIEW`); the `PLN SWA Provisioner`
  identity has the same role on it; the preview and close jobs use the preview
  token while production keeps `AZURE_STATIC_WEB_APPS_API_TOKEN`. Fork guards
  landed in [PR #53](https://github.com/Stonegate-Software/paragon-learning-network/pull/53)
  (`a1467546`); the split landed in [PR #55](https://github.com/Stonegate-Software/paragon-learning-network/pull/55)
  (`134b82ce`). Verified: a preview deploy/provision/GET smoke/authenticated
  write smoke succeeded on `red-smoke-0392c4e0f-5601.eastus2.5.azurestaticapps.net`
  (write smoke passed on retry), a real PR preview created and closed env
  `56`, and the `#55` production deploy succeeded with the original token.
  The production token was rotated with `az staticwebapp secrets reset-api-key`
  and the new value written to `AZURE_STATIC_WEB_APPS_API_TOKEN`; the
  production deploy run 42075838119 succeeded with it, proving the rotation
  (the old value is invalid). Both the production SWA token and
  `SUPABASE_DB_URL_PROD` now live in the `production` environment (`SUPABASE_DB_URL_PROD`
  sourced from the live `pln-prod` session-pooler app setting); the repo-level
  copies were deleted and production dispatch run 42232583122 verified
  `migrate-prod` and the production deploy. Docs record: [PR #57](https://github.com/Stonegate-Software/paragon-learning-network/pull/57), merged `2500c257`.
- 2026-11-06 — phasetimer Phase 0 delivered. The static `AZURE_CREDENTIALS`
  secret is gone and the legacy `phasetimer-github` app/SP (which carried
  Contributor on the subscription and `phasetimer_group`) was decommissioned
  with both role assignments removed: a new `phasetimer-github-actions` app has a
  main-branch federated credential, the `Phasetimer SWA Provisioner` custom
  role on the SWA, and three repo vars; `azure-dns-config.yml` uses OIDC and
  `SECURITY.md` records the solo-owner exception. The SWA token was rotated
  and verified by a preview deploy; the manual OIDC check run 42237926568
  passed; the obsolete secret was deleted. The Playwright build jobs were
  pinned to `ubuntu-24.04` (Playwright 1.56 does not support 26.04), and stale
  preview environments were cleaned. The Dependabot preview path is fixed by
  [PR #54](https://github.com/hierovision/phasetimer/pull/54)
  (`skip_deploy_on_missing_secrets`). `PROD_SUPABASE_DB_URL` was moved to the
  `production` environment and verified by `migrate-prod`; the job required
  pinning `supabase/setup-cli` from `version: latest` (v3.0.0) to `2.118.0`
  because v3 failed on the stale `[inbucket]` config / `--db-url` path
  ([PR #55](https://github.com/hierovision/phasetimer/pull/55)). Local-env
  investigation (`~/repos/pt`, remote `hierovision/phasetimer`): `.env.local`
  and `.env.test.local` are gitignored but 0644 and contain
  `SUPABASE_SERVICE_ROLE_KEY` (dev) and `SUPABASE_SERVICE_ROLE_KEY_PROD` (prod,
  new-format `sb_secret_...`); they contain no `PROD_SUPABASE_DB_URL`/DB
  password, and the local `supabase/.temp` link is the dev project with no
  stored password. The local env was cleaned 2026-11-06: both files are 0600,
  `_PROD` is removed, the dev key is retained for local access, and the owner
  attests the keys never left the host — no rotation (dated acceptance).
- 2026-11-03 — Phase 0 containment applied where the platform allows. Applied
  and read back: ai-framework branch protection, secret scanning + push
  protection, Dependabot alerts + updates, CodeQL default setup, and the dated
  solo-owner exception (merged `1a88483`); paragon Dependabot + secret scanning
  + push protection and a clean `verify` PR for `migrate-prod` + exception;
  excel `main` protection, Dependabot alerts, CodeQL, and a clean PR dropping
  raw failure logs + adding the exception; marvin/phasetimer Dependabot alerts
  + updates; phasetimer `production` restricted to `main`. Plan-gated:
  paragon/phasetimer wait timers (422), marvin/phasetimer branch protection and
  secret scanning (403/422 on the private free plan), paragon CodeQL (403).
  Privacy-gated: moving secret values into environment secrets and the SWA
  token split require owner-run Azure work. Phase 1 remains unimplemented.
