---
slug: opencode-v2-upgrade
title: Migrate the OpenCode integration from V1 1.19.4 to V2 2.1.4
status: approved
created: 2026-10-26
revised: [2026-10-26, 2026-10-27, 2026-10-27]
related: [RM-044, RM-058, RM-067]
---

# Plan: opencode-v2-upgrade

## Goal / Approach

**Goal:** every OpenCode-facing surface in this library — agent/config/install,
run-vehicle dispatch, wake-on-completion, watchdog/guard, behavioral evals, CI,
and the docs that describe them — runs on OpenCode V2 `2.1.4` with no V1-only
surface left, verified by an isolated canary, hermetic suites, and live drills,
and reversible with a drilled rollback.

**Approach:** this is a cutover, not a dual-run layer. V1 and V2 cannot coexist
under the default `opencode` command; scripts call one binary and one config
dialect. Introduce one shared adapter — `scripts/opencode_v2.py` — that owns
every version-specific fact (binary/version probe, service discovery, typed
`/api/*` calls, `OPENCODE_DB` resolution, V2 DB readers, permission-rule
builder, event/tool normalizer, denial classifier). `dispatch_agent.py`,
`observe_completion.py`, `watch_agent.py`, `session_guard.py`, and the eval
runner import that adapter instead of re-deriving V1 facts. The repo keeps its
contracts (dispatch CLI, heartbeat lines, run-log shape, exit codes, eval
predicates) and changes only the vehicle underneath them.

The migration is gated from the outside in:

1. **Phase 0 — canary only (no repo change).** Install V2 into an isolated
   prefix, prove the service/API/model/stability surface, back up V1 config and
   the session DB, and drill the rollback. Any failed gate stops the migration
   before a commit exists.
2. **Phase 1 — adapter + config/agents/install.** Stage the native V2 agent and
   permission conversion (validated in a temp agents directory), the install
   validator, the V2 package pin, the two offline checkers, and the rewritten
   reference page. Do not swap the live symlinked corpus yet.
3. **Phase 2 — dispatcher.** cwd/PWD instead of `--dir`, always `--model`,
   session preflight, shared-service default with `--standalone`/`--server`
   options, timeout `session.interrupt`, V2 deny-by-default permission merge,
   V2 denial classifier, V2 stream normalization.
4. **Phase 3 — wake.** `session.get` preflight, `session.switchAgent`, then
   `session.prompt` through the service API; no `--attach`; 404 defers instead
   of creating a ghost session.
5. **Phase 4 — watchdog + guard.** API-first reading with the read-only DB as
   the offline fallback; `session_v2`/`session_message` readers;
   `session_v2.time_idle`/`idle_outcome` as the completion signal; model/tokens
   from the V2 row or API; one adapter shared by both supervision scripts.
6. **Phase 5 — eval/CI.** `@opencode/cli@2.1.4`, `--standalone`,
   `OPENCODE_LOG_LEVEL=ERROR`, cwd/PWD, per-run `OPENCODE_DB` and XDG
   isolation, V2 tool vocabulary, and the workflow assertions.
7. **Phase 6 — docs/ADR/roadmap + live drills + cutover.** Rewrite the dated
   reference, update every active tool-name/flag reference, land ADR-0014 and
   the roadmap row, swap the agent corpus into the live layout, run the live
   drills against the host V2 default, then merge.

Each phase leaves the full verification suite green. The host default
`opencode` stays V1 until Phase 6; live work before that uses
`PATH=<isolated-prefix>/bin:$PATH` so the branch scripts exercise V2 while the
default command remains the rollback path. The DB migration is one-way: the
backup is the V1 rollback, not a live dual-read.

**Transition safety:** implement on a branch worktree while the global
`~/.config/opencode/agents` and `skills` symlinks still point at the primary
checkout. Editing the branch corpus does not change the running V1 personas
until the symlink target moves or the branch merges. Do not run `install.sh`
from the branch before the cutover; agent conversion and the default-command
switch are one atomic operational step, and no new V1 session should start
between them.

### Revised 2026-10-27 — Option A: isolated canary, drained atomic switch

This revision supersedes the earlier host-action and cutover ordering. The code
migration still uses Phases 1–6 above, but no framework or consumer PR merges
before the drained runtime switch and post-cutover smoke succeed.

1. **C5 before every other canary gate.** The canary script first takes the
   consistent SQLite backup through Python `sqlite3`, backs up the global
   config, snapshots **dereferenced** V1 agent files, and verifies hashes plus
   `PRAGMA integrity_check`. The `sqlite3` CLI is not available and is not used.
   Only after C5 passes may it install or invoke V2. Every V2 invocation asserts
   an `OPENCODE_DB` under `.scratch/v2-canary/` and isolated XDG
   state/cache/runtime/TMPDIR; the real DB is never an implicit default.
2. **Real-config C3 and separated write classes.** C3 deliberately reads the
   real global config/auth, but imports the current `opencode-go` credential
   from V1 `auth.json` into the isolated DB over stdin (`api` → `key`) without
   printing or persisting a secret JSON file. C4 always uses a new empty DB.
   Migration rehearsal is a separate gate on a copy of the 2.96 GB backup with a
   900-second timeout, source-hash verification, `session_v2` population checks,
   and an explicit fidelity report. A stability run is never used as migration
   evidence.
3. **Implement and review two unmerged PRs.** The implementer works from this
   plan on `feat/opencode-v2-upgrade` in a framework branch worktree. Paragon
   migration occurs only in an isolated worktree at an approved commit (research
   baseline: `7b36953`), never in its dirty primary checkout. Both PRs carry
   their tests and review evidence and remain unmerged while the host stays V1.
4. **Consumer-readiness gate.** The consumer script validates Paragon's native
   V2 `opencode.json`, all ten project wrappers, tool names, model bindings, and
   plugin dependency surfaces; runs the V2-aware framework checker and an
   isolated V2 consumer smoke; and writes a readiness artifact containing both
   PR URLs and exact framework/consumer commit SHAs. The cutover refuses stale,
   missing, dirty, or mismatched readiness evidence.
5. **Drain gate.** After both PRs are approved and merge-ready, the owner closes
   every architect, implementer, reviewer, consumer, detached dispatch, watcher,
   and OpenCode service session. From a normal terminal, the cutover preflight
   verifies no matching live processes/services, takes a fresh final V1 backup,
   verifies it, and records an explicit drain acknowledgement. The architect and
   implementer sessions never execute the final cutover.
6. **Atomic/versioned switch.** The normal-terminal cutover installs V2 only
   into `$HOME/.local/lib/opencode/2.1.4/`, stages a versioned V2 config root
   containing the reviewed agent/plugin corpus, and points one wrapper at that
   runtime plus config. It then atomically replaces the user-owned
   `$HOME/.yarn/bin/opencode` symlink with that wrapper using a same-directory
   rename. The wrapper sets `XDG_CONFIG_HOME` to the versioned V2 root, so one
   symlink switch selects both binary and config. The existing V1 package,
   `~/.config/opencode` agents, config, and plugin remain untouched. A manifest
   records the original symlink, versioned paths, commit SHAs, and final backup.
7. **Post-smoke before merge.** The post-smoke script proves the default command
   is V2, loads all 17 framework agents and ten Paragon wrappers, checks config,
   credentials, plugin disposition, migrated `session_v2`, and runs the live
   drills. Only then does the owner merge the two PRs. A post-merge invocation
   verifies the merged SHAs and the versioned corpus matches them.
8. **Rollback restores V1, including agent files.** Any failed gate or smoke
   invokes the cutover script's rollback mode: stop V2 writers, preserve the
   failed V2 DB, restore the final pre-cutover DB through Python `sqlite3`,
   atomically restore the original `~/.yarn/bin/opencode` symlink, verify the
   preserved V1 config/plugin and dereferenced agent hashes (restoring those
   files from the C5 snapshot if any differ), and prove V1 1.19.4 reads the
   restored DB. Because the PRs are still unmerged, no consumer checkout needs
   rewriting during this rollback.

The four operational entry points are `scripts/opencode_v2_canary.py`,
`scripts/opencode_v2_consumer.py`, `scripts/opencode_v2_cutover.py`, and
`scripts/opencode_v2_post_smoke.py`. They fail closed, have hermetic tests, and
never infer a successful gate from a partially written artifact. The cutover
alone requires a TTY, `--execute`, `--drain-acknowledged`, the final backup, and
matching consumer-readiness evidence; it is not run by an agent session.

### Canary evidence (2026-10-27)

All canary writes stayed under `.scratch/`. No global V2 install, global cutover,
or real session-DB write occurred. Port 49374 was free after the probes.

