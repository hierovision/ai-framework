---
slug: rm-075-phase-2-consumer-handoffs
title: Deliver five isolated Phase 2 consumer security remediation handoffs
status: draft
created: 2026-11-07
revised: [2026-11-07]
related: [fix-consumer-security-exposure, RM-075, RM-073, RM-076]
---

# Plan: rm-075-phase-2-consumer-handoffs

## Goal / Approach

**Goal:** Every exposure recorded for the five known consumers is fixed,
explicitly accepted with an owner-dated record, or decommissioned, and each
consumer has a cold-executable handoff plus an isolated verification record.

The framework coordinator authors five briefs and never edits a consumer repo.
A separate consumer implementer executes each brief in an isolated worktree,
opens one consumer PR, and stops for owner review. The owner performs every
secret write, global framework install, production deployment, service restart,
and merge. RM-075 closes only after all five dispositions and verification
records exist.

The fixed framework baseline is
`64251af5540d7c1d6ab2d833cc1a92cbbe001bf6` (`64251af`). It contains the
RM-073 propagation controls and the 2026-11-07 dependency/follow-up fixes.
Do not substitute floating `main`. A newer baseline requires a plan revision,
new version evidence, and a full verification rerun.

### Common design-time evidence

Read-only inspection established these starting points. A SHA is a content
baseline, not approval to update a primary checkout.

| Consumer | Design-time remote `main` | Local state verified read-only |
|---|---|---|
| `hierovision/excel-daily-monitor` | `24ff7d1317d54cd1ce028f9b3ee93dc916bcf66c` | Local `main` was `3d37f9e6c39c5e6e95e5a799fd2ccfec846cec77`; the 27 remote-only commits changed only `data/status.json`; primary had pre-existing untracked `.scratch/`. |
| `hierovision/marvin-slack` | `533baf8f1ed878325ece50bb3ec9747fb009111f` | Primary and `origin/main` matched; no tracked dirt. |
| `hierovision/phasetimer` (local `pt`) | `5b1925f5134612a823674c993651dfc3ca6a69a4` | Local `main` was `f9ab96defb389740b310d8893cc9d340c5d5d663`; three remote-only commits changed release/OIDC workflows and `SECURITY.md`; two existing stashes remain untouched. |
| `Stonegate-Software/paragon-learning-network` | `8d74f7b86be3d7af8ac0573a7a2f5505f8fed14f` | Primary was on `fix/legal-notice-copy` at `20da939b786be217bff6c5acb1aeeed32546760e`, with untracked `.opencode/plans/`; a final reread also showed modified `ROADMAP.md` while live sessions were present. Research used `origin/main`, which matched remote `main`; neither file was touched by this design. |
| `hierovision/pln` | No mutable implementation base; archived | `/home/hierovision/repos/pln` is absent. Live API readback showed `archived=true`, Actions `enabled=false`, zero Actions secrets, zero workflow runs, and zero open issues. |

The following framework facts were also read back live:

- The `eval` environment contains exactly `OPENCODE_API_KEY` and
  `DEEPSEEK_API_KEY`; repository-level Actions secrets are empty.
- `python3 scripts/check_repo_posture.py --repo hierovision/ai-framework`
  passed all 16 checks.