| Gate | Result | Evidence and material facts |
|---|---|---|
| C1 | PASS | `.scratch/v2-canary/C1.txt`: isolated output `opencode v2.1.4`; default remains `1.19.4`; default symlink is `$HOME/.yarn/bin/opencode`. |
| C2 | PASS | `.scratch/v2-canary/C2.txt`: `/api/info` returned `2.1.4`; the stale managed service was subsequently stopped. |
| C3 | PASS after credential isolation | `C3-real.txt`, `models-real.txt`: all eight `opencode-go/*` bindings present. V2 stores credentials in the selected DB; real auth was imported into the canary DB only. |
| C4 | PASS | `C4.txt`: renewed credential, fresh empty DB, 10/10 exit 0 with final text `OK`; 1.77–9.67 seconds per run; no pre-session hang. Two earlier expired-key failures remain recorded and were not counted. |
| C5 | PASS | `C5.txt`, `backup.sha256`: 2,955,141,120-byte DB, SHA-256 `3a44d625…a035a1`, integrity `ok`, 2,195 V1 sessions; config tarball hash also verified. |
| Migration rehearsal | PASS with fidelity residual | `migration-rehearsal.txt`: copy-only 900-second gate; 2,076 source sessions populated `session_v2`, one new smoke returned `OK`, integrity `ok`, source backup hash unchanged. 119 source sessions with messages were absent from `session_v2`; this is not a lossless-migration claim and requires classification or explicit owner acceptance before cutover. |
| C6 | PASS | `C6.txt`: isolated `opencode-ai@1.19.4` read three sessions from the restored backup; all IDs belonged to that backup. |
| C7 | PASS as audit | `global-config-audit.md`: `small_model` normalizes to `agents.title.model`; `instructions` survives. The V1 plugin export is rejected; a wrapper alone is not a functional port. Native V2 config/plugin shapes and the static-disable fallback are recorded. |
| C8 | PASS | `C8.txt`: no active Todo/`todowrite`, LSP, or websearch dependency outside this plan; no enablement or workaround added. |

### Canary gates (Phase 0, before any repo change)

All evidence is written under `.scratch/v2-canary/` (never `/tmp`). No canary
step may touch the real DB except the backup read.