- Main run [42380383465](https://github.com/hierovision/ai-framework/actions/runs/42380383465)
  at `becf689e3c6461281fee321031e941b68f64fcda` passed every secret-bearing
  `evals` matrix job. PR run
  [42402998846](https://github.com/hierovision/ai-framework/actions/runs/42402998846)
  had `evals=skipped` and successful no-secret jobs. Main run
  [42403341546](https://github.com/hierovision/ai-framework/actions/runs/42403341546)
  at `64251af` was green with `evals` skipped because the docs-only matrix was
  empty; it is not evidence of a secret-bearing eval.
- The host install manifest currently names clean commit `becf689e...` at
  `/home/hierovision/repos/ai-framework`. The common owner upgrade below moves
  it to the fixed `64251af` runtime worktree. No agent reads secret values.

### Mandatory isolation and drift gate

Each active consumer brief starts with the following protocol. Substitute the
repo owner/name, local primary path, and design-time SHA from the table.
`git fetch` updates the object store and remote ref only; it never switches,
pulls, stashes, or writes the primary checkout's files.

```bash
export CONSUMER_REPO="<owner/name>"
export PRIMARY="$HOME/repos/<local-slug>"
export EXPECTED_BASE="<design-time-sha>"
export WT="$HOME/repos/worktrees/<local-slug>/rm-075-phase-2"
export BRANCH="chore/rm-075-phase-2"

git -C "$PRIMARY" status -sb
git -C "$PRIMARY" branch --show-current
git -C "$PRIMARY" worktree list
git -C "$PRIMARY" stash list
export BASE_SHA="$(gh api "repos/$CONSUMER_REPO/commits/main" --jq .sha)"
printf 'BASE_SHA=%s\n' "$BASE_SHA"

# Stop on drift in a security-relevant file. Excel alone may advance under
# data/** because its scheduled workflow commits deployment data to main.
if [ "$BASE_SHA" != "$EXPECTED_BASE" ]; then
  gh api "repos/$CONSUMER_REPO/compare/$EXPECTED_BASE...$BASE_SHA" \
    --jq '.files[].filename'
  echo "STOP: compare the changed paths with the brief; do not apply stale versions"
  exit 1
fi

git -C "$PRIMARY" fetch origin main
git -C "$PRIMARY" cat-file -e "$BASE_SHA^{commit}"
git -C "$PRIMARY" worktree add --detach "$WT" "$BASE_SHA"
git -C "$WT" switch -c "$BRANCH"
```

For Excel, replace the drift `exit 1` with an allowlist check that fails if any
changed path is outside `data/**`. For the other three active consumers, any
unexpected drift blocks execution pending a dated plan revision. Never infer
versions from a dirty primary worktree. Preserve every pre-existing branch,
stash, untracked file, worktree, and live process.

Before editing the isolated worktree, run the brief's audit-only command against
`BASE_SHA` and save the sanitized output as its before-audit. Compare advisory
IDs with the design-time workstream. A missing ID is evidence that the finding
is already fixed; a new ID blocks for an explicit fix/dated-acceptance decision.
Never run an auto-fixer. Repeat the same audit after remediation and record the
fixed, retained, and new ID sets so every finding has a disposition.

Each brief stores sanitized command output, before/after versions, PR URL, run
URLs, owner decisions, and unresolved items in
`.scratch/consumer-security-sweep/verification-<repo>.md` in the framework
repo. No secret values, `.env` contents, tokens, connection strings, artifacts
containing student data, or raw service logs enter that record.

### Common framework install/upgrade and verification

The owner performs this once, in a quiet window, because `install.sh` changes
global OpenCode symlinks. The stable runtime worktree must remain present while
its links are installed.

```bash
export FW_ROOT="$HOME/repos/ai-framework"
export FW_RUNTIME="$HOME/repos/worktrees/ai-framework/rm-075-runtime"
export FW_SHA="64251af5540d7c1d6ab2d833cc1a92cbbe001bf6"

# Preserve the previous non-secret manifest for rollback.
mkdir -p "$FW_ROOT/.scratch/consumer-security-sweep"
test -f "$HOME/.config/opencode/.ai-framework-install.json"
cp "$HOME/.config/opencode/.ai-framework-install.json" \
  "$FW_ROOT/.scratch/consumer-security-sweep/install-manifest-before-phase2.json"

if ! git -C "$FW_RUNTIME" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git -C "$FW_ROOT" worktree add --detach "$FW_RUNTIME" "$FW_SHA"
fi
test "$(git -C "$FW_RUNTIME" rev-parse HEAD)" = "$FW_SHA"
bash "$FW_RUNTIME/install.sh" --require-clean
bash "$FW_RUNTIME/install.sh" --check
python3 - <<'PY'
import json
p = json.load(open('/home/hierovision/.config/opencode/.ai-framework-install.json'))
assert p['repo_path'] == '/home/hierovision/repos/worktrees/ai-framework/rm-075-runtime', p
assert p['commit'] == '64251af5540d7c1d6ab2d833cc1a92cbbe001bf6', p
assert p['dirty'] is False, p
PY
```

The consumer implementer only runs `bash "$FW_RUNTIME/install.sh" --check`;
it never changes the global install. The coordinator runs and records these
framework controls once at `FW_RUNTIME`:

```bash
python3 scripts/test_eval_workflows.py
python3 scripts/test_log_redaction.py
python3 scripts/test_eval_env.py
python3 scripts/test_agent_permissions.py
python3 scripts/test_skill_deps.py
node skills/refining-issue-acceptance/evals/fixtures/untrusted-content.test.mjs
bash -n install.sh
bash scripts/test_install_sh.sh
python3 -m yamllint -c .yamllint.yaml .github/workflows/
python3 scripts/check_repo_posture.py --repo hierovision/ai-framework
python3 -m venv .scratch/rm-075-pip-venv
.scratch/rm-075-pip-venv/bin/pip install --require-hashes -r scripts/ci-requirements.txt
npm ci --prefix skills/capturing-ui-evidence
npm --prefix skills/capturing-ui-evidence audit --omit=dev
npm ci --prefix skills/auditing-accessibility
npm --prefix skills/auditing-accessibility audit --omit=dev
npm ci --prefix skills/validating-ui
npm --prefix skills/validating-ui audit --omit=dev
```

Pass criteria: every command exits 0; `install.sh --check` reports the fixed
SHA and clean manifest; the redaction suite's synthetic raw values do not
appear in output; the child-env test retains only its documented allowlist;
the permissions test finds no auth/session-store read root; and no dependency
install resolves through a consumer checkout. The exact dependency pins at
this baseline are Playwright `1.64.1`, axe-core `4.14.0`, PyYAML `6.0.3`,
yamllint `1.38.0`, and pathspec `1.1.1`. OpenCode remains on the supported
`@opencode/cli 2.2.5` path; this plan does not upgrade OpenCode.

The main-only eval control belongs to the framework. No consumer has a
secret-bearing behavioral-eval workflow to clone. A consumer with no eval
workflow records `not present` after running the following in its isolated
worktree; it must not add one. Existing application preview/deploy jobs are
verified separately and must not be mislabeled as evals.

```bash
if [ -d .github/workflows ]; then
  ! find .github/workflows -maxdepth 1 -type f -iname '*eval*' -print | grep .
fi
```

For each new `.github/dependabot.yml`, use this exact base and omit the
GitHub Actions entry only where the workstream says there are no workflows:

```yaml
version: 2
updates:
  - package-ecosystem: npm
    directory: "/"
    schedule:
      interval: weekly
    open-pull-requests-limit: 5
  - package-ecosystem: github-actions
    directory: "/"
    schedule:
      interval: weekly
    open-pull-requests-limit: 5
```

Marvin has no workflows and receives only the npm entry. PhaseTimer and
Paragon receive both entries. PhaseTimer also adds this scoped rule; it is a
runtime-compatibility pin, not a security suppression:

```yaml
    ignore:
      - dependency-name: "@types/node"
        update-types: ["version-update:semver-major"]
```

Indent that `ignore` block under the npm update entry. Excel retains its
existing monthly npm/GitHub Actions config. No config adds a gitignored or
host-local `.opencode` surface.

Framework rollback: create an isolated worktree at the previous clean manifest
commit, run the current runtime's `install.sh --uninstall`, run the previous
worktree's `install.sh --require-clean` and `--check`, then remove the unused
runtime worktree only when it is clean. Do not delete either worktree while
its symlinks are live. Never roll back the main-only eval, redaction,
allowlist, auth-root, or dependency-pin controls to make a consumer pass.

### Workstream A — `excel-daily-monitor`

**Disposition:** fix the stale Playwright declaration and remove the remaining
public failure-artifact exposure; retain the existing dated scheduled-commit
branch exception. Current live `main` may advance only under `data/**`.

**Before:** `package.json` declares `playwright ^1.49.0`; the lock resolves
`1.63.0`. `daily.yml` excludes console/network logs but still uploads
`failure.json`, screenshots, and HTML from a public repo. Screenshots and page
content can contain student data, and `failure.json` can contain URLs with
non-token identifiers. Redaction tests do not make those formats safe.

**After:** `playwright` and `playwright-core` are exactly `1.64.1`; the public
failure upload step is absent. Evidence remains only on the ephemeral runner.
Dependabot, secret scanning/push protection, CodeQL, and the force/delete
ruleset remain enabled. No PR requirement is added to the scheduled data path.

Consumer-owned files:

- `package.json` and `package-lock.json` — exact Playwright `1.64.1` pin.
- `.github/workflows/daily.yml` — remove the entire `Upload failure evidence`
  step; do not replace it with a broader artifact glob.
- `.github/dependabot.yml`, `SECURITY.md`, and the already SHA-pinned workflows
  remain unchanged unless live drift requires a revised brief.

Commands in the isolated consumer worktree:

```bash
npm install --save-exact --package-lock-only --ignore-scripts playwright@1.64.1
npm ci --ignore-scripts
npx playwright install chromium
npm test
mkdir -p .scratch
npm audit --package-lock-only --json > .scratch/rm-075-npm-audit.json
node - <<'JS'
const lock = require('./package-lock.json').packages;
const audit = require('./.scratch/rm-075-npm-audit.json');
if (lock[''].dependencies.playwright !== '1.64.1') process.exit(1);
if (lock['node_modules/playwright'].version !== '1.64.1') process.exit(1);
if (lock['node_modules/playwright-core'].version !== '1.64.1') process.exit(1);
if (audit.metadata.vulnerabilities.total !== 0) process.exit(1);
JS
! grep -q 'Upload failure evidence\|actions/upload-artifact' .github/workflows/daily.yml
! git grep -n -E 'uses:[[:space:]]*[^#]+@v[0-9]' -- .github/workflows/
git diff --check
```

Pass criteria: all tests pass, the three Playwright assertions hold, audit
metadata totals zero, no failure artifact is uploaded, no action is tag-pinned,
and the diff touches only the two manifests and `daily.yml`. `npm audit` was
also zero in a scratch-only `1.64.1` lockfile trial; the implementer still runs
the real repo tests.

Owner posture verification (names/settings only):

```bash
gh api repos/hierovision/excel-daily-monitor/vulnerability-alerts -i  # HTTP 204
gh api repos/hierovision/excel-daily-monitor/automated-security-fixes --jq .enabled  # true
gh api repos/hierovision/excel-daily-monitor --jq '.security_and_analysis.secret_scanning.status'  # enabled
gh api repos/hierovision/excel-daily-monitor --jq '.security_and_analysis.secret_scanning_push_protection.status'  # enabled
gh api repos/hierovision/excel-daily-monitor/code-scanning/default-setup --jq .state  # configured
gh api repos/hierovision/excel-daily-monitor/rulesets/26544515 \
  --jq '[.rules[].type] | sort'  # ["deletion","non_fast_forward"]
```

Rollback: close the unmerged PR to make no runtime change. After merge, revert
the squash commit through a new PR; do not rewrite the scheduled `main`
history. Restoring public artifacts is not an approved rollback for a failed
scrape; diagnose from the runner and keep the artifact removal.

### Workstream B — `marvin-slack`

**Disposition:** fix three transitive dependency exposures, add least-privilege
systemd controls, retain the installed local secret scanner, and record the
private-free/secret posture and any unrotated-token decision.

**Before → after:**

- `body-parser 2.3.0 → 2.4.0` (advisory `1243074` / GHSA-27r3-jxmh-p828).
- `undici 7.29.1 → 7.30.1` (advisories `1243078`, `1243081`, `1243113`,
  `1243473`, `1243475`, `1243478`, `1243481`, and `1243484`).
- `qs 6.16.0 → 6.16.1` (advisory `1243687` / GHSA-6pq8-jhm2-2vcw; new since
  the sweep).
- `@slack/bolt` stays `5.1.0`; Node stays `>=20` and the service's Node `24.8.0`
  satisfies the fixed `undici` engine floor.

A scratch-only override/lockfile trial produced zero audit findings. It did not
restart the live service.

Consumer-owned files:

- `package.json` and `package-lock.json` — explicit overrides above plus
  `test:security = "npm run test:secrets && npm audit --package-lock-only --audit-level=high"`.
- `.githooks/pre-push` — new; fail-closed local dependency/secret gate that
  changes to the worktree root and runs `npm run test:security`.
- `scripts/install-hooks.sh` — include `pre-push` in the existence and
  executable checks; retain the existing synthetic secret-scanner smoke test.
- `deploy/marvin.service` — retain `NoNewPrivileges=true` and add the directives
  below.
- `.github/dependabot.yml` — new; npm at `/`, weekly.
- `SECURITY.md` — new; private-free branch/secret-scanning limitation, local
  hook compensating control, and the actual owner decision/date for unrotated
  Slack tokens. The implementer must not invent an exposure attestation.

The new `.githooks/pre-push` content is:

```bash
#!/usr/bin/env bash
set -euo pipefail
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
if ! command -v node >/dev/null 2>&1; then
  echo "pre-push: Node >=20 is required; refusing an unaudited push" >&2
  exit 1
fi
npm run test:security
```

Add exactly these systemd directives under `[Service]`:

```ini
ProtectSystem=full
PrivateTmp=true
PrivateDevices=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true
RestrictRealtime=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
CapabilityBoundingSet=
AmbientCapabilities=
UMask=0077
```

Commands in the isolated consumer worktree:

```bash
npm pkg set 'overrides.body-parser=2.4.0' 'overrides.undici=7.30.1' 'overrides.qs=6.16.1' \
  'scripts.test:security=npm run test:secrets && npm audit --package-lock-only --audit-level=high'
npm install --package-lock-only --ignore-scripts
npm ci --ignore-scripts
chmod +x .githooks/pre-push
npm test
bash .githooks/pre-push
node - <<'JS'
const p = require('./package-lock.json').packages;
for (const [name, version] of Object.entries({
  'node_modules/body-parser': '2.4.0',
  'node_modules/undici': '7.30.1',
  'node_modules/qs': '6.16.1',
})) {
  if (p[name]?.version !== version) throw new Error(`${name}: ${p[name]?.version}`);
}
JS
systemd-analyze --user verify deploy/marvin.service
test "$(git config --get core.hooksPath)" = .githooks
test -x .githooks/pre-commit
test -x .githooks/pre-push
git diff --check
```

Pass criteria: 217 existing tests plus the secret-scanner tests (or a higher
current count with zero failures) pass; the pre-push hook's audit exits 0; all
three exact lock versions hold; systemd verification exits 0; both hooks remain
installed and executable; `.env` is mode `0600` and ignored. No command prints
`.env` or journal contents.

The owner verifies only the local file metadata, without reading its contents:

```bash
test "$(stat -c '%a' /home/hierovision/repos/marvin-slack/.env)" = 600
git -C /home/hierovision/repos/marvin-slack check-ignore .env
```

The owner supplies one of these decisions before merge: a dated statement that
the Slack token file never left the host and rotation is not required, reviewed
by 2027-01-25; or owner-only revocation/rotation through Slack followed by a
write-only `.env` update. Absence of that decision blocks merge. Secret scanning
and branch rulesets remain platform-gated on the private free plan; Dependabot
alerts/security updates and the local hook are the compensating controls.

Owner-only deployment after merge (the consumer agent does not run it). This
uses a detached runtime worktree, not the primary checkout. The unit's existing
`EnvironmentFile=/home/hierovision/repos/marvin-slack/.env` remains unchanged;
the owner does not copy or expose that file.

```bash
export MARVIN_RUNTIME="$HOME/repos/worktrees/marvin-slack/rm-075-runtime"
export MARVIN_PR_URL="<merged-consumer-pr-url>"
export MARVIN_SHA="$(gh pr view "$MARVIN_PR_URL" --json mergeCommit --jq .mergeCommit.oid)"
test -n "$MARVIN_SHA" && test "$MARVIN_SHA" != null
systemctl --user cat marvin > "$HOME/.config/systemd/user/marvin.service.before-rm-075"
git -C /home/hierovision/repos/marvin-slack fetch origin main
if ! git -C "$MARVIN_RUNTIME" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git -C /home/hierovision/repos/marvin-slack worktree add --detach \
    "$MARVIN_RUNTIME" "$MARVIN_SHA"
fi
test "$(git -C "$MARVIN_RUNTIME" rev-parse HEAD)" = "$MARVIN_SHA"
git -C "$MARVIN_RUNTIME" status --porcelain  # must be empty before dependency install
npm --prefix "$MARVIN_RUNTIME" ci --ignore-scripts
install -m 0644 "$MARVIN_RUNTIME/deploy/marvin.service" \
  /home/hierovision/.config/systemd/user/marvin.service
mkdir -p /home/hierovision/.config/systemd/user/marvin.service.d
cat > /home/hierovision/.config/systemd/user/marvin.service.d/rm-075-runtime.conf <<'EOF'
[Service]
WorkingDirectory=/home/hierovision/repos/worktrees/marvin-slack/rm-075-runtime
ExecStart=
ExecStart=/home/hierovision/.nvm/versions/node/v24.8.0/bin/node /home/hierovision/repos/worktrees/marvin-slack/rm-075-runtime/src/server.js
EOF
systemctl --user daemon-reload
systemctl --user restart marvin
test "$(systemctl --user is-active marvin)" = active
systemctl --user show marvin \
  -p NoNewPrivileges -p ProtectSystem -p PrivateTmp -p PrivateDevices \
  -p ProtectKernelTunables -p ProtectKernelModules -p ProtectControlGroups \
  -p RestrictSUIDSGID -p LockPersonality -p RestrictRealtime -p UMask
```

Rollback disables `rm-075-runtime.conf`, restores the saved unit,
daemon-reloads and restarts the previous primary-based service, then reverts
the code through a new PR. The primary checkout is never fast-forwarded or
used as an agent work location. Remove the runtime worktree only when it is
clean and no unit points at it. Do not disable the secret hook or print tokens
to test the service.

### Workstream C — `pt` / `phasetimer`

**Disposition:** upgrade the toolchain with a fresh lock resolution, SHA-pin
all actions, verify before production migration, add Dependabot, split the
preview/production Static Web Apps tokens, and date-accept only four named
development residuals after owner approval.

The design-time dependency trial used Node `22.23.3`, already installed on the
host. The trial did not run the application suite. Do not use an engine-ignore
flag: fresh resolution includes `nopt 10.0.1`, whose engine excludes Node
`24.8.0` but accepts Node `22.23.3`.

**Direct before → after:**

| Package/control | Before | After |
|---|---|---|
| Node | manifest `>=18`; CI `24` | manifest `>=22.22.2 <23`; CI `22.23.3` |
| `vue` | `3.5.22` | `3.5.45` |
| `uuid` | `13.0.0` | `13.0.1` |
| `vite` | direct `5.4.21`; transitive `7.1.12` | direct `6.4.5`; fresh compatible transitive resolution |
| `vitest` | `4.0.6` | `4.1.12` |
| `@vitest/browser-playwright` | `4.0.6` | `4.1.12` |
| `@vitest/ui` | `4.0.6` | `4.1.12` |
| `vitest-browser-vue` | `2.0.1` | `3.1.0` |
| `@vue/test-utils` | `2.4.6` | `2.5.1` |
| `@vue/compiler-dom` | `3.5.22` transitive | `3.5.45` explicit dev peer |
| `happy-dom` | `20.0.10` | `21.0.4` |
| `@lhci/cli` | `0.15.1` | `0.16.0` |
| `puppeteer` | `24.28.0` | `25.16.0` |
| `playwright`, `@playwright/test` | `1.56.1` | `1.64.1` |
| `vite-plugin-pwa` | `0.20.5` | `1.3.0` (supports Vite 6) |
| `workbox-build`, `workbox-window` | `7.3.0` transitive | `7.4.1` explicit dev peers |
| `source-map-js` | `1.2.1` | `1.2.2` resolution |
| `postcss` | `8.5.6` | `8.5.32` resolution |
| `nanoid` | `3.3.11` | `3.3.20` resolution |
| `ws` | `8.18.3` | `8.22.1` through fresh lock resolution |

Remove `@types/uuid`; `uuid 13` supplies its own types. Keep
`@vitejs/plugin-vue` on its existing compatible range (the trial resolved
`5.2.4`). Do not force `basic-ftp 6`: `get-uri` requests `^5.0.2`, so that
override is incompatible.

Consumer-owned files:

- `package.json` and `yarn.lock` — versions above, regenerated from the exact
  manifest without install scripts.
- `.github/workflows/release.yml` — pins, Node, verify-before-migrate, preview
  token, artifact handoff, and production dependency audit.
- `.github/workflows/azure-dns-config.yml` and `azure-oidc-check.yml` — pin
  `azure/login` and any other action to the SHAs below.
- `.github/dependabot.yml` — new; npm at `/` and GitHub Actions, weekly;
  ignore only future `@types/node` major updates while runtime is Node 22.
- `SECURITY.md` — actual owner decision date and review date for the four
  residuals, the existing private-free exception, and the retained local dev
  key decision. Do not mark the production SWA token environment-scoped until
  the owner verification below proves it.

Manifest commands in the isolated worktree:

```bash
export PATH="$HOME/.nvm/versions/node/v22.23.3/bin:$PATH"
test "$(node --version)" = v22.23.3
npm pkg set \
  'dependencies.vue=3.5.45' \
  'dependencies.uuid=13.0.1' \
  'devDependencies.@lhci/cli=0.16.0' \
  'devDependencies.@playwright/test=1.64.1' \
  'devDependencies.@vitest/browser-playwright=4.1.12' \
  'devDependencies.@vitest/ui=4.1.12' \
  'devDependencies.@vue/compiler-dom=3.5.45' \
  'devDependencies.@vue/test-utils=2.5.1' \
  'devDependencies.happy-dom=21.0.4' \
  'devDependencies.playwright=1.64.1' \
  'devDependencies.puppeteer=25.16.0' \
  'devDependencies.vite=6.4.5' \
  'devDependencies.vite-plugin-pwa=1.3.0' \
  'devDependencies.vitest=4.1.12' \
  'devDependencies.vitest-browser-vue=3.1.0' \
  'devDependencies.workbox-build=7.4.1' \
  'devDependencies.workbox-window=7.4.1' \
  'engines.node=>=22.22.2 <23' \
  'resolutions.source-map-js=1.2.2' \
  'resolutions.postcss=8.5.32' \
  'resolutions.nanoid=3.3.20'
npm pkg delete 'devDependencies.@types/uuid'
rm yarn.lock
yarn install --ignore-scripts
```

Use this exact action pin map in every workflow; retain
`supabase/setup-cli`'s already fixed `version: 2.118.0`:

- `actions/checkout` → `3d3c42e5aac5ba805825da76410c181273ba90b1` (`v7.0.1`).
- `actions/setup-node` → `949feb2413d6458794dcd2491c4babbbce0c15c1` (`v7.1.0`).
- `Azure/static-web-apps-deploy` →
  `4d27395796ac319302594769cfe812bd207490b1` (`v1`).
- `supabase/setup-cli` →
  `45a513f8c64c0bc8e0e3dfe572b5c95be85f6359` (`v3.0.1`).
- `azure/login` → `7184910d9eb2b1c5e48f7073824a90609bb9b6d6` (`v2`).
- `actions/upload-artifact` →
  `cf430e030ddbb5b0abf93d22962f4752f3646cd9` (`v7.0.2`).
- `actions/download-artifact` →
  `9000827ccba6bdab643e8b6fd33ac0654aef8333` (`v8.0.2`).

In `release.yml`, split the current production build into `verify-prod` and
`build_deploy_prod`:

1. `verify-prod` runs on the same push/prod-dispatch conditions as the old
   production build. It checks out, uses Node `22.23.3`, installs frozen
   dependencies, installs Chromium, runs unit tests, contrast, build, and
   `yarn audit --groups dependencies --level high`, then uploads `dist` as
   `phasetimer-dist-${{ github.sha }}` with one-day retention.
2. `migrate-prod` declares `needs: verify-prod` and keeps its existing
   `production` environment and branch policy.
3. `build_deploy_prod` declares `needs: migrate-prod`, downloads that exact
   artifact to `dist`, and deploys with `skip_app_build: true`. It no longer
   installs, tests, or rebuilds after migration.
4. Preview retains its independent test/build path but uses
   `AZURE_STATIC_WEB_APPS_API_TOKEN_PREVIEW` for both upload and close.
   Production continues using `AZURE_STATIC_WEB_APPS_API_TOKEN`, resolved from
   the `production` environment after the owner action.
5. No migration rollback is attempted by this workflow. A revert deploys
   application code through the normal verify → migrate → deploy sequence;
   schema repair is forward-only.

The owner performs the token split, with no secret value printed or stored in a
brief:

```bash
# Existing production metadata verified read-only: resource group
# phasetimer_group, location East US 2, SKU Free.
if ! az staticwebapp show -n phasetimer-preview -g phasetimer_group --output none 2>/dev/null; then
  az staticwebapp create -n phasetimer-preview -g phasetimer_group \
    --location "East US 2" --sku Free --output none
fi
az staticwebapp secrets list -n phasetimer-preview -g phasetimer_group \
  --query properties.apiKey --output tsv |
  gh secret set AZURE_STATIC_WEB_APPS_API_TOKEN_PREVIEW \
    --repo hierovision/phasetimer
az staticwebapp secrets list -n phasetimer -g phasetimer_group \
  --query properties.apiKey --output tsv |
  gh secret set AZURE_STATIC_WEB_APPS_API_TOKEN \
    --repo hierovision/phasetimer --env production
```

Open the workflow PR before deleting the repository-wide production token.
After the PR preview succeeds and the merged production deploy succeeds, the
owner deletes only the repository-scoped copy:

```bash
gh secret delete AZURE_STATIC_WEB_APPS_API_TOKEN --repo hierovision/phasetimer
! gh api repos/hierovision/phasetimer/actions/secrets \
  --jq '.secrets[].name | select(. == "AZURE_STATIC_WEB_APPS_API_TOKEN")' | grep .
gh api repos/hierovision/phasetimer/environments/production/secrets \
  --jq '[.secrets[].name] | sort'
# Expected names: AZURE_STATIC_WEB_APPS_API_TOKEN and PROD_SUPABASE_DB_URL.
```

If verification fails before deletion, revert the workflow PR and retain the
existing repository token while restoring service. After deletion, rollback
requires the owner to write the current production token back to that
repository secret from Azure, revert through a PR, and rerun verification; do
not rotate the token merely to execute rollback.

Verification in the isolated worktree:

```bash
export PATH="$HOME/.nvm/versions/node/v22.23.3/bin:$PATH"
yarn install --frozen-lockfile --ignore-scripts
yarn playwright install chromium
yarn type-check
yarn test --run
yarn check-contrast
yarn build
yarn eslint .
"$FW_RUNTIME/.scratch/rm-075-pip-venv/bin/python" -m yamllint \
  -c "$FW_RUNTIME/.yamllint.yaml" .github/workflows/
! grep -R -n -E 'uses:[[:space:]]*[^#]+@v[0-9]|version:[[:space:]]*latest' .github/workflows/
mkdir -p .scratch
set +e
yarn audit --groups dependencies --json > .scratch/rm-075-audit-prod.jsonl
prod_rc=$?
yarn audit --json > .scratch/rm-075-audit-all.jsonl
all_rc=$?
set -e
test "$prod_rc" -eq 0
test "$all_rc" -ne 0
python3 - <<'PY'
import json
expected = {1240853, 1243505, 1244013, 1244623}
for path, production in [('.scratch/rm-075-audit-prod.jsonl', True),
                         ('.scratch/rm-075-audit-all.jsonl', False)]:
    ids = set()
    summary = None
    for line in open(path, encoding='utf-8'):
        row = json.loads(line)
        if row.get('type') == 'auditAdvisory':
            ids.add(row['data']['advisory']['id'])
        elif row.get('type') == 'auditSummary':
            summary = row['data']['vulnerabilities']
    if production:
        assert ids == set(), ids
        assert summary and all(summary[k] == 0 for k in
                               ('critical', 'high', 'moderate', 'low', 'info')), summary
    else:
        assert ids == expected, (ids, expected)
PY
git diff --check
```

The four accepted IDs and their exact post-trial versions/paths are:

- `1240853` / GHSA-c475-qrg2-pj4r — `basic-ftp 5.3.1`, high,
  `@lhci/cli>proxy-agent>pac-proxy-agent>get-uri>basic-ftp`; development-only
  Lighthouse/proxy path. A `6.2.1` override is rejected because it violates
  `get-uri`'s `^5.0.2` range.
- `1243505` / GHSA-gcqx-w48m-w2h4 — `deepmerge 4.3.1`, low, Workbox/Rollup
  plugin path; no patched release is reported.
- `1244013` / GHSA-3g3m-2fjr-6pw4 — vulnerable `glob 11.1.0` paths in
  Workbox/js-beautify, moderate; other resolved glob versions do not make that
  path safe. A major override is not justified without a separate migration.
- `1244623` / GHSA-g3hv-75wg-m249 — vulnerable `minimatch 10.2.6` paths in
  lint/test/language tooling, moderate; other resolved minimatch versions do
  not make those paths safe.

`SECURITY.md` must name each ID, version/path, development-only rationale,
actual owner decision date, and review date `2027-01-25` (or an earlier owner
chosen date). The exact-ID assertion must fail if an advisory disappears, so
the stale acceptance is removed, or if any new ID appears. Production
dependencies must remain at zero advisories. This is a dated disposition, not
an audit-level suppression.

The scratch trial ended with production counts all zero and a full-tree summary
of 1 high path, 10 moderate paths, and 2 low paths across exactly those four
unique advisories. It did not run `yarn build`, tests, or deployment. Those are
implementation gates, not evidence already held.

The owner additionally runs `yarn e2e` after writing any required test
environment files directly into the isolated worktree; agents never read or
copy `.env*` from the primary checkout. Verify the PR preview and post-merge
production run before closing the workstream. Verify the production
`https://www.phasetimer.com` response and preserve the existing Phase 0 dated
acceptance for the never-exposed local dev key. Do not rotate that key or the
Porkbun/Pulumi keys without the owner's dated exposure decision.

Rollback before merge closes the PR and leaves production untouched; the owner
may delete the unused preview app only through a separate explicit decision.
After merge, revert the squash commit through a new PR and run the normal
pipeline. Do not roll back database migrations or force-push `main`.

### Workstream D — `paragon-learning-network`

**Disposition:** complete the Next target, clear the current high-severity
dependency set, preserve the Phase 0 fork/token/environment controls, add
Dependabot and a production audit gate, and date-accept one development-only
`minimatch` residual after owner approval.

**Before → after:**

- `next 16.4.1 → 16.4.3` (the parent disposition's fixed target).
- `applicationinsights 2.9.8 → 3.17.0`; the lock trial resolves vulnerable
  `@opentelemetry/core 1.30.1` to fixed `2.10.0`/`2.12.0` paths.
- `vitest 5.0.2 → 5.1.0` in client/domain/shared;
  `@vitest/mocker 5.0.2 → 5.1.0`.
- `typescript-eslint 8.70.1 range → exact 8.72.1` at the root.
- `source-map-js 1.2.1 → 1.2.2` workspace override.
- `vite 8.3.1 → 8.3.6` workspace override.
- `zod 4.6.5 → 4.6.6` workspace override.
- `minimatch 10.2.6` remains in TypeScript-ESLint development paths and is the
  sole residual in the lock trial (GHSA-g3hv-75wg-m249, moderate). No major
  override is allowed without a separate compatibility design.

The scratch-only lock trial produced zero production advisories and exactly one
moderate development advisory. It did not typecheck the Application Insights
major upgrade or exercise telemetry.

Consumer-owned files:

- `apps/client/package.json` — Next, Application Insights, Vitest.
- `packages/domain/package.json` and `packages/shared/package.json` — Vitest.
- `package.json` — exact TypeScript-ESLint.
- `pnpm-workspace.yaml` — add the three overrides below, preserving its
  `minimumReleaseAge` and `allowBuilds` policy unchanged.
- `pnpm-lock.yaml` — regenerate with `pnpm 12.6.0` and Node `24.8.0`.
- `.github/workflows/ci.yml` — add `pnpm audit --prod --audit-level=high`
  after frozen install in the product path.
- `.github/dependabot.yml` — new; npm workspace at `/` and GitHub Actions,
  weekly.
- `SECURITY.md` — actual owner decision date/review for the single residual
  and the live Code Security/CodeQL plan limitation.
- `apps/client/src/lib/telemetry/server.ts` and
  `apps/client/src/instrumentation.ts` — only if the documented v3 SDK requires
  a source migration. Their current setup/start/defaultClient call path was
  reviewed. Any broader telemetry rewrite stops for a revised plan.

Use pnpm `12.6.0`; pnpm 12 reads overrides from `pnpm-workspace.yaml`, not the
legacy root `package.json` `pnpm` field.

```bash
corepack pnpm --version  # 12.6.0
node --version           # v24.8.0
pnpm --filter @pln/client pkg set \
  dependencies.next=16.4.3 \
  dependencies.applicationinsights=3.17.0 \
  devDependencies.vitest=5.1.0
pnpm --filter @pln/domain pkg set devDependencies.vitest=5.1.0
pnpm --filter @pln/shared pkg set devDependencies.vitest=5.1.0
pnpm --filter paragon-learning-network pkg set \
  devDependencies.typescript-eslint=8.72.1
cat >> pnpm-workspace.yaml <<'EOF'
overrides:
  source-map-js: 1.2.2
  vite: 8.3.6
  zod: 4.6.6
EOF
pnpm install --lockfile-only --ignore-scripts
pnpm install --frozen-lockfile
mkdir -p .scratch
```

The append is valid only because the design-time workspace file has no
`overrides:` key. The drift gate must stop if one already exists; the
implementer merges the three entries instead of duplicating the key.

Verification:

```bash
pnpm audit --prod --audit-level=high
set +e
pnpm audit --json > .scratch/rm-075-pnpm-audit.json
audit_rc=$?
set -e
test "$audit_rc" -ne 0
python3 - <<'PY'
import json
x = json.load(open('.scratch/rm-075-pnpm-audit.json'))
a = x.get('advisories', {})
assert set(a) == {'1244623'}, set(a)
v = x['metadata']['vulnerabilities']
assert v['critical'] == 0 and v['high'] == 0, v
assert a['1244623']['module_name'] == 'minimatch'
assert a['1244623']['findings'][0]['version'] == '10.2.6'
PY
supabase start
supabase db reset
supabase test db
pnpm db:types
git diff --exit-code -- packages/shared/src/
pnpm typecheck
pnpm --filter @pln/client build
node scripts/deploy/verify-artifact-deps.mjs apps/client/.next/standalone/apps/client
pnpm lint
pnpm test
pnpm test:integration
pnpm --filter @pln/client exec playwright install chromium
pnpm e2e
node scripts/check-no-service-role-in-client.mjs
node scripts/check-workflows.mjs
! git grep -n -E 'uses:[[:space:]]*[^#]+@v[0-9]' -- .github/workflows/
git diff --check
```

Use the CI file's dummy local Supabase build values, never production values.
The full build/test/integration/e2e sequence and preview write smoke are the
compatibility gate for Application Insights `3.17.0`. If the SDK requires a
migration outside the two named files, stop; do not revert silently to the
vulnerable release or accept the runtime OpenTelemetry advisory.

`SECURITY.md` must identify GHSA-g3hv-75wg-m249, `minimatch 10.2.6`, its
TypeScript-ESLint-only paths, the actual owner decision date, and review date
`2027-01-25` (or earlier). The full-audit assertion fails on every additional
ID or on a high/critical result. Code Security/CodeQL is disabled by the live
plan; record that limitation rather than claiming CodeQL is enabled.

Owner posture verification must show Dependabot alerts/security updates
enabled, secret scanning/push protection enabled, `verify` required by the
active `main` ruleset, zero required approvals under the existing dated
exception, the production environment restricted to `main`, preview token only
at repository scope, and production token plus production DB URL only in the
`production` environment. List names, never values. After merge, verify the
normal production workflow and `scripts/deploy/smoke.mjs` against
`https://www.paragon-ln.com`; verify the PR preview and authenticated preview
write smoke before closing.

Rollback uses a revert PR through normal CI/deploy. Do not use manual
`workflow_dispatch target=production` as a dependency rollback because the
current workflow applies production migrations on every production dispatch.
Schema changes are not in this workstream; any database repair is forward-only.

### Workstream E — `pln` (retired/archived)

**Disposition:** decommission-only, verified remotely. Do not clone, unarchive,
patch dependencies, create a worktree, or run an install. The absent local
checkout is recorded as a fact, not reconstructed from memory.

The brief's exact verification commands are:

```bash
gh api repos/hierovision/pln --jq .archived
# expected: true
gh api repos/hierovision/pln/actions/permissions --jq .enabled
# expected: false
gh api repos/hierovision/pln/actions/secrets --jq .total_count
# expected: 0
gh api 'repos/hierovision/pln/actions/runs?per_page=1' --jq .total_count
# expected: 0
gh api 'repos/hierovision/pln/issues?state=open&per_page=100' --jq length
# expected: 0
az staticwebapp show -n pln-prod -g pln \
  --query '{name:name,host:defaultHostname}' --output json
# expected: the retained shared production app, not a deletion
curl -fsS https://www.paragon-ln.com/.swa/health.html
# expected: ok; this is only a production liveness check, not a Supabase proof
```

The 195 historical dependency advisories are dispositioned by decommissioning,
not by upgrading an archived repo. No rollback re-enables Actions, restores
duplicate secrets, or unarchives the repo. Any mismatch is an incident-handoff
stop, not an instruction to improvise containment.

The owner must record the disposition of the remaining shared dev password and
Porkbun/Pulumi provider keys. Recommended default: retain them only under an
actual owner-dated never-exposed acceptance with review by 2027-01-25; if the
owner cannot attest non-exposure, use `handling-security-incidents` and perform
owner-only coordinated rotation. Do not rotate a never-exposed key merely
because it appears in the old register, and never update Paragon or PhaseTimer
secret values from this framework pass. Preserve `pln-prod`, `pln-insights`,
and the shared Supabase projects. This brief cannot prove Supabase project
health without the owner supplying the project references through an approved
read-only check; Paragon's real CI/preview/production verification is the
application-level evidence.

### Handoff completeness and coordination sequence

1. Owner approves this plan, including each dated-acceptance default that will
   be used. Approval establishes a decision only when the implementing brief
   records its actual approval date and rationale.
2. The coordinator writes the five briefs from these workstreams and runs the
   scoped completeness verifier in Verification.
3. The owner installs the fixed framework runtime; the coordinator records the
   common control results and eval run evidence.
4. Five independent consumer implementers run in their isolated worktrees.
   The framework coordinator never applies their diffs.
5. Each consumer PR passes its own gates and owner actions. A failed runtime
   gate blocks that workstream; it cannot be converted into a suppression
   without a new dated owner decision and plan revision.
6. The coordinator collects four consumer PR/verification records plus the
   remote `pln` record, checks that primary checkouts are unchanged, and only
   then updates RM-075 closure docs. Do not close on opened-but-unmerged PRs.

## Acceptance Criteria

1. **Five complete briefs exist.** The five files named in Files to Modify
   contain their repo, design-time base, fixed framework SHA, before/after
   versions, exact commands, pass criteria, rollback, owner-only steps, and
   the AC11 clause. — Verifier: the scoped Python completeness check in
   Verification exits 0 and prints exactly five `PASS` lines.

2. **The fixed framework runtime and all propagation controls verify.** The
   install manifest names `64251af` and `dirty=false`, and every common
   framework command exits 0. — Verifier: `install.sh --check`, the manifest
   assertion, and the common command log in the framework verification record.
   The record also links the green secret-bearing main run and a PR run with
   `evals=skipped`.

3. **Excel closes its dependency and public-artifact findings without breaking
   scheduled publication.** Playwright resolves to exact `1.64.1`, audit totals
   zero, `daily.yml` has no failure upload action, `npm test` passes, and the
   next scheduled data commit plus Pages deploy succeeds. — Verifier: the
   Excel command block, the resulting workflow run URLs, and unchanged
   force/delete ruleset/security settings.

4. **Marvin has zero audited dependency findings and a running hardened
   service.** The three lock versions match, unit tests pass, the pre-push hook
   completes its secret tests and audit, systemd verification passes, both
   hooks and the `.env` metadata checks pass, and the owner-deployed service is
   active with every listed directive. — Verifier: the Marvin command block and
   `systemctl --user show` output. `SECURITY.md` contains the actual owner token
   decision/date or the owner rotation record.

5. **PhaseTimer verifies before production migration and has no production
   dependency advisory.** Its exact manifest/lock targets hold, every action
   reference is a full SHA, no CLI uses `latest`, `verify-prod` precedes
   `migrate-prod`, production audit exits 0, and the full audit contains exactly
   the four owner-dated residual IDs. — Verifier: the PhaseTimer command block,
   YAML diff/job graph, and audit parser. `yarn build`, typecheck, unit,
   contrast, lint, and owner e2e all pass; PR preview and post-merge production
   runs succeed.

6. **PhaseTimer's production deploy token is environment-scoped and preview is
   isolated.** Preview and close use only `AZURE_STATIC_WEB_APPS_API_TOKEN_PREVIEW`;
   the production environment contains the production deploy token and DB URL;
   the repository-level production token is absent only after both deploy paths
   verify. — Verifier: workflow grep plus secret-name API readback and the two
   deployment run URLs. No secret value appears in the record.

7. **Paragon has no high/critical or production dependency findings and its
   telemetry/toolchain passes the real gates.** Next is `16.4.3`, the overrides
   resolve to `1.2.2`/`8.3.6`/`4.6.6`, Application Insights is `3.17.0`, the
   production audit exits 0, and the full audit contains only dated `minimatch`
   GHSA-g3hv-75wg-m249. — Verifier: the Paragon command block, generated-types
   no-diff check, complete CI run, preview write smoke, and production smoke.

8. **`pln` remains decommissioned with shared production retained.** All five
   GitHub readbacks have their expected values, `pln-prod` still exists, the
   Paragon health endpoint returns `ok`, and the owner residual-key decision is
   dated. — Verifier: the `pln` command block in the remote verification
   record. No local clone or consumer edit is created.

9. **Every active consumer change is isolated and reviewable.** Each active
   repo has one PR from its isolated branch, no direct push to `main`, no
   force-push, and no unexpected primary-checkout diff or branch movement. —
   Verifier: compare the preflight and final `status -sb`, current branch,
   worktree list, and stash list; collect four PR URLs and their checks.
   Pre-existing untracked paths and stashes are unchanged, not "cleaned up".

10. **RM-075 closes only on complete evidence and retains its proof limits.**
    The closure lists all five dispositions and records that unknown public
    consumers, undisclosed secret exposure, future advisories, unexecuted
    external systems, and Supabase health outside the performed checks are not
    proven. — Verifier: `python3 scripts/check_roadmap_verbatim.py` exits 0;
    the roadmap row/counters/detail agree and all five verification links are
    present.

## Files to Modify

### Framework tracked files (coordinator only, during RM-075 implementation)

- `.opencode/plans/fix-consumer-security-exposure.md` — append the Phase 2
  execution record, consumer PR/run links, actual owner decisions, and residuals;
  retain the parent plan for RM-076.
- `docs/ROADMAP.md` — close RM-075 only after AC1–AC10, with matching priority
  strip, horizon count, and closed counter.
- `docs/roadmap-detail/RM-075.md` — add the delivery/evidence record and proof
  limits.
- `.opencode/plans/rm-075-phase-2-consumer-handoffs.md` — retire at the RM-075
  delivering PR under AGENTS rule 4; its durable residue is the parent record,
  roadmap detail, briefs, and verification records.

### Framework scratch artifacts (coordinator only; sanitized, not committed)

- `.scratch/consumer-security-sweep/handoff-excel-daily-monitor.md`
- `.scratch/consumer-security-sweep/handoff-marvin-slack.md`
- `.scratch/consumer-security-sweep/handoff-pt.md`
- `.scratch/consumer-security-sweep/handoff-paragon-learning-network.md`
- `.scratch/consumer-security-sweep/handoff-pln.md`
- `.scratch/consumer-security-sweep/verification-{excel-daily-monitor,marvin-slack,pt,paragon-learning-network,pln}.md`
- `.scratch/consumer-security-sweep/install-manifest-before-phase2.json`

`scripts/check_security_handoffs.py` is deliberately not created here; RM-076
owns that generic checker. The Phase 2 scoped verifier below checks AC11's
required content without claiming RM-076 is delivered.

### Consumer-owned files (edited only by each consumer implementer)

The exact per-repo paths are enumerated in the five workstreams. They are not
framework edits and must not be staged in the framework repo. No consumer
schema or generated type is hand-edited.

## Scope

**Included**

- Five cold-executable briefs and five sanitized verification records.
- Four isolated active-consumer remediation passes and one remote archived-repo
  verification.
- Fixed framework install manifest plus proof of the Phase 1 eval, redaction,
  child-env, auth-root, content-fence, dependency-pin, CI-hash, and posture
  controls at one exact baseline.
- Consumer dependency remediation, PhaseTimer CI ordering/token scoping,
  Marvin service hardening, Excel public-artifact removal, Dependabot config,
  secret-scanning/platform posture, rollback, and owner-only secret steps.
- Owner-dated acceptance for explicitly named residuals that are not fixed.
- Same-PR RM-075 roadmap/detail closure after all evidence exists.

**Excluded**

- Any consumer edit authored or applied from the framework checkout; any
  primary-checkout branch switch, stash, pull, cleanup, or agent deployment.
- Reading secret values or copying `.env*` files. Secrets are owner-write-only;
  metadata/name/mode readback is allowed only as specified.
- Rotation of keys never shown to be exposed without an actual dated owner
  decision. Routine dependency remediation does not imply rotation.
- Phase 1 redesign/rework, a generic consumer posture checker, and the Phase 3
  sweep/advisory/register/handoff checker/weekly `security.yml` (RM-076).
- The RM-008 full permission matrix, RM-015 tagged-worktree delivery model,
  OpenCode upgrades, and generic CI/CD template work.
- Runtime exploitation, penetration tests, full OWASP/ASVS reviews, and
  legal/compliance conclusions.
- Deleting or unarchiving `pln`, destroying shared Azure/Supabase resources, or
  rolling back database migrations.
- Claims to enumerate unknown public consumers or to prove that no secret ever
  left a host when the available evidence cannot establish that fact.

## Schema / Type Impacts

No database, Supabase schema, migration, RPC, or generated-type change is in
scope. Paragon runs `pnpm db:types` only as a no-drift verifier and never
hand-edits `packages/shared/src/database.types.ts`. PhaseTimer does not run
`gen:types` or hand-edit `src/types/database.types.ts`. Any generated diff or
migration requirement stops the consumer pass for a revised plan.

Dependency manifests and lockfiles change only in the consumer workstreams.
The framework install manifest remains the Phase 1 JSON contract
`repo_path`, `commit`, `dirty`, `installed_at`; its schema is unchanged.

## Verification

### Framework scoped handoff completeness check

Run from the framework repo after authoring the five briefs. This is the
Phase 2 content verifier for original AC11; it is not the deferred RM-076
`check_security_handoffs.py` implementation.

```bash
python3 - <<'PY'
from pathlib import Path
root = Path('.scratch/consumer-security-sweep')
files = {
    'excel-daily-monitor': 'handoff-excel-daily-monitor.md',
    'marvin-slack': 'handoff-marvin-slack.md',
    'pt': 'handoff-pt.md',
    'paragon-learning-network': 'handoff-paragon-learning-network.md',
    'pln': 'handoff-pln.md',
}
required = [
    '64251af5540d7c1d6ab2d833cc1a92cbbe001bf6',
    'Before', 'After', 'Verification', 'Pass criteria', 'Rollback',
    'Owner-only', 'no `audit fix --force`', 'no undated suppression',
]
for repo, name in files.items():
    text = (root / name).read_text(encoding='utf-8')
    missing = [token for token in required if token not in text]
    assert repo in text, (repo, 'repo name')
    assert not missing, (repo, missing)
    print(f'PASS {repo}: {name}')
PY
```

Each brief also carries an explicit versions table and every command from its
workstream. The completeness check does not prove that a command ran; the
consumer verification records carry that separate evidence.

### Framework final checks

```bash
python3 scripts/check_roadmap_verbatim.py
git diff --check
git status --short
# Only the plan/parent/roadmap/detail paths intended for the current PR are staged.
# Scratch briefs, audit output, research, and verification logs remain untracked.
```

### Consumer checks

The exact commands and pass criteria are in each workstream and are copied into
its cold-executable brief. The coordinator verifies four consumer PRs with
green required checks plus the archived `pln` readbacks. The coordinator does
not substitute framework tests for consumer tests or a clean lockfile for a
runtime deployment.

## Open Questions

1. **Base drift after this design pass.** Recommended default: pin live `main`
   at execution and stop on any changed path for Marvin, PhaseTimer, and
   Paragon; allow Excel changes only under `data/**`. Rerun the relevant audit
   and revise exact versions before proceeding on any other drift. Do not apply
   the design-time SHAs as rollback targets.

2. **PhaseTimer residual acceptance.** Recommended default: use the lock-trial
   manifest targets and date-accept exactly GHSA-c475-qrg2-pj4r,
   GHSA-gcqx-w48m-w2h4, GHSA-3g3m-2fjr-6pw4, and GHSA-g3hv-75wg-m249 for
   development-only paths, reviewed by 2027-01-25. If the owner requires zero
   high findings, stop and design an LHCI/get-uri replacement or compatible
   major upgrades; do not force `basic-ftp 6`.

3. **Paragon `minimatch` residual.** Recommended default: accept only
   GHSA-g3hv-75wg-m249 in the TypeScript-ESLint development path, with actual
   owner date and 2027-01-25 review. A major override needs separate tests and
   approval. The `applicationinsights 3.17.0` runtime gate is not optional.

4. **Unrotated local/shared credentials.** Recommended default: preserve the
   existing PhaseTimer never-exposed local dev-key acceptance and obtain actual
   owner-dated decisions for Marvin Slack tokens and the shared dev
   password/Porkbun/Pulumi residuals. Review by 2027-01-25. If non-exposure
   cannot be attested, invoke incident handling and coordinated owner-only
   rotation; never rotate by default.

5. **PhaseTimer Node baseline.** Recommended default: Node `22.23.3` in CI and
   `>=22.22.2 <23` in the manifest because it is installed and satisfies the
   fresh dependency engines. If the owner standardizes on Node 24 instead, use
   a Node `24.15.0+` baseline, revise all versions, and rerun the full lock/test
   trial. Never use `--ignore-engines`.

6. **PhaseTimer preview credential split.** Recommended default: create
   `phasetimer-preview` and delete the repository-wide production token only
   after preview and production verification. If the owner prefers to retire
   previews instead, revise the brief explicitly; do not merely move the token
   and leave preview broken or secretly sharing the production credential.

7. **Excel public diagnostics.** Recommended default: remove public failure
   artifacts entirely. A later sanitized-text-only artifact requires a new
   redaction design covering student identifiers, URLs, HTML, and binary
   screenshots; it is not part of this pass.

8. **Missing local `pln` checkout and shared Supabase proof.** Recommended
   default: use remote read-only decommission checks and Paragon application
   evidence; do not clone the archived repo. If the owner requires direct
   Supabase health evidence, the owner supplies project references for an
   approved read-only check. Absence is recorded as unverified, not guessed.

9. **AC11 verifier ownership.** Recommended default: Phase 2 uses the scoped
   completeness check above and five content-complete briefs; RM-076 builds
   `scripts/check_security_handoffs.py`. Therefore this plan satisfies AC11's
   handoff content clause but does not claim the deferred generic checker or
   Phase 3 is delivered.

10. **Stack-specific planning guidance.** No one bundled stack reference fits
    this multi-repo operations item (generic Node, Vue, and Next consumers).
    Recommended default: use the actual consumer manifests/workflow commands
    above and the reviewed Next/Vue dependency paths, with no hand-translated
    application architecture changes. Runtime failures route back to a scoped
    revision rather than generic stack assumptions.

11. **Machine-readable consumer inventory is still absent.**
    `reference/consumer-repos.md` does not exist at fixed baseline `64251af`.
    Recommended default: Phase 2 uses the five owner-confirmed slugs corroborated
    by `SECURITY.md`, RM-075, and the parent plan; RM-076 creates the inventory
    and `--list` verifier. Do not invent that Phase 3 artifact merely to make the
    handoff completeness check pass.

## History

- 2026-11-07 — Initial RM-075 draft. UX consult skipped: no user-facing UI.
  No single matching stack reference; used the actual consumer commands and
  recorded the gap as OQ10. Preserved the cross-repo, secret-write-only,
  no-force, dated-disposition, and Phase 3 boundaries.
- 2026-11-07 — Read-only fleet verification found `pln` absent locally,
  Paragon's primary on a feature branch, Excel behind remote only in
  `data/status.json`, and PhaseTimer behind remote in four security/workflow
  files. Verified existing worktrees/stashes and live processes without
  changing them. Paragon's primary `ROADMAP.md` appeared modified between the
  initial and final read-only status checks; it was left untouched and is a
  preflight preservation item. Live API confirmed `pln`
  archive/Actions/secret/run/issue state, all four active Dependabot
  alert/update settings, the Paragon health endpoint `ok`, and the framework
  eval secret split and posture checker.
- 2026-11-07 — Ran network audits only against committed manifests copied into
  framework `.scratch/rm-075-research`; no consumer install or script ran in a
  primary checkout. Results replaced the stale sweep counts: Excel zero at
  current and target Playwright; Marvin three packages fixed by explicit
  overrides; Paragon 12 advisories reduced to one development residual in the
  lock trial; PhaseTimer 153 unique advisories reduced to four named
  development residuals and zero production findings in the lock trial.
- 2026-11-07 — Scratch-only compatibility findings: PhaseTimer requires the
  Vite-compatible PWA set and Node `22.23.3` (or Node `24.15.0+`), and rejects
  a `basic-ftp 6` major override; Paragon's Application Insights `3.17.0`
  upgrade clears OpenTelemetry advisories but still needs real build/telemetry
  gates. No application test, deployment, service restart, secret write, or
  consumer edit was performed in this design pass.
- 2026-11-07 — Verified framework secret-bearing main run 42380383465 and PR
  run 42402998846 with no eval job. Main run 42403341546 at the fixed baseline
  had an empty docs-only eval matrix and is not counted as secret-bearing
  evidence. Added explicit unknown-consumer and unprovable-external-state
  limits plus the deferred AC11 checker boundary.

### What this plan cannot prove

This plan covers only the five owner-confirmed consumers named above. Unknown
public consumers cannot be enumerated from this machine or the framework repo;
Phase 1 controls are their propagation protection and RM-076 is the repeatable
future detection control. No finite sweep proves "all consumers" or "all
exposures". Point-in-time audits do not predict later advisories. Lockfile
trials do not prove runtime compatibility, and API readbacks do not prove a
secret was never exposed. The plan also cannot prove direct `pln` Supabase
project health without an approved owner-supplied read-only check. Every such
limit must remain visible in the closure record.