| Gate | Check | Pass condition | On failure |
|---|---|---|---|
| C1 | Isolated install: `npm install --global --prefix .scratch/v2-prefix @opencode/cli@2.1.4` | `PATH=.scratch/v2-prefix/bin:$PATH opencode2 --version` prints `2.1.4`; default `opencode --version` still `1.19.4` | Stop; do not install globally |
| C2 | Service/API: `opencode2 service status`; `opencode2 api get /api/info` | Both exit 0 and return JSON; exact output saved | If `api` is missing (#59251), record it and block Phase 3 until the direct-HTTP fallback in `opencode_v2.py` is proven |
| C3 | Models: `opencode2 models` | Every `model:` value in `agents/*.md` appears | Stop; a missing binding is a rollback trigger |
| C4 | Stability: 10× `timeout 180 opencode2 run --standalone --model opencode-go/deepseek-v4.1-flash --format json "Reply OK"` | 10/10 exit 0, non-empty text containing `OK`; no pre-session hang (#59287) | Stop; try the version policy below; do not paper over a hang |
| C5 | Backup: tar `~/.config/opencode` (excluding `node_modules`) and `sqlite3 <db> ".backup '<backup>/opencode.db'"` | `sha256sum -c backup.sha256` and `sqlite3 <backup>/opencode.db "pragma integrity_check;"` print `ok` | Stop; no repo change |
| C6 | Rollback drill: `npm install --global --prefix .scratch/v1-prefix opencode-ai@1.19.4` + restore the DB copy into a temp `XDG_DATA_HOME` | V1 `--version` prints `1.19.4`; V1 reads the restored DB (`session list` or `watch_agent.py`) | Stop; the backup is not a rollback |
| C7 | Plugin/global config probe: load the global config under V2 in a temp config copy; probe a V1-shape agent/permission config, an `OPENCODE_CONFIG_CONTENT` marker (agent + permission), and the plugin API | The accepted key names (`agents`, `permissions`, ordered rules), the `OPENCODE_CONFIG_CONTENT` acceptance, and the plugin form are recorded; a rejected form is named | If `OPENCODE_CONFIG_CONTENT` is unsupported, switch to a temp config file; if the plugin API is absent, record a dated static-disable and open a follow-up |
| C8 | Capability audit: repo-wide grep for `todowrite`, LSP, websearch use | No skill/agent depends on Todo, LSP, or websearch; record the negative | If a dependency exists, add a dated workaround or block |

### Known V2 risks and mitigations

| Risk | Impact | Mitigation / gate |
|---|---|---|
| Linux `run` hang before session creation (#59287, 2.1.4/2.0.32) | A dispatch or eval hangs with no session ID, so interrupt cannot help | C4 is a hard 10/10 gate; `run_opencode` keeps the process-group timeout kill; the outcome records `no-session` when it fires; no automatic retry loop |
| Service/API/plugin list reportedly missing (#59251) | Wake and API-first watchdog cannot reach the service | C2/C7 probe; `opencode_v2.py` falls back to `service.json` + HTTP; if both fail, Phase 3 is blocked (honest deferral, not a silent downgrade) |
| Agent model not applied; no `--variant`/`OPENCODE_PERMISSION` (#55278) | A dispatch runs the wrong model | Dispatcher always passes `--model`; D1 verifies the session model; no variant and no `OPENCODE_PERMISSION` are used |
| `external_directory` defaults to allow | A dispatch can read outside its grant | Deny-first ordered rules + explicit allow roots; D2 negative drill; `execute: deny` |
| Shared server survives client timeout | Generation continues after the client is killed | `session.interrupt` on timeout + verify not active; `--standalone` for CI |
| Title/free-tier behavior (#58176) | Titles or free-tier routing are unreliable | Session identity is the ID, never the title; no persona is free-bound |
| Console provider registration (#58335) | A provider path differs | Not used by this repo; recorded as out of scope |
| Websearch keyless change (#54311) | A websearch-dependent skill would break | C8 audit: no skill depends on websearch |
| LSP not run (#56276) | An LSP-dependent skill would lose diagnostics | C8 audit: no skill depends on LSP |
| Todo guidance missing (#59259) | Agents get no todo tool guidance | C8 audit: no skill depends on Todo; the migration does not add it |
| Code Mode `execute` bypasses policies (#56349) | A policy bypass | `execute: deny` on every persona |
| Root `-m`/`--agent` removed (#56218) | Old invocations fail | Only `run --agent` / `run --model` are emitted; C1/C4 exercise them |

### Version policy

- Pin exactly `2.1.4` in CI, the reference page, and the ADR. No `latest`, no
  caret range, no auto-update.
- Fallback only on a failed canary gate: the highest `2.x` that passes C1–C6.
  `2.0.32` is **not** presumed safe — #59287 names it too. If no `2.x` passes,
  stop and stay on V1 `1.19.4`; report the gate evidence.
- Re-verify the dated facts on every touch; `reference/opencode-integration.md`
  is the volatile-facts home.

### Security posture

- `external_directory` is deny-by-default for every dispatch profile. The
  adapter emits an ordered catch-all deny first and explicit `<abs-path>/**`
  allow rules after it, matching the precedence proved at canary C7. Persona
  files do not carry `external_directory`; the dispatcher owns the grant and
  validates each `--allow-dirs` path before launch (exit 2 on a missing path).
- `execute: deny` on every persona. Code Mode is not needed by any framework
  skill; denying `execute` closes the #56349 policy bypass. Re-open only with a
  named task and a dated record.
- No `--auto` in dispatch, wake, eval, or CI. V2 auto-rejects asks in
  noninteractive runs and continues; the dispatcher must classify that as
  `permission denied: …`, never as `empty result`.
- Shell allowlists convert 1:1 (`bash` key → `shell` key, same patterns, same
  order). The new checker compares each persona against `git show main:` and
  fails on any added allow pattern. No widening, no new broad globs.
- No `OPENCODE_PERMISSION` (unsupported in V2); permissions travel only through
  config. `OPENCODE_LOG_LEVEL=ERROR` replaces `--log-level`.
- DB access stays read-only (`file:…?mode=ro`). The only mutating control call
  is `session.interrupt` on timeout; no session deletion, no DB writes.
- The canary uses an isolated prefix and a copied DB; the backup is `0600`.
  Secrets are never echoed. No test is skipped or weakened: the V2 assertions
  replace V1 assertions with equal or stronger checks.

### Roadmap ID note

The next open ID is `RM-067`, but an untracked draft plan
(`.opencode/plans/fix-consumer-security-exposure.md`) also claims it. At
implementation time, take the next free ID: use `RM-068` with a detail file
`docs/roadmap-detail/RM-068.md` if the security plan landed first; otherwise
`RM-067`. Never create a duplicate.

## Acceptance Criteria

1. **Canary install and version isolation.** The isolated prefix installs
   `@opencode/cli@2.1.4`; `opencode2 --version` prints `2.1.4` while the
   default `opencode --version` still prints `1.19.4`. — Verifier: the exact
   commands in C1; output saved to `.scratch/v2-canary/C1.txt`.
2. **Service/API discovery is proven.** At least one sanctioned path reaches
   the service: `opencode2 api get /api/info` exits 0 with a JSON body, or the
   `service.json` + HTTP fallback returns the same info when `api` is absent
   (#59251). — Verifier: `.scratch/v2-canary/C2.txt` records both probes with
   exit codes; if both fail, Phase 3 is blocked and the plan is revisited.
3. **Model catalog completeness.** Every `model:` value bound in `agents/*.md`
   appears in `opencode2 models`. — Verifier:
   `comm -23 <(grep -h '^model:' agents/*.md | awk '{print $2}' | sort -u) <(opencode2 models | sort)`
   prints nothing, using the output format recorded at C3 (if `models` prints a
   table, the canary-recorded parser replaces the one-liner).
4. **Stability gate.** Ten consecutive standalone trivial runs complete without
   a pre-session hang. — Verifier: the C4 loop exits 0 ten times, each with a
   non-empty final text containing `OK`; timings saved to
   `.scratch/v2-canary/C4.txt`.
5. **Backup integrity.** The V1 config tarball and a consistent SQLite backup of
   `opencode.db` exist and verify. — Verifier:
   `sha256sum -c .scratch/v2-canary/backup.sha256` exits 0 and
   `sqlite3 .scratch/v2-canary/opencode.db "pragma integrity_check;"` prints
   `ok`.
6. **Rollback is drilled, not asserted.** An isolated V1 install plus the
   restored DB copy reads the V1 session data. — Verifier: C6 commands; V1
   `--version` is `1.19.4` and a V1 session read succeeds against the restored
   copy.
7. **Native V2 agents load.** All 17 agent files carry a path-derived ID (no
   `name:`), and `install.sh` links all 17 into a fresh agents directory. —
   Verifier: `OPENCODE_AGENTS_DIR=<tmp> ./install.sh` prints
   `Installed 17 agent(s)`; `opencode2 agent list` lists all 17 (if the V2
   command differs, the canary-recorded equivalent is used); `grep -c '^name:' agents/*.md`
   returns 0 for every file.
8. **No V1 agent/config keys remain.** The agent corpus uses `permissions`
   (ordered) with `shell`, `subagent`, `edit`, `execute`; no `permission`
   singular, `bash`, `write`, `task`, or per-agent `external_directory`. —
   Verifier: `python3 scripts/check_v2_config.py` exits 0;
   `python3 scripts/test_v2_config.py` exits 0 and proves a V1 fixture is
   rejected.
9. **Permission conversion is 1:1.** Every persona's allowed shell patterns are
   identical to its V1 `bash` allow set; no pattern is added. — Verifier:
   `python3 scripts/check_v2_config.py --baseline main` exits 0 (it parses
   `git show main:agents/<name>.md` and fails on any added allow pattern).
10. **V2 package/plugin pin.** No active surface carries `@opencode-ai/plugin`;
    the ignored dev pin `.opencode/package.json` (see `.opencode/.gitignore`)
    and the global config pin the V2 plugin package at the version resolved for
    `2.1.4` at C7 (never a V1 package, never `latest`). — Verifier:
    `python3 scripts/check_v2_surfaces.py` exits 0 (its allowlist covers the
    historical ADR/roadmap/plan text); `grep -R "@opencode/plugin"
    .opencode/package.json ~/.config/opencode/package.json` shows the recorded
    pin; `npm --prefix .opencode ls @opencode/plugin` reports that version.
11. **Global config/plugin audit recorded.** The host `~/.config/opencode`
    config and plugin are audited and either ported and load-verified or
    disabled with a dated record. — Verifier:
    `.scratch/v2-canary/global-config-audit.md` names every key and the
    `auto-compact-at-threshold` plugin with its disposition; a V2 `--standalone`
    run's captured log contains the plugin's startup marker, or the dated
    disable entry is present.
12. **Consumer binding checker is V2-aware.** `check-consumer-bindings.py`
    resolves path-derived agent IDs, the V2 `agents` config object, and
    `small_model` without treating `name:` as authoritative. — Verifier:
    `python3 scripts/test_model_policy.py` exits 0 and
    `python3 scripts/check-consumer-bindings.py .` exits 0.
13. **Dispatcher argv and stream.** The dispatcher launches
    `opencode run --agent … --format json` with no `--dir`, `--attach`, or
    `--log-level`; the child gets `cwd` and `PWD` set to the dispatch directory;
    a model is always passed; the V2 JSON stream fixture yields session ID,
    final text, tokens, cost, and tool events. — Verifier:
    `python3 scripts/test_dispatch_agent.py` exits 0; its stub asserts argv,
    cwd, PWD, and the parsed V2 fixture.
14. **Resume preflight.** A `--session` targeting an unknown session exits 2
    with `unknown session` and never launches `opencode`; a known session
    launches and the returned ID equals the requested ID. — Verifier: new
    hermetic tests in `scripts/test_dispatch_agent.py` with an API stub
    returning 200/404.
15. **Timeout interrupt.** On a shared-service timeout the dispatcher calls
    `session.interrupt`, verifies the session is no longer active, and records
    `interrupt=ok|failed|no-session`; in `--standalone` mode it records
    `interrupt=not-needed` and kills only the process group. Exit code 4 is
    unchanged. — Verifier: `python3 scripts/test_dispatch_agent.py` timeout
    test asserts the stub call and the outcome detail.
16. **Deny-by-default external paths.** A dispatch with no grant cannot read a
    path outside its working directory; a dispatch with `--allow-dirs` can. —
    Verifier: live drill D2: the ungranted run exits non-zero with
    `permission denied: external_directory <path>`; the granted run exits 0.
17. **Denial classification.** V2's noninteractive auto-reject is classified as
    `permission denied: <tool> <target>`, never `empty result`. — Verifier:
    a canary-captured V2 denial fixture is asserted in
    `python3 scripts/test_dispatch_agent.py`.
18. **Model binding is applied on every dispatch.** A dispatch without an
    explicit `--model` runs the target's effective binding, resolved in V2
    discovery order (project `.opencode/agents/`, repo `agents/`, global
    layout); a missing binding exits 2 before launch. — Verifier: D1 prints
    `model=<binding>` and `GET /api/session/{id}` (or the V2 session row)
    equals the value in the effective agent file; a hermetic test with no
    `model:` and no explicit flag exits 2.
19. **Wake uses the service API, not `--attach`.** The observer preflights
    `session.get`, compares the returned ID to the requested ID, defers with a
    named reason on 404, switches the agent, then prompts the same session; no
    new session is created. — Verifier: `grep -R -- "--attach" scripts/` prints
    nothing; `python3 scripts/test_observe_completion.py` exits 0 with the
    preflight / switch / prompt sequence asserted.
20. **No ghost turn.** The live wake appends exactly one turn to the
    orchestrator's existing session, attributed to the wake agent, with no new
    session row. — Verifier: drill D5: `WAKE success` within 5 minutes, the
    session ID is unchanged, and the pre/post session counts are equal.
21. **Watchdog reads V2.** `watch_agent.py` reports OK / STALLED / DONE from
    V2 data, uses `session_v2.time_idle` and `idle_outcome` when present, and
    exposes model and token totals. — Verifier:
    `python3 scripts/test_watch_agent.py` exits 0 with V2 fixtures; drill D3
    produces the three expected verdicts.
22. **Guard reads V2.** `session_guard.py` enumerates `session_v2`, reads
    `session_message`, detects the dead-stream and denial-carrier patterns, and
    shares the adapter with the watchdog. — Verifier:
    `python3 scripts/test_session_guard.py` exits 0 with V2 fixtures; drill D4
    scans a two-child wave without a false abort.
23. **Degradation is preserved.** With no DB and no service, the watchdog and
    guard fall back to heartbeat-only behavior and keep their documented exit
    codes. — Verifier: the existing absent-DB/absent-server fixtures in
    `test_watch_agent.py` and `test_session_guard.py` exit 0.
24. **CI pins V2.** Both eval workflows install `@opencode/cli@2.1.4`, set
    `OPENCODE_LOG_LEVEL=ERROR`, and contain no `--log-level`, `--print-logs`,
    `opencode run --dir`, or `opencode-ai@`. — Verifier:
    `python3 scripts/test_eval_workflows.py` exits 0 and a grep of
    `.github/workflows/` finds no V1 token.
25. **Eval runner is V2-native and isolated.** Each eval runs with cwd and
    `PWD` set to the temp workdir, `--standalone`, an explicit `--model`, a
    per-run `OPENCODE_DB`, and per-run `XDG_STATE_HOME`/`XDG_CACHE_HOME`; the
    host DB row count is unchanged; a continuation whose session is missing is
    logged as `continuation_lost` and restarted fresh. — Verifier:
    `python3 skills/authoring-skills/scripts/test_runner.py` exits 0; a live
    eval leaves the host `session_v2` count unchanged.
26. **Typed eval vocabulary is updated.** Manifests, event-stream fixtures, and
    the authoring docs use V2 names (`shell`, `edit`, `path`); the harness
    accepts V1 aliases for consumer evals and logs the alias. — Verifier:
    `python3 scripts/test_typed_evals.py`, `python3 scripts/check_typed_evals.py --base main`,
    and `python3 skills/authoring-skills/scripts/test_runner.py` all exit 0.
27. **Live eval canary passes.** One core and one default eval pass on V2. —
    Verifier:
    `python3 skills/authoring-skills/scripts/run_behavioral_eval.py --model opencode-go/deepseek-v4.1-flash --core --skill designing-architecture`
    and the same with `--default --skill reviewing-code` both exit 0 with
    `PASS`.
28. **Reference page is V2-only and dated.** `reference/opencode-integration.md`
    documents the V2 binary/package, flags, cwd/PWD, service/API endpoints, DB
    tables, permission semantics, agent path IDs, tools, plugins, and env vars,
    dated 2026-10-26, with no active V1 claim. — Verifier:
    `python3 scripts/test_watch_agent.py` (updated doc assertion) exits 0;
    `python3 scripts/check_v2_surfaces.py` exits 0.
29. **Active docs and skill bodies are updated.** `agent-teams`,
    `subagent-supervision`, `model-routing`, `COUNCIL.md`, `agents/council.md`,
    `designing-architecture`, `validating-ui`, `authoring-skills/*`,
    `skills-library.md`, and `README.md` describe the V2 vehicle and tool names.
    — Verifier: `python3 skills/authoring-skills/scripts/validate_skill.py --all`
    and `python3 scripts/check_v2_surfaces.py` exit 0.
30. **ADR and roadmap closure are on the branch.** `ADR-0014-opencode-v2-upgrade.md`
    exists and is indexed; the roadmap row and detail file exist; the plan is
    retired in the merge PR. — Verifier: `python3 scripts/check_roadmap_verbatim.py`
    exits 0; `test -f docs/ADRs/ADR-0014-opencode-v2-upgrade.md`; the merge PR
    diff deletes `.opencode/plans/opencode-v2-upgrade.md`.
31. **No test weakening.** The migration replaces V1 expectations with V2
    expectations; no test function is deleted, skipped, or loosened. —
    Verifier: `git diff main -- 'scripts/test_*.py' 'skills/**/test_runner.py'`
    contains no `-def test_`, no `.skip`, and no `xfail`; the full command list
    below is green.

### Revised 2026-10-27 — Option A operational acceptance criteria

The following criteria are additive. Where earlier verifiers use the absent
`sqlite3` CLI, the Python `sqlite3` equivalent in the canary/cutover scripts is
the replacement. AC1 accepts the observed V2 version string `opencode v2.1.4`.
AC10's global plugin pin now means the versioned V2 config root, not the preserved
V1 global config.

32. **C5 is the first canary mutation.** Before any V2 service/run/migration,
    the canary creates and verifies a consistent DB backup, config backup, and
    dereferenced V1 agent snapshot; every later V2 process has an explicit
    scratch DB and isolated XDG/TMP paths. — Verifier:
    `python3 scripts/test_opencode_v2_canary.py` includes an ordering assertion
    and a forbidden-real-DB-path test; the live artifact is
    `.scratch/v2-canary/C5.txt` with hash and integrity evidence.
33. **Real-config model readiness is reproducible.** C3 reads the real global
    config/auth but seeds only an isolated credential table, finds all eight
    unique agent bindings, and emits no credential value. — Verifier:
    `python3 scripts/opencode_v2_canary.py --gate C3` exits 0 and writes an
    equivalent of `C3-real.txt` with `missing_bindings=0`; its hermetic test
    proves expired/stale `account.json` is not preferred over current
    `auth.json`.
34. **Stability and migration are independent gates.** C4 starts with zero
    `session_v2` rows and passes 10/10 fresh standalone runs; migration uses a
    separate copy, a 900-second ceiling, populated `session_v2`, source-ID
    membership, integrity, and unchanged source hash. — Verifier:
    `python3 scripts/opencode_v2_canary.py --gate C4` and `--gate migration`
    produce the two artifacts; cutover preflight fails unless the 119-session
    rehearsal residual has since been classified or carries a dated owner
    acceptance.
35. **The drain gate fails closed.** Cutover cannot start with a live OpenCode,
    dispatch, observer, watchdog, or guard process/service, without a fresh
    verified final backup, or without explicit drain acknowledgement. —
    Verifier: `python3 scripts/test_opencode_v2_cutover.py` supplies fake
    process/service/backup states and asserts non-zero exit with no switch for
    each failure.
36. **Paragon readiness is commit-bound.** An isolated Paragon worktree has
    native V2 config, ten path-derived wrappers, updated tool names and package
    surfaces, passing consumer checks, and an isolated V2 smoke; its primary
    checkout is untouched. — Verifier:
    `python3 scripts/opencode_v2_consumer.py ready <paragon-worktree>` exits 0
    and emits exact framework/consumer SHAs plus both PR URLs;
    `python3 scripts/check-consumer-bindings.py <paragon-worktree>` and
    `python3 scripts/test_opencode_v2_consumer.py` exit 0; cutover rejects any
    SHA mismatch.
37. **One atomic link selects the versioned runtime and config.** The default
    command changes only through same-directory atomic replacement of
    `$HOME/.yarn/bin/opencode`; the selected wrapper sets the versioned V2
    `XDG_CONFIG_HOME`; no V1 package, global agent, global config, or global
    plugin file is overwritten. — Verifier:
    `python3 scripts/test_opencode_v2_cutover.py` performs the switch in a temp
    HOME, proves V1 hashes unchanged and V2 version/config/agent discovery,
    and injects a failure to prove automatic restoration.
38. **Rollback restores V1 data and personas.** Rollback restores the original
    binary link and final V1 DB, restores any mismatched V1 agent file from the
    dereferenced snapshot, retains the V1 plugin/config, and proves a V1 session
    read. — Verifier: the temp-HOME rollback test asserts byte-identical V1
    agent/config/plugin files and DB integrity; live evidence must match C6's
    `opencode session list --max-count 3 --format json` success before rollback
    is accepted.
39. **All four operational scripts are tested fail-closed entry points.**
    Canary, consumer, cutover, and post-smoke each reject incomplete evidence
    and never treat a partial run as success. — Verifier:
    `python3 scripts/test_opencode_v2_canary.py`,
    `python3 scripts/test_opencode_v2_consumer.py`,
    `python3 scripts/test_opencode_v2_cutover.py`, and
    `python3 scripts/test_opencode_v2_post_smoke.py` all exit 0; the cutover
    test also proves a non-TTY agent invocation without `--execute` and
    `--drain-acknowledged` cannot switch anything.
40. **Post-smoke gates both merges.** Framework and Paragon PRs remain
    unmerged until the default-V2 post-smoke and live drills pass; failure runs
    rollback, and only success allows the user-initiated squash merges and the
    post-merge SHA/corpus check. — Verifier:
    `python3 scripts/opencode_v2_post_smoke.py --framework <worktree>
    --consumer <paragon-worktree>` writes a passing artifact before either
    merge; `--post-merge` exits 0 afterward; the framework PR includes all
    roadmap closure artifacts and deletes this plan.
41. **Versioned config/plugin behavior is explicit.** The V2 config retains the
    cross-repo instruction and native title model, and auto-compaction is either
    a fully tested V2 plugin with startup marker and subscription/compaction
    proof or an owner-approved dated disable in the versioned root. — Verifier:
    `node --test plugins/auto-compact-at-threshold/test.mjs` and
    `python3 scripts/opencode_v2_post_smoke.py` pass; the smoke shows the native
    title model/instruction, and either the plugin ID/startup marker or the
    approved disable record. A V1 wrapper alone fails this criterion.

## Files to Modify

### New files

- `scripts/opencode_v2.py` — shared adapter: version/binary probe, service
  discovery, typed API calls (`session.get`, `session.agent`, `session.prompt`,
  `session.interrupt`, `session.active`, `session.log`), `OPENCODE_DB`
  resolution, V2 DB readers (`session_v2`, `session_message`, `session_inbox`,
  `event`), permission-rule builder, tool/event normalizer, denial classifier.
- `scripts/check_v2_config.py` — offline linter: rejects V1 agent/config keys,
  validates V2 permission shapes, and with `--baseline main` compares each
  persona's allow set against the V1 file.
- `scripts/check_v2_surfaces.py` — offline linter for active V1-only surfaces
  (`opencode run --dir`, `--attach`, `--log-level`, `--print-logs`,
  `/session/status`, `opencode-ai@`, `@opencode-ai/plugin`, `subagent_type`,
  `task_id`, `permission.external_directory`), with a fixed historical
  allowlist.
- `scripts/test_v2_config.py` — fixtures proving both new linters fail closed.
- `docs/ADRs/ADR-0014-opencode-v2-upgrade.md` — decision record: V2 cutover,
  native config, dispatcher model binding, shared service + interrupt, wake
  API, external-directory posture, version policy, rollback.
- `docs/roadmap-detail/RM-067.md` (or `RM-068.md` if the security plan landed
  first) — provenance, canary evidence, drills, and closure notes.

### Shared scripts

- `scripts/dispatch_agent.py` — drop `--dir` from the child argv; launch with
  `cwd`/`PWD`; always pass `--model` from the effective binding (project
  `.opencode/agents/<name>.md`, then repo `agents/<name>.md`, then the global
  layout); exit 2 with `no model binding for <agent>` when none resolves; add
  `--standalone` and `--server URL` global options (placed before `run`); keep
  `--session` as the only resume path (no `--continue`, no `--fork`; AGENTS.md
  rule 1 still binds); preflight `--session`; interrupt on timeout; build V2
  deny-by-default permission rules; classify V2 denials; use the adapter's
  stream parser.
- `scripts/observe_completion.py` — replace `--attach` delivery with service
  discovery + `session.get` → `session.switchAgent` → `session.prompt`; 404
  defers with `reason=unknown-session`; `--wake-url` maps to the service URL;
  no URL uses local discovery.
- `scripts/watch_agent.py` — adapter-backed session lookup, V2 completion
  signal (`time_idle`/`idle_outcome`), V2 model/token exposure, API-first
  liveness with read-only DB fallback, `OPENCODE_DB`/`OPENCODE_DB_PATH`
  precedence.
- `scripts/session_guard.py` — V2 tree (`session_v2`), message/part reader
  (`session_message`), denial-carrier scan, dead-stream count, shared adapter.
- `scripts/ci-lane-overrides.py` — emit the V2 `agents`/`permissions` shape
  (ordered rules), not the V1 `agent`/`permission` shape.
- `scripts/check-consumer-bindings.py` — path-derived IDs, V2 `agents` object,
  legacy `agent` fallback for consumers, `small_model` retained.
- `scripts/dispatch-profiles.json` — profile comments and keys updated; the
  adapter owns deny-first rules, so profiles carry only allow roots.
- `scripts/test_dispatch_agent.py` — V2 argv/cwd/PWD/model/preflight/interrupt/
  permission/denial/stream fixtures.
- `scripts/test_observe_completion.py` — API wake stubs replace the attach stub;
  preflight/404/switch/prompt assertions.
- `scripts/test_watch_agent.py` — V2 fixtures, completion-signal tests, doc
  assertion for the V2 reference.
- `scripts/test_session_guard.py` — V2 fixture DB and denial-carrier tests.
- `scripts/test_eval_workflows.py` — V2 install pin and env assertions.
- `scripts/test_model_policy.py` — V2 config-shape and consumer-checker
  assertions.
- `scripts/test_agent_dispatch.py` — update any V1 argv/config expectations it
  carries.

### Config, agents, install

- `agents/*.md` (17 files) — remove `name:`, convert `permission:` to V2
  `permissions`, `bash` → `shell`, `task` → `subagent`, fold `write` into
  `edit`, add `execute: deny`; preserve `model`, `description`, `mode`,
  `hidden`. Preserve the one `temperature` value only if C7 accepts it;
  otherwise move it to the provider/model options or drop it with a dated note
  (never silently lose a bound option).
- `install.sh` — validate description + model + path-derived ID; no `name`
  requirement; skip a malformed agent with a named reason.
- `.github/workflows/eval-behavioral.yml` — install `@opencode/cli@2.1.4`,
  `OPENCODE_LOG_LEVEL=ERROR`, update the lane-override comment.
- `.github/workflows/eval-per-change.yml` — same install/env changes and the
  same comment update.
- `.github/workflows/ci.yml` — add the new offline gates
  (`check_v2_config.py`, `check_v2_surfaces.py`, `test_v2_config.py`,
  `test_observe_completion.py`, `test_model_policy.py`) to the existing
  quality-gates step; no new job or topology.

### Eval harness and vocabulary

- `skills/authoring-skills/scripts/run_behavioral_eval.py` — V2 argv, cwd/PWD,
  `--standalone`, `OPENCODE_LOG_LEVEL` (drop `--print-logs`/`--log-level`; keep
  stderr capture), per-run DB/XDG env, V2 event/tool normalization, V1 alias
  logging, denial text; continuation preflights the session and records
  `continuation_lost` + starts fresh instead of letting `--session` silently
  create a new one.
- `skills/authoring-skills/scripts/test_runner.py` — V2 argv/env assertions and
  alias tests.
- `skills/authoring-skills/SKILL.md` — typed-assertion examples use `shell`,
  `edit`, `path`.
- `skills/authoring-skills/references/eval-assertions.md` — V2 stream/tool
  shapes and the V1-alias rule.
- `skills/authoring-skills/references/eval-harness.md` — V2 invocation and
  isolation.
- `skills/auditing-accessibility/evals/evals.json` — `bash` actions → `shell`.
- `skills/capturing-ui-evidence/evals/evals.json` — `bash` actions → `shell`.
- `skills/debugging-test-failures/evals/evals.json` — `bash` actions → `shell`.
- `skills/deploying-with-supabase/evals/evals.json` — `bash` actions → `shell`.
- `skills/managing-github-issues/evals/evals.json` — `bash` actions → `shell`.
- `skills/observing-runs/evals/evals.json` — `bash` actions → `shell`.
- `skills/refining-issue-acceptance/evals/evals.json` — `bash` actions → `shell`.
- `skills/securing-ci/evals/evals.json` — `bash` actions → `shell`.
- `skills/writing-integration-tests/evals/evals.json` — `bash` actions → `shell`.
- `skills/writing-unit-tests/evals/evals.json` — `bash` actions → `shell`.
- `skills/*/evals/fixtures/event-streams/**/events.jsonl` — V2 tool names
  (`shell`/`edit`), `path`, and session fields (8 fixture files; keep one V1
  alias fixture for the harness's backward-compatibility test).

### Docs, ADR, roadmap

- `reference/opencode-integration.md` — full V2 rewrite, dated 2026-10-26.
- `reference/agent-teams.md` — run-vehicle lane, `--session` preflight, model
  binding, wake vehicle, `subagent`/`agent`/`sessionID` task semantics.
- `reference/subagent-supervision.md` — §wake and §watchdog rewritten for the
  service API, `session_v2`/`session_message`, `--server`/discovery, and
  `session.interrupt`.
- `reference/model-routing.md` — the sandbox caveat's V2 permission shape and
  the eval-lane invocation.
- `docs/COUNCIL.md` — `agent: "council-*"` and the V2 subagent/session fields.
- `agents/council.md` — same tool-name and resume-language updates.
- `skills/designing-architecture/SKILL.md` — `council-ux` consulted through the
  V2 `subagent` tool (`agent:`), no `subagent_type`.
- `skills/validating-ui/SKILL.md` — same.
- `skills/implementing-features/references/stacks/skills-library.md` — cite the
  V2 reference; cwd/PWD instead of `--dir`.
- `README.md` — V2 install requirement, version pin, and the no-`name`
  frontmatter rule.
- `docs/ADRs/README.md` — index row for ADR-0014.
- `docs/ROADMAP.md` — the new Now row, horizon strip, and counters.
- `.opencode/plans/opencode-v2-upgrade.md` — this plan; deleted by the merge PR
  after the essence is folded into ADR-0014, the reference, and the roadmap
  detail.

### Host actions (not repo-tracked)

- `.opencode/package.json`, `.opencode/package-lock.json` — ignored by
  `.opencode/.gitignore`; update the local dev pin from `@opencode-ai/plugin`
  to the V2 plugin version recorded at C7 and install it. Do not force-add
  ignored files.
- `~/.config/opencode/package.json` — replace `@opencode-ai/plugin` with the V2
  package version.
- `~/.config/opencode/plugins/auto-compact-at-threshold.js` — port to the
  `Plugin.define`/`setup` API, add one startup log line (service + version) so
  load is observable, and verify it loads; or disable it with a dated record
  and a follow-up row.
- `~/.config/opencode/opencode.jsonc` — audit `small_model` and `instructions`
  under V2; record the accepted shape in the reference page.
- `~/.config/opencode/tui.json` — if present, rename to `cli.json` and verify
  the TUI settings load under V2.

### Revised 2026-10-27 — Operational scripts, plugin, and consumer files

Add these framework files to the earlier lists:

- `scripts/opencode_v2_canary.py` — C5-first orchestration; backup/hash/integrity
  helpers; scratch-environment assertions; current-auth import; C1–C8 evidence;
  fresh-DB stability and separate long-timeout migration rehearsal.
- `scripts/opencode_v2_consumer.py` — `check`/`ready` modes for an isolated
  consumer worktree; native-config and wrapper checks; framework checker and
  isolated V2 smoke; commit-bound readiness artifact. It never edits a consumer
  primary checkout.
- `scripts/opencode_v2_cutover.py` — TTY/execute/drain/readiness preflight;
  final backup; versioned runtime/config/wrapper staging; atomic default-link
  switch; manifest; failure restoration and explicit `--rollback` mode. It is
  documented for the owner's normal terminal, not an architect/implementer run.
- `scripts/opencode_v2_post_smoke.py` — default-V2, model, agent, config,
  plugin, DB, live-drill, Paragon, and post-merge SHA/corpus checks.
- `scripts/test_opencode_v2_canary.py` — gate ordering, path isolation, secret
  handling, fresh-DB stability, migration-copy, and fidelity-residual fixtures.
- `scripts/test_opencode_v2_consumer.py` — V1 rejection, native V2 acceptance,
  readiness SHA/PR binding, dirty-primary refusal, and isolated-smoke stubs.
- `scripts/test_opencode_v2_cutover.py` — drain failures, non-TTY refusal,
  atomic link/config switch in a temp HOME, unchanged V1 hashes, injected-failure
  restoration, and full V1 agent/config/plugin/DB rollback.
- `scripts/test_opencode_v2_post_smoke.py` — partial-evidence refusal,
  pre-merge/post-merge ordering, consumer failure, and rollback routing.
- `plugins/auto-compact-at-threshold/index.js` — canonical V2
  `Plugin.define` implementation using `setup(ctx)`, V2 model/session domains,
  aborted event subscription, cleanup, and startup marker; never a V1 wrapper.
- `plugins/auto-compact-at-threshold/package.json` — exact
  `@opencode/plugin@2.1.4` runtime pin.
- `plugins/auto-compact-at-threshold/test.mjs` — threshold parsing, token
  accounting, subscription, compaction, cleanup, and startup-marker tests.

Add this separate Paragon PR scope (research read-only at baseline `7b36953`;
implementation occurs in a new isolated worktree at the then-approved ref):

- `opencode.json` — replace legacy `agent` with `agents`, replace deprecated
  `small_model` with native `agents.title.model`, and retain model bindings plus
  `.opencode/agents.md` instructions.
- `.opencode/agents/*.md` (ten files) — path-derived IDs; native ordered
  `permissions`; `shell`/`subagent`/`edit`; no `name`, `permission`, `bash`,
  `task`, or `write`; preserve every existing allow/deny decision and binding.
- `.opencode/agents.md` — V2 agent/config precedence, `subagent`/`agent`/
  `sessionID` language, and current debug command.
- `.opencode/package.json` and `.opencode/package-lock.json` — remove the unused
  V1 `@opencode-ai/plugin` pin; do not add a V2 plugin dependency unless Paragon
  actually gains a plugin.
- `scripts/check-opencode-v2.mjs` and `scripts/check-opencode-v2.test.mjs` —
  consumer-owned native-config/legacy-token gate with red fixtures.
- `.github/workflows/ci.yml` — run the consumer V2 checker in `verify`; keep the
  existing topology, permissions, pins, and product gates unchanged.

The earlier **Host actions** list is superseded by the versioned-switch design:
V2 package/config/plugin files land under `$HOME/.local/lib/opencode/` and the
versioned V2 `XDG_CONFIG_HOME`; the real V1 `~/.config/opencode` tree is backup
and rollback state, not an in-place migration target.

## Scope

### Included

- The canary, backup, rollback drill, and version policy above.
- Native V2 agent/config/install conversion, including the permission model.
- Dispatcher, wake, watchdog, guard, eval runner, and CI migration.
- The shared `scripts/opencode_v2.py` adapter and its offline tests.
- The dated reference rewrite, ADR-0014, roadmap row/detail, and active-doc
  tool-name/flag sweep.
- Host config/plugin audit and cutover actions required to run V2 as the
  default command.

### Excluded

- Editing consumer repositories, their wrappers, or their `opencode.json`.
  `check-consumer-bindings.py` only gains V2/legacy awareness.
- Writing a V1→V2 session-data migration or a dual-read compatibility layer.
  V2 owns the auto-migration; the backup is the rollback.
- New features or policy changes: Code Mode adoption, Todo/LSP/websearch
  enablement, model re-binding, lane-policy changes, or a run-log schema change.
- Fixing upstream V2 defects (#59287, #59251, #55278, #58176, #58335, #54311,
  #56276, #59259, #56349, #56218). The plan detects, mitigates, or blocks on
  them; it does not patch opencode.
- Deleting V1 sessions or the V1 binary before the backup and drills pass.
- Windows/macOS validation beyond the Linux canary.
- New workflow/job topology or new required checks. The new offline linters and
  suites join the existing `quality-gates` step; RM-042/RM-044 stay open unless
  this plan's own evidence satisfies them separately.
- Rewriting skills or docs unrelated to OpenCode-facing surfaces.

### Non-goals

- No V1/V2 compatibility layer in the scripts. The cutover is atomic; the
  previous release tag is the code rollback.
- No attempt to keep the V1 CLI working after cutover, no dual DB reads for
  production, and no in-place V2-to-V1 downgrade of a migrated DB.
- No adoption of V2-only capabilities beyond what the current contracts need
  (Code Mode, todo, LSP, websearch, `--fork`, title-based identity).
- No model re-binding, lane-policy change, or eval cost-policy change.
- No consumer migration in this branch; consumer wrappers are a follow-up with
  the updated checker.

### Revised 2026-10-27 — Option A scope boundary

**Included now:** the isolated Paragon consumer PR and its readiness/post-smoke
gates, the four operational scripts, the versioned V2 plugin/config root, the
owner-run drained cutover, and rollback of both session data and V1 agent files.
This explicitly supersedes the earlier exclusion/non-goal that deferred all
consumer migration. The two PRs are still independent and user-merged only after
post-smoke.

**Still excluded:** every other consumer; edits to Paragon's dirty primary
checkout before its user-initiated merge; any agent-run global cutover or global
V2 installation; any real session-DB write during design, implementation, or
pre-cutover review; in-place V2-to-V1 downgrade; and weakening the migration
residual into a silent acceptance. The cutover is the only step permitted to
write the real session DB, and only after the final drain backup.

## Schema / Type Impacts

No repo-owned database or generated type file exists. The contracts below are
vendor-owned or in-repo wire formats and change with this migration.

### OpenCode session DB (vendor-owned, one-way)

- V1 tables `session`, `message`, `part` become migration sources. V2 reads and
  writes `session_v2`, `session_message`, `session_inbox`, and `event`.
- First V2 boot auto-migrates V1 sessions. This is treated as **one-way**;
  rollback restores the C5 backup, not a live dual-read.
- `OPENCODE_DB` overrides the path; `opencode debug paths db` prints it. The
  repo adapter keeps `OPENCODE_DB_PATH` as the highest-precedence test override,
  then `OPENCODE_DB`, then the vendor location.
- `session_v2.time_idle` and `idle_outcome` become the completion/idleness
  signal. Exact columns and value enumerations are captured from the canary
  `PRAGMA table_info` and stored as a fixture; the adapter probes columns and
  degrades rather than hardcoding a guessed schema.
- `session_v2` model/token columns are parsed defensively; an unknown shape
  degrades to `?`, never a crash.

### Config and agent frontmatter

- Top-level config keys used by this repo: `agents`, `permissions`, `providers`,
  `mcp.servers`, `plugins`, `snapshots`, `media`, `skills`, `commands`,
  `references`, `agents.title.model`.
- Agent files: path-derived ID; `name` is ignored and removed; `model`,
  `description`, `mode`, `hidden` retained; `permissions` replaces
  `permission`; ordered rules use `shell`, `subagent`, `edit`,
  `external_directory`, `skill`, `execute`.
- The exact ordered-rule serialization is fixed by the C7 probe, not guessed.
  `OPENCODE_CONFIG_CONTENT` remains the injection mechanism; if C2/C7 shows it
  is unsupported, the adapter switches to a temp config file and the reference
  records the change.

### JSON event stream and run log

- V2 `opencode run --format json` events replace V1 part shapes. The adapter
  normalizes session ID, final text, tokens, cost, and tool calls.
- Tool vocabulary: `bash` → `shell`, `write`/`patch` → `edit`, `filePath` →
  `path`, `task` → `subagent` (with `agent` and `sessionID`), `skill` by id
  (path-derived skill name; there is no `--skill` flag). The run-log
  `kind=agent` schema is unchanged; only the attribution source moves from the
  V1 `session` row to the V2 session/API.
- Typed-eval predicate schema is unchanged (closed `action`/`artifact`/`text`
  keys). Values move to V2 names; the harness accepts V1 aliases for consumer
  manifests and logs the alias.

### API contract

- Typed `/api/*` replaces `/session/status` and `/event`:
  `/api/session/active`, `/api/session/{id}`, `/api/session/{id}/prompt`,
  `/api/session/{id}/agent`, `/api/session/{id}/log`, `/api/event`.
- Discovery/auth goes through `opencode api`; the fallback reads
  `~/.local/state/opencode/service.json` and speaks HTTP directly. A missing
  endpoint is a named deferral, never a crash.

### Revised 2026-10-27 — Observed V2 storage and config behavior

- V2 2.1.4 stores credentials in the selected `OPENCODE_DB` (`credential` and
  related tables). A fresh DB does not inherit V1 `auth.json`; the canary and
  cutover import the current key with `type: "api"` converted to `type: "key"`.
  The legacy `account.json` key was expired and is not authoritative. No secret
  export is written to disk or logged.
- The migration copy initially had no `session_v2`; after V2 initialization and
  smoke it held 2,077 rows (2,076 migrated source IDs plus one smoke). The 119
  source IDs not migrated all had V1 messages. The adapter must report counts
  and IDs without claiming full fidelity; cutover requires their classification
  or dated owner acceptance.
- `small_model` is deprecated compatibility input normalized to
  `agents.title.model = { providerID, model }`. `instructions` remains an array.
  Agent `permissions` and top-level `permissions` are ordered
  `{action, resource, effect}` arrays.
- Environment config documents through `OPENCODE_CONFIG_CONTENT` and
  `OPENCODE_CONFIG` appeared as sources but did not activate the marker agent.
  The dispatcher therefore uses a generated `opencode.jsonc` under a temporary
  `XDG_CONFIG_HOME`, with a fresh/stopped service, rather than either variable.
- V1 plugin functions and returned event hooks are not V2 contracts. V2 uses
  `@opencode/plugin@2.1.4`, `Plugin.define({id, setup})`, domain methods, and an
  aborted `ctx.event.subscribe()` loop. Session compaction is
  `ctx.session.compact({sessionID})`; cleanup is returned from `setup`.
- The versioned wrapper's `XDG_CONFIG_HOME` is part of the runtime contract.
  Rollback restores the V1 link and therefore the original V1 config/agent root;
  the dereferenced snapshot is the repair source if any V1 agent hash differs.

## Verification

### Hermetic suite (must stay green every phase)

- `python3 skills/authoring-skills/scripts/validate_skill.py --all`
- `python3 scripts/check_v2_config.py && python3 scripts/check_v2_config.py --baseline main`
- `python3 scripts/check_v2_surfaces.py`
- `python3 scripts/check_typed_evals.py --base main`
- `node scripts/verify.mjs`
- `node skills/managing-github-issues/evals/fixtures/unit.test.mjs`
- `node skills/refining-issue-acceptance/evals/fixtures/unit.test.mjs`
- `python3 skills/observing-runs/scripts/test_query.py`
- `python3 skills/observing-runs/scripts/test_log.py`
- `python3 skills/observing-runs/scripts/test_prune.py`
- `python3 skills/authoring-skills/scripts/test_runner.py`
- `python3 scripts/test_eval_report.py`
- `python3 scripts/test_typed_evals.py`
- `python3 scripts/test_registry.py`
- `python3 scripts/test_changed_files.py`
- `python3 scripts/test_quarantine.py`
- `python3 scripts/test_stall_timeout.py`
- `python3 scripts/test_eval_workflows.py`
- `python3 scripts/test_watch_agent.py`
- `python3 scripts/test_agent_dispatch.py`
- `python3 scripts/test_dispatch_agent.py`
- `python3 scripts/test_observe_completion.py`
- `python3 scripts/test_model_policy.py`
- `python3 scripts/test_v2_config.py`
- `python3 scripts/test_validate_delegated_result.py`
- `python3 scripts/test_delegated_result_contract.py`
- `python3 scripts/test_session_guard.py`
- `bash -n install.sh`
- `python3 -m yamllint -c .yamllint.yaml .github/workflows/`
- `python3 scripts/check_roadmap_verbatim.py`

### Live drills (Linux host, V2, credentials in env; evidence under `.scratch/`)

- **D1 — dispatch all reachable agent classes.** One trivial dispatch per
  profile class in `scripts/dispatch-profiles.json` that a persona maps to
  (`architect`, `planner`, `implementer`, `reviewer`, `council`, `test`) plus
  one default-profile run: exit 0, one `kind=agent` run-log record each, and
  the printed `model=` equals the agent's `model:` value. `meta-loop` has no
  mapped persona today; record that gap rather than inventing one.
- **D2 — external-directory negative/positive.** A planner prompt that reads a
  file outside the grant exits non-zero with
  `permission denied: external_directory <path>`; the same dispatch with
  `--allow-dirs` exits 0.
- **D3 — watchdog verdicts.** `python3 scripts/watch_agent.py --session <live>
  --watch 5` shows OK during generation and DONE after; a synthetic stale
  heartbeat with no DB/API activity shows STALLED. All three exit codes match
  the documented map.
- **D4 — guard wave.** `python3 scripts/session_guard.py --root <wave> --once
  --json` scans two children, reports no false abort, and a denial fixture
  reports `permission-auto-reject`.
- **D5 — wake, no ghost turn.** Detached child with `--wake-to <session>` and
  `--wake-agent <agent>`: `WAKE success` within 5 minutes; the orchestrator
  session ID is unchanged; exactly one turn is appended; no new session row.
- **D6 — eval canary.** The two commands in AC27 both exit 0 with `PASS`.
- **D7 — model doctor.** `python3 scripts/model-liveness-check.py` exits 0 and
  `python3 scripts/check-consumer-bindings.py .` exits 0.
- **D8 — rollback rehearsal.** In a scratch worktree at the previous release:
  reinstall V1, restore the C5 DB copy, run a V1 session read, then reinstall
  V2. The documented runbook matches what was executed.

### Cutover and merge

1. All hermetic suites green on the branch.
2. Host cutover: `npm uninstall --global opencode-ai` then
   `npm install --global @opencode/cli@2.1.4`; verify `opencode --version`
   prints `2.1.4`, then run D1–D7 against the default command.
3. Any live-drill failure: `npm uninstall --global @opencode/cli` +
   `npm install --global opencode-ai@1.19.4`, restore the C5 backup, abort the
   merge, and report the gate evidence.
4. Land ADR-0014, the roadmap row/detail, the doc sweep, and the plan
   retirement in the same PR; merge only with the full suite and drills green.

### Revised 2026-10-27 — Option A execution contract

Add the four script suites to the hermetic list and run these commands from the
framework branch worktree (never from the primary checkout on `main`):

```bash
python3 scripts/test_opencode_v2_canary.py
python3 scripts/test_opencode_v2_consumer.py
python3 scripts/test_opencode_v2_cutover.py
python3 scripts/test_opencode_v2_post_smoke.py
node --test plugins/auto-compact-at-threshold/test.mjs
python3 scripts/opencode_v2_canary.py --all
```

The canary stops at the first failed gate. Its C5 backup and scratch-path
assertions precede every V2 invocation; C4 and migration artifacts are separate.
The migration residual must be classified or explicitly accepted by the owner
before runtime cutover.

For the isolated Paragon worktree:

```bash
python3 scripts/check-consumer-bindings.py <paragon-worktree>
python3 scripts/opencode_v2_consumer.py check <paragon-worktree>
python3 scripts/opencode_v2_consumer.py ready <paragon-worktree>
node <paragon-worktree>/scripts/check-opencode-v2.mjs
node --test <paragon-worktree>/scripts/check-opencode-v2.test.mjs
```

Run Paragon's own gates in that worktree after dependency installation:

```bash
pnpm typecheck
pnpm lint
pnpm test
pnpm db:types
git diff --exit-code -- packages/shared/src/
```

After both PRs are reviewed and merge-ready, the implementer stops. The owner
closes every OpenCode/session/dispatch process and opens a normal terminal. No
architect, implementer, reviewer, or consumer agent executes the next command.
From the framework branch worktree, the owner runs:

```bash
python3 scripts/opencode_v2_cutover.py --preflight \
  --framework <framework-worktree> --consumer <paragon-worktree>
python3 scripts/opencode_v2_cutover.py --execute --drain-acknowledged \
  --framework <framework-worktree> --consumer <paragon-worktree>
python3 scripts/opencode_v2_post_smoke.py \
  --framework <framework-worktree> --consumer <paragon-worktree>
```

The execute step must re-run preflight, take the final drained V1 backup, and
write the switch manifest before touching the default link. It must not merge a
PR. Only a passing post-smoke allows the owner to squash-merge the framework and
Paragon PRs. Then run:

```bash
python3 scripts/opencode_v2_post_smoke.py --post-merge \
  --framework <framework-main> --consumer <paragon-main>
```

On any pre-merge runtime failure, the owner runs rollback from the same normal
terminal, with all V2 sessions closed:

```bash
python3 scripts/opencode_v2_cutover.py --rollback --manifest <manifest>
python3 scripts/opencode_v2_post_smoke.py --rollback-check --manifest <manifest>
```

Rollback-check must print V1 `1.19.4`, intact V1 agent/config/plugin hashes, an
`ok` DB integrity result, and a successful V1 session-list read. After a merged
change, runtime rollback also requires explicit revert PRs; the script never
rewrites either primary checkout on its own.

## Open Questions

1. **Shared service or `--standalone` for dispatch?** Proposed default: shared
   service for local dispatch (preserves wake through the orchestrator's own
   server and nested visibility), `--standalone` for CI and hermetic one-shots,
   and `session.interrupt` on timeout. Justification: the wake path needs a
   shared server; standalone removes it.
2. **API-first or DB-first watchdog?** Proposed default: API-first
   (`/api/session/{id}` + `/api/session/{id}/log`), read-only DB fallback for
   offline tests and an unreachable service. Justification: the API is the
   sanctioned liveness surface; the DB fallback keeps hermetic parity.
3. **Native V2 agents or V1 normalization?** Proposed default: native V2 in
   all 17 files. Justification: the repo is the reference implementation;
   normalization hides drift and the brief names native as the destination.
4. **Fallback version if 2.1.4 fails the canary?** Proposed default: the
   highest `2.x` that passes C1–C6; do not assume `2.0.32` (named in #59287).
   If none passes, stay on V1 and report. Justification: a hang gate is not
   negotiable.
5. **Does any skill need LSP, Todo, or websearch?** Proposed default: no. The
   audit in C8 records the negative; no workaround or enablement is added.
   Justification: no skill body invokes them; adding them would be scope creep.
6. **Roadmap ID collision.** Proposed default: take the next free ID at
   implementation time; `RM-068` if the untracked security plan lands `RM-067`
   first, otherwise `RM-067`. Justification: duplicate IDs break the roadmap
   contract.
7. **Host cutover timing and backup retention.** Proposed default: cut over
   after the hermetic suite is green and before the live drills; retain the V1
   backup and the V1 install instructions for 14 days, then delete them with a
   dated note. Justification: the DB migration is one-way; the window must
   cover a failed live drill.
8. **No matching stack reference.** `designing-architecture` ships
   `vue-supabase` and `nextjs-supabase` references; neither applies to this
   Python/Node tooling repo. Proposed default: proceed generically and use the
   repo's own CI suites and `reference/opencode-integration.md` as the stack
   contract. Justification: forcing an app-stack reference would invent
   schema/RLS work that does not exist here.

9. **Migration fidelity residual.** Proposed default: classify the 119 missing
   source sessions during implementation and block cutover until their exclusion
   is explained or the owner records explicit acceptance of the lost history.
   Justification: `session_v2` population passed, but 2,076 of 2,195 source
   sessions is not proof of lossless migration.
10. **Auto-compaction disposition.** Proposed default: ship the fully tested V2
    plugin in the versioned config; allow the dated static-disable fallback only
    with explicit owner approval. Justification: the V1 export fails and a
    wrapper silently loses the threshold behavior.
11. **Paragon worktree baseline.** Proposed default: branch from the latest
    owner-approved committed `main` SHA, not from the dirty primary working
    tree; leave all unrelated uncommitted owner changes untouched. Justification:
    research found `ROADMAP.md`, docs, plans, and legal assets already modified
    or untracked in the primary checkout.

## History

- 2026-10-26 — initial design pass from the OpenCode V2 migration architect
  brief. Canary/rollback gates, six workstreams, 31 acceptance criteria, and the
  version/security policies recorded. UX consult skipped: no user-facing
  UI. No matching stack reference for this Python/Node tooling repo; planned
  generically.
- 2026-10-27 — Option A revision after C1–C8 canary evidence: C5-first
  isolation, real-config C3 with DB-scoped credential import, fresh-DB 10/10
  stability, separate copy-only migration rehearsal and fidelity residual, V1
  rollback proof, native config/plugin findings, and capability audit. Added
  drain and Paragon-readiness gates, four fail-closed operational scripts, a
  versioned one-link runtime/config switch, V1 agent-file rollback, and
  pre-merge/post-merge smoke ordering; acceptance criteria now total 41. UX
  consult skipped again: no user-facing UI. No global cutover or real DB write
  performed.
- 2026-10-27 — owner approved the plan and its recommended defaults: classify
  the 119-session residual before cutover, fully port auto-compaction unless the
  owner later approves a dated disable, and use an isolated Paragon worktree
  from the latest approved committed SHA. Handoff is to a fresh implementer;
  the architect never runs the final cutover.


## History

- 2026-10-27 — implementation pass (Option A, all 41 ACs). Added the shared
  `scripts/opencode_v2.py` adapter, the four operational scripts + hermetic
  suites, the V2 auto-compaction plugin + Node tests, native V2 conversion of
  all 17 framework agents and the 10 Paragon wrappers, the V2 dispatcher /
  wake / watchdog / guard / eval-runner / CI migration, the offline
  `check_v2_config.py` + `check_v2_surfaces.py` linters, ADR-0014, the
  reference rewrite, the active-doc sweep, and the RM-067 row/detail.
  Verification (framework worktree): the full hermetic suite is green
  (`validate_skill --all`, both v2 linters, `verify.mjs`, all `test_*.py`
  including the four operational suites, `node --test plugins/...`, yamllint,
  roadmap-verbatim); the isolated canary `--all` (C5→C1→C2→C3→C4→C6→C7→C8→
  migration) passes with C5-first ordering and scratch-only DB writes. Paragon
  worktree at `7b36953`: `check-consumer-bindings.py`, `opencode_v2_consumer.py
  check`, `check-opencode-v2.mjs` + its test, `pnpm typecheck`, `pnpm lint`,
  `pnpm test` (199/199), and `pnpm db:types` (no source diff) pass.
  Migration residual classification: the 119-session rehearsal residual is a
  truncated, resumable id-ordered backfill (`kv.migration.v1-v2` cursor; every
  missing id is below the cursor, every source id above it is migrated), not
  data loss. The canary gate now reports the residual and requires
  classification/owner acceptance before cutover.
  No global V2 install, no global cutover, no real session-DB write, and no PR
  merge occurred. The two PRs are open/unmerged; the owner runs the drained
  cutover + post-smoke from a normal terminal.

### Follow-ups

- The owner still owns the drain/cutover/post-smoke/merge gate; the framework
  and Paragon PRs must stay unmerged until it passes.
- The canary's C6/C7 gates now execute the V1 rollback read and the isolated
  config/plugin probe; re-record their live evidence on the owner's final
  pre-cutover run.
- The V2 migration backfill is resumable; a repeated boot continues from the
  cursor. Re-run the migration gate after the final drain backup and record
  the final residual (or the owner's dated acceptance).
