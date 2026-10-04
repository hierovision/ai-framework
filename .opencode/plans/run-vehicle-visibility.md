---
slug: run-vehicle-visibility
title: Run-vehicle live visibility — stream tees, heartbeats, session-resolved attribution, permission grants
status: approved
created: 2026-10-03
revised: [2026-10-03, 2026-10-03, 2026-10-03, 2026-10-03]
related: [rm-022, go-first-model-bindings]
---

# Plan: run-vehicle-visibility

## Goal / Approach

Goal: every `dispatch_agent.py` run-vehicle dispatch exposes progress live —
raw session events and a canonical heartbeat — from the first minute to the
terminal line, and its attribution names the model that actually ran — without
changing the delegated-result contract.

Today `run_opencode` buffers stdout/stderr in memory and `main()` writes
nothing until completion, so the operator sees only `session_id=` at start
and `run_log=/result=` at the end; the opencode session DB via
`watch_agent.py --session` is the only live channel, and heartbeat files
exist only if the orchestrator hand-writes the protocol into the prompt.
Three optional flags close both gaps:

- `--stream-out FILE` — tee the stdout `--format json` event stream, one raw
  NDJSON line per event, flushed per line (live `tail -f`, `jq`-friendly).
- `--stream-err FILE` — tee stderr the same way (provider/server
  diagnostics).
- `--heartbeat FILE` — dispatcher-managed envelope plus prompt injection. The
  dispatcher writes the `# progress:` header and `START` before launch and
  appends exactly one terminal line (`DONE ok` / `BLOCKED <detail>`) on every
  outcome branch; the injected prompt block instructs the agent to append
  `STEP` / `CALL begin|end` / `POLL` lines per
  `reference/subagent-supervision.md` §2.

Semantics: a fresh dispatch truncates the target files; a `--session` resume
appends (history accumulates). Open failures exit 2 with a named error before
opencode launches. Flags stay opt-in; the supervision reference makes
`--stream-out` + `--heartbeat` mandatory-by-contract for dispatches expected
to exceed ~10 min.

Approach: tee lines inside the existing reader threads (the in-memory `raw`
accumulation is unchanged, so contract validation is untouched); add a small
heartbeat writer around `main()`'s existing outcome branches; inject a fixed
block that names the absolute heartbeat path and cites the canonical protocol
section rather than restating it.

Folded in 2026-10-03 — attribution bug found in a consuming repo
(paragon-learning-network): `resolve_agent_model` (dispatch_agent.py:145)
reads the framework checkout's `agents/<name>.md`, while opencode resolves the
project wrapper under the consumer's `.opencode/agents/`. The run behaved
correctly but the printed header and the `kind=agent` record named
`opencode/nemotron-3-ultra-free` for a Go run — a false record against
paragon's no-free-models rule. Fix: resolve the attribution model from the
finished session row (`session.model` blob) through the watcher's existing
reader; the frontmatter binding stays as the pre-run display value (relabeled
`binding=`) and as the fallback when the DB is unavailable. The event stream
itself carries no model field (probed against the 2026-10-01 run streams), so
the session DB is the ground truth. Do not replicate opencode's
agent-resolution precedence.

Folded in 2026-10-03 (second incident) — two architect dispatches died with
`failure: empty result` ~45 s in (`ses_efd9815fdffepLG4xeD2n3d6xS`,
glm-5.3-flash; `ses_efd8a001dffePR1M6prjSgCrcL`, deepseek-v4.1-flash). Session
exports show the cause: the briefs read sibling consumer repos outside the
working directory; opencode's `external_directory` permission auto-rejects
non-interactively, the turn terminates, and `opencode run` exits 0 with no
final text. The dispatcher grants no external paths and reports the death as
an uninformative `empty result`. Fix: `--allow-dirs` (repeatable) grants
declared external paths least-privilege via the permission config, and
denial-aware classification names the denied tool/command instead of
`empty result`.

No stack reference applies — framework-internal Python tooling.

## Practical Result (human view)

For: the framework owner — operator of long dispatches, including from
consumer repos.

- **Before** — a dispatch is a black box. The log shows one `session_id=`
  line and then silence until it ends; live progress means polling the
  opencode DB with `watch_agent.py`. In a consumer repo the attribution can
  also lie: on the 2026-10-03 paragon exercise the header and the run-log
  record said `opencode/nemotron-3-ultra-free` while the run used paragon's
  Go wrapper binding. Failures are opaque: two architect dispatches died
  "empty result" and only a manual session export revealed they were
  permission-denied cross-repo reads, not model failures.
- **After** — one launch with the flags, then watch plain files: `tail -f`
  the raw event stream and the heartbeat while it runs; when it ends, the
  record names the model that actually ran. Briefs that read sibling repos
  pass `--allow-dirs` and work; a denial surfaces as
  `permission denied: <command>` instead of silence. Exact commands in
  Verification.
- **Value** — attribution you can act on (a false free-model record is a
  false compliance signal in consumer repos), dispatch failures classified
  at the point of failure instead of by forensics, and confidence to run
  dispatches in parallel.
- **How you judge it** — on the next consumer dispatch: event lines appear
  in the stream file within a minute of launch; the heartbeat has STEP/CALL
  lines while it runs and one terminal line after; the run-log record's
  `model` equals the project wrapper binding; and a cross-repo brief with
  `--allow-dirs` completes instead of exiting empty.
- **What it asks of you** — nothing ongoing: pass the flags on long
  dispatches and `--allow-dirs` when the brief reaches outside the workdir
  (or skip them; behavior without flags is unchanged except the corrected
  attribution). No approvals, services, or maintenance.

## Acceptance Criteria

1. **The stream tee is live, not end-of-run.** While a dispatch is still
   running, `--stream-out FILE` already contains each stdout event line
   emitted so far; at exit it contains every line exactly once. Verifier:
   new hermetic case `test_stream_out_live_and_complete` in
   `scripts/test_dispatch_agent.py` (stub emits 3 NDJSON lines with ~0.5 s
   gaps; the test observes ≥1 line while the child is alive, 3 after);
   `python3 scripts/test_dispatch_agent.py` exits 0.

2. **Stderr tee.** `--stream-err FILE` captures stderr live with the same
   completeness. Verifier: `test_stream_err_live_and_complete` (stub writes
   2 stderr lines).

3. **Fresh vs resume semantics.** A fresh dispatch truncates the target
   files; `--session <id>` resume appends. Verifier:
   `test_stream_files_fresh_vs_resume` (two runs on one path; line counts
   asserted).

4. **Heartbeat envelope.** With `--heartbeat FILE`, the file contains the
   `# progress:` header and a `START` line before any session event, and
   exactly one terminal line after every outcome branch: `DONE ok` on
   success; `BLOCKED <detail>` on contract failure, non-zero exit, timeout,
   or result-write failure. Verifier: `test_heartbeat_envelope_success` and
   `test_heartbeat_terminal_blocked` (contract-failure + timeout cases).

5. **Heartbeat injection.** With `--heartbeat FILE`, the prompt handed to
   opencode carries the canonical block: the absolute heartbeat path, a
   pointer to `reference/subagent-supervision.md` §2, the STEP/CALL/POLL
   requirement, and the no-single-call-over-180 s rule. Verifier: stub dumps
   its prompt argument (`STUB_DUMP_PROMPT`);
   `test_heartbeat_prompt_injection` asserts the block and the reference
   path.

6. **Preflight failures are clean.** An unopenable stream/heartbeat target
   exits 2 with a named stderr message before opencode is launched (no
   session created). Verifier:
   `test_stream_open_failure_exits_2_before_launch` (target path under an
   existing file).

7. **No behavior change without the flags.** All existing
   `test_dispatch_agent.py` cases pass unmodified and no files are created
   when the flags are absent. Verifier: `python3
   scripts/test_dispatch_agent.py` exits 0.

8. **Contract docs carry the recipe.** `reference/subagent-supervision.md`
   documents the flag trio, the dispatcher-vs-subagent line ownership, and
   the operator tail/watch recipe; the injected block cites that section
   (dispatcher never re-defines the protocol). `reference/agent-teams.md`'s
   run-vehicle bullet names the flags and its §Attribution states the
   record's model is session-resolved. Verifier: read-through acceptance in
   the PR plus the grep assertion in AC5's test.

9. **Operator loop verified live.** One real smoke dispatch on a Go model
   with all three flags is tailed while running (events + heartbeat), and
   `python3 scripts/watch_agent.py --progress FILE --session <id> --json`
   shows the heartbeat and session; completion still writes the result file
   and exactly one `kind=agent` run-log record. Verifier: the smoke run's
   session id, file paths, and watch JSON recorded in the plan History.

10. **Attribution names the run's resolved model.** For a dispatch into a
    consumer repo (`--dir <consumer>` with a project wrapper), the pre-run
    line labels the frontmatter value as `binding=`, and the completion
    output plus the `kind=agent` record use the model resolved from the
    session row (`session.model` blob, read-only through the watcher's
    reader) — a paragon-style Go run is never recorded as the framework's
    free binding. Verifier: hermetic
    `test_record_model_from_session_db` — the stub emits `ses_stub_valid`;
    a temp SQLite fixture (schema per `watch_agent.find_session`) carries
    that session row with a Go model blob; `OPENCODE_DB_PATH` points the
    dispatcher at it; asserts the record `model` and the printed `model=`
    line; `python3 scripts/test_dispatch_agent.py` exits 0.

11. **DB-unavailable fallback.** When the session row cannot be read (no DB,
    missing row, unreadable blob), the dispatch still succeeds and the
    record falls back to the frontmatter binding; the `binding=` vs `model=`
    labels make the source visible. Verifier:
    `test_model_fallback_without_db`, plus the existing
    `test_valid_dispatch_records_attribution` (no matching row) staying
    green.

12. **External-path grants.** `--allow-dirs PATH` (repeatable — one flag per
    path; pass it several times to grant several directories) adds
    `<absolute-path>/**` to opencode's `permission.external_directory`
    allow-map for the dispatched run, merged with any caller-supplied
    `OPENCODE_CONFIG_CONTENT` (caller settings win on conflict); each path
    is validated to exist before launch (exit 2 otherwise); without the flag
    behavior is unchanged. Verifier: hermetic
    `test_allow_dir_grants_external_permission` — stub dumps its environment;
    the test asserts the emitted permission map contains the resolved path
    and that a non-existent path exits 2 before a session is created.

13. **Denial-aware classification.** When the captured stream's final
    message carries a tool part with `status=error` and the
    permission-rejection text (or captured stderr carries
    `external_directory ... auto-reject`), the dispatch detail names it —
    `permission denied: <tool> <command-or-path>` — instead of
    `empty result`, and the run-log record carries that detail. Verifier:
    hermetic `test_permission_denial_classification` (stub emits a denied
    tool part and no text); assert outcome `failure` and the denied detail.

14. **Docs require grants for cross-boundary briefs.**
    `reference/subagent-supervision.md` §Dispatch vehicles and §1 state that
    any brief whose work reaches outside the working directory must pass
    `--allow-dirs`, citing this two-session incident;
    `reference/agent-teams.md`'s run-vehicle bullet names the flag alongside
    the visibility flags. Verifier: read-through acceptance plus the grep
    assertion in AC13's test (the classifier detail names
    `external_directory`).

## Files to Modify

- `scripts/dispatch_agent.py` — add `--stream-out`, `--stream-err`,
  `--heartbeat`; preflight opens with parent-dir creation; tee writes in the
  two reader threads; heartbeat header/START before launch and terminal
  `DONE`/`BLOCKED` in every outcome branch; prompt-block injection. Resolve
  the attribution model from the session DB after the run, print
  `binding=` pre-run and `model=` at completion, fall back to the binding.
  Add `--allow-dirs` permission grants and permission-denial classification
  (AC12–AC13).
- `scripts/test_dispatch_agent.py` — new stub modes (paced stream, stderr
  writes, prompt dump, denied tool part, env dump) and the cases named in
  ACs 1–14, including the temp SQLite session-row fixture.
- `scripts/watch_agent.py` — honor an `OPENCODE_DB_PATH` override at call
  time (default `~/.local/share/opencode/opencode.db` unchanged) so the
  dispatcher and hermetic tests share one reader; no verdict or query
  changes.
- `reference/subagent-supervision.md` — §Dispatch vehicles / §1 / §2 / §4:
  flag trio, `--allow-dirs` requirement for cross-boundary briefs, line
  ownership (dispatcher: header/START/terminal; subagent: STEP/CALL/POLL),
  canonical injected block, operator recipe.
- `reference/agent-teams.md` — run-vehicle bullet in §Lane policy names the
  visibility and grant flags; §Attribution states the record's model is the
  session-resolved model (frontmatter binding is display + fallback only).
- `reference/opencode-integration.md` — note the read-only session-model
  read, the DB-path override, and the external-directory permission model.
- `.opencode/plans/run-vehicle-visibility.md` — this plan.

## Scope

**Included**
- The three flags and their exact semantics (live tee, fresh/resume,
  envelope, injection, preflight failure).
- The attribution fix: session-resolved model for the completion output and
  the `kind=agent` record, with frontmatter fallback (consumer-repo repro).
- External-path permission grants (`--allow-dirs`) and permission-denial
  classification (the two-architect incident).
- Hermetic tests for every AC and the reference-doc updates.
- One live smoke in the framework repo, one consumer-dir smoke against
  paragon, and one cross-repo read dispatch proving `--allow-dirs` (all
  recorded in History).

**Excluded**
- Retrofitting the dispatches already running today (impossible; their live
  view remains `watch_agent.py --session` / `opencode export`).
- Replicating opencode's agent-resolution precedence (project wrapper vs
  global vs config) in the dispatcher — the session row is the ground truth.
- `watch_agent.py` verdict/query changes (only the test-only DB-path
  override).
- A `--supervise DIR` umbrella or default-on streaming (Open Question 1).
- Blanket `--auto` permission approval or implicit sibling-repo access —
  grants are declared per path, least privilege (Open Question 6).
- Adding `--print-logs` to the dispatch argv (stderr tee captures what
  exists; the denial is client-visible in the stream; deeper server logs are
  a separate change).
- In-session Task visibility (different vehicle) and auto kill/resume on
  watchdog verdicts (RM-024 territory).
- The plan-format "practical result" directive — a separate process change
  in the designing-architecture contract, tracked outside this plan (this
  plan's `## Practical Result` is its first application).

## Schema / Type Impacts

None. No run-log schema change: the dispatcher still emits exactly one
`kind=agent` record per dispatch. The session-DB read is read-only and adds
no tables or columns. Stream and heartbeat files are line-oriented text
artifacts at caller-chosen paths (normally under `.scratch/`, gitignored).

## Verification

```markdown
- python3 scripts/test_dispatch_agent.py          # AC1–AC14
- python3 scripts/test_watch_agent.py             # heartbeat parsing unchanged
- python3 skills/authoring-skills/scripts/validate_skill.py --all
- python3 scripts/check_typed_evals.py --base main
```

Live smoke (AC9), Go lane, artifacts under `.scratch/dispatch/`:

```markdown
- python3 scripts/dispatch_agent.py --agent architect --model opencode-go/glm-5.3-flash \
    --prompt-file .scratch/dispatch/smoke.md \
    --stream-out .scratch/dispatch/smoke.events.jsonl \
    --stream-err .scratch/dispatch/smoke.stderr.log \
    --heartbeat .scratch/dispatch/smoke.progress.log \
    --contract design-consult --timeout 600
- tail -f .scratch/dispatch/smoke.events.jsonl
- tail -f .scratch/dispatch/smoke.progress.log
- python3 scripts/watch_agent.py --progress .scratch/dispatch/smoke.progress.log --session <id> --json
```

Consumer-repro smoke (AC10), framework dispatcher into paragon's project
wrapper:

```markdown
- python3 scripts/dispatch_agent.py --agent architect --dir ../paragon-learning-network \
    --prompt-file .scratch/dispatch/smoke-consumer.md \
    --stream-out .scratch/dispatch/smoke-consumer.events.jsonl \
    --heartbeat .scratch/dispatch/smoke-consumer.progress.log \
    --contract design-consult --timeout 600
- assert the printed model= and the run-log record equal paragon's project
  wrapper binding, not opencode/nemotron-3-ultra-free
```

Cross-boundary proof (AC12–AC13), the exact failure that killed the two
architect sessions — a brief that reads sibling repos:

```markdown
- python3 scripts/dispatch_agent.py --agent architect \
    --allow-dirs ../paragon-learning-network --allow-dirs ../marvin-slack \
    --prompt-file .scratch/dispatch/smoke-cross-repo.md \
    --stream-out .scratch/dispatch/smoke-cross.events.jsonl \
    --heartbeat .scratch/dispatch/smoke-cross.progress.log \
    --contract design-consult --timeout 600
- assert it completes with a valid result (not "empty result"); and a second
  run without --allow-dirs records "permission denied: ..." instead
```

## Open Questions

1. **Interface shape.** Proposed default: three explicit flags as specified.
   Alternative: a `--supervise DIR` umbrella deriving
   `<task>.events.jsonl` / `.stderr.log` / `.progress.log` from the same
   primitives. Explicit flags ship first; revisit if call sites prove
   error-prone.
2. **Heartbeat ownership.** Proposed default: dispatcher envelope + prompt
   injection (mechanical, no orchestrator discipline required).
   Alternative: documentation-only convention (every prompt must carry the
   block).
3. **Event-file growth.** Proposed default: no pruning this pass; files sit
   under `.scratch/` (gitignored) and are disposable. Revisit with a
   retention rule if heavy dispatches produce multi-hundred-MB streams.
4. **stderr depth.** Proposed default: capture stderr as produced (no
   `--print-logs`); add it in a follow-up only if the smoke run shows too
   little diagnostic signal.
5. **Pre-run header label.** Proposed default: pre-run prints
   `binding=<frontmatter>` (honest label) and completion prints
   `model=<session-resolved>`; the record uses the resolved value.
   Alternative: replicate opencode's resolution order to print `model=`
   pre-run — rejected as fragile (Excluded).
6. **Grant scope.** Proposed default: explicit `--allow-dirs` per dispatch
   (least privilege), no implicit sibling-repo access. Alternative:
   auto-allow a configured root (e.g. `~/repos/**`) for orchestrator
   convenience — rejected for now; revisit if call sites routinely need
   many paths.

## History

- 2026-10-03 — delta-nit fold (user-authorized: bound the unexpected-exception
  heartbeat detail from the delta verification
  `.scratch/dispatch/review-delta-run-vehicle-visibility.result.md` on
  `097480c`; folded into PR #94). Files: `scripts/dispatch_agent.py`,
  `scripts/test_dispatch_agent.py`, this plan. RED-first (the new assertion
  failed for the right reason against pre-fix code, then green):

  | Finding | Fix (file:line) | Verification evidence |
  |---|---|---|
  | D-nit | cap the unexpected-error detail at the outcome-branch convention, 200 (`scripts/dispatch_agent.py:575–579`) | `test_heartbeat_terminal_on_unexpected_write_failure` part (c): RED = `AssertionError: 500` (unbounded 500-char detail in the heartbeat); GREEN = detail after `unexpected dispatch error: ` ≤ 200, rc 3 |

  - **Verification (hermetic, exit 0 each)** —
    `python3 scripts/test_dispatch_agent.py` (19 cases),
    `python3 scripts/test_watch_agent.py` (11 cases),
    `python3 skills/authoring-skills/scripts/validate_skill.py --all`,
    `python3 scripts/check_typed_evals.py --base main`.
  - **Scope** — `agents/reviewer.md`, workflows, and the uncommitted
    `.opencode/plans/go-first-model-bindings.md` worktree change untouched.

- 2026-10-03 — review-fix pass (user-authorized: resolve ALL four minors +
  three nits from PR #94's `approve-with-nits` on commit `52ff1c4`; on top of
  `af0174e`). Files: `scripts/dispatch_agent.py`,
  `scripts/test_dispatch_agent.py`, `reference/subagent-supervision.md`,
  `reference/opencode-integration.md`, this plan. RED-first per finding
  (the new assertion failed for the right reason against pre-fix code, then
  green):

  | Finding | Fix (file:line) | Verification evidence |
  |---|---|---|
  | M1 | guard outcome→result write, terminal in `finally` (`scripts/dispatch_agent.py:532–581`); broad `except Exception` around `log_record` (`:602–603`) | `test_heartbeat_terminal_on_unexpected_write_failure`: RED = `UnicodeEncodeError` traceback + no terminal; GREEN = one `BLOCKED unexpected dispatch error` line, rc 3; record-write `OSError` → `run-log record failed` warning, `DONE ok`, rc 0 unchanged |
  | M2 | warn to stderr on unparsable caller config + docstring note (`scripts/dispatch_agent.py:302–316`) | `test_permission_config_warns_on_malformed_caller_env`: RED = no warning; GREEN = `OPENCODE_CONFIG_CONTENT` warning, grant still merged, rc 0 |
  | M3 | `os.path.isdir` + named error (`scripts/dispatch_agent.py:472–475`) | `test_allow_dir_grants_external_permission` file case: RED = rc 0; GREEN = rc 2, `directory` named, no session |
  | M4 | inject block only when not `--session` (`scripts/dispatch_agent.py:501–504`); rule in `reference/subagent-supervision.md:22–31` | `test_heartbeat_prompt_injection` resume case: RED = block re-injected; GREEN = block absent, envelope `START` still written |
  | N1 | use `HEARTBEAT_PROTOCOL_REF` in `heartbeat_prompt_block` (`scripts/dispatch_agent.py:258`) | inspection; existing block test still green |
  | N2 | single blank line before `## Permission config` (`reference/opencode-integration.md:51`) | inspection |
  | N3 | broaden `ANSI_RE` to CSI non-SGR / OSC / two-char (`scripts/dispatch_agent.py:91–95`) | `test_permission_denial_classification`: RED = `\x1b…` in detail; GREEN = stripped |

  - **Verification (hermetic, exit 0 each)** —
    `python3 scripts/test_dispatch_agent.py` (19 cases; +2),
    `python3 scripts/test_watch_agent.py` (11 cases),
    `python3 skills/authoring-skills/scripts/validate_skill.py --all`,
    `python3 scripts/check_typed_evals.py --base main`.
  - **Coverage gate** — no mislayered tests and no high-value gap beyond the
    findings; M3/M4/N3 extend the existing cases, M1/M2 add one each.
  - **Scope** — `agents/reviewer.md`, workflows, and the uncommitted
    `.opencode/plans/go-first-model-bindings.md` worktree change untouched.
- 2026-10-03 — review + scope widening (user-authorized): `reviewing-code`
  pass on PR #94 → verdict `approve-with-nits` (no blockers/majors; four
  `consider` minors: heartbeat terminal-write guard, unparsable-config
  diagnostic, `--allow-dirs` isdir check, resume block accumulation).
  Absorbed: `agents/reviewer.md` — its blanket `edit`/`write: deny`
  contradicted `reviewing-code` Step 7 / `docs/CONCEPTS.md` ("writes only
  REVIEW.md"); `edit` is now path-scoped (`*` deny, `REVIEW.md` allow),
  validated live (reviewer wrote REVIEW.md in a smoke dispatch).
- 2026-10-03 — implemented (branch `feat/run-vehicle-visibility`). Delivered
  AC1–AC13 plus the AC8/AC14 doc updates in `scripts/dispatch_agent.py`,
  `scripts/test_dispatch_agent.py`, `scripts/watch_agent.py`,
  `reference/subagent-supervision.md`, `reference/agent-teams.md`, and
  `reference/opencode-integration.md`; no `agents/*.md` binding, workflow, or
  other-plan change (the Go-first flip stays queued).
  - **RED evidence** — new AC tests authored before the implementation was
    finalized were run against the pre-change `dispatch_agent.py` /
    `watch_agent.py` (stashed): `test_stream_out_live_and_complete`,
    `test_stream_err_live_and_complete`, `test_stream_files_fresh_vs_resume`,
    `test_heartbeat_envelope_success`, `test_heartbeat_terminal_blocked`,
    `test_heartbeat_prompt_injection`, `test_stream_open_failure_exits_2_before_launch`,
    `test_record_model_from_session_db`, `test_permission_denial_classification`,
    and `test_allow_dir_grants_external_permission` all failed for the right
    reason (unrecognized flags / no live tee / `empty result` / free model);
    restored, then green.
  - **Verification (hermetic, exit 0 each)** —
    `python3 scripts/test_dispatch_agent.py` (17 cases),
    `python3 scripts/test_watch_agent.py` (11 cases),
    `python3 skills/authoring-skills/scripts/validate_skill.py --all`,
    `python3 scripts/check_typed_evals.py --base main`.
  - **Live smokes** (artifacts under `.scratch/dispatch/`, gitignored):
    - AC9 framework Go: session `ses_efb45d163ffem7v4j7JDt0bGcT`;
      `smoke.events.jsonl` (14 lines) + `smoke.progress.log`
      (header/START + injected STEP/CALL lines + `DONE ok`);
      `model=opencode-go/glm-5.3-flash`; `run_log=` + result written;
      `watch_agent.py --session … --json` → verdict `OK`.
    - AC10 consumer repro (`--dir ../paragon-learning-network`, no `--model`):
      session `ses_efb451244fferb0VqVjm8cmrPi`; pre-run
      `binding=opencode/nemotron-3-ultra-free` (honest frontmatter label) but
      `model=opencode-go/glm-5.3-flash` at completion and in the sole
      `kind=agent` record — paragon's project-wrapper binding, never the
      framework free binding.
    - AC12 grant proof: session `ses_efb43eb5bffeNoAs2vBi6f3uHB` with
      `--allow-dirs ../paragon-learning-network --allow-dirs ../marvin-slack`
      completed `Consult outcome: cross-repo-ok`, reading both siblings.
    - AC13 denial proof: same brief without grants — session
      `ses_efb4162d0ffeYvCr4HqNeWaILO`, outcome `failure`, detail
      `permission denied: external_directory /home/hierovision/repos/paragon-learning-network/*`,
      heartbeat terminal `BLOCKED …` (not `empty result`).
  - **Red/mismatch notes** — none contract-breaking. One mechanical/quality
    refinement after the first denial smoke: the captured stderr carried ANSI
    codes, so `permission_denial` now strips them and extracts the
    `external_directory (<path>)` name for a clean record detail (re-probed
    live; AC13 re-verified).

### Follow-ups
- The injected supervision block asks for "timestamped" lines but does not
  pin the `Z`/UTC format the watchdog's `HB_RE` matches; the live smoke's
  subagent lines used a local ISO offset and were parsed as `RAW`. Consider
  pinning the format in the injected block (candidate self-improvement note).
- `--print-logs` depth and event-file retention remain Excluded per Open
  Questions 3–4; revisit only with evidence of insufficient signal.

- 2026-10-03 — revised (approved). Folded the second incident: two architect
  dispatches died `failure: empty result` on `external_directory` permission
  auto-rejects during the sibling-repo reads their briefs required
  (`ses_efd9815fdffepLG4xeD2n3d6xS`, glm-5.3-flash;
  `ses_efd8a001dffePR1M6prjSgCrcL`, deepseek-v4.1-flash). Added `--allow-dirs`
  grants + denial-aware classification (AC12–AC14), the cross-boundary smoke,
  Scope/Open Question 6, and the incident to Goal/Approach + Practical
  Result. The go-first bindings plan authored inline during this diagnosis.
- 2026-10-03 — approved (user, in-session). Implementation sequenced after
  RM-021 lands ("we need to actually implement 021 first"); queued behind the
  RM-021 implement pass — no implementer dispatched yet.
- 2026-10-03 — revised (draft). Folded in the consumer-repo attribution bug
  (paragon: header/run-log named the framework free binding while the run
  used the project wrapper) into Goal/Approach, AC10–AC11, Files, Scope,
  Verification. Added `## Practical Result (human view)` as the first
  application of the proposed plan-format directive; that directive's home
  (designing-architecture `references/plan-format.md` + `SKILL.md`, not
  AGENTS.md) is recorded separately.
- 2026-10-03 — initial draft. Direct user request: "is it not possible to
  have visibility in that run-vehicle type?" — exact design required before
  any change. Follow-on to RM-022 (the run-vehicle half of the supervision
  protocol). No stack reference applies (framework-internal Python tooling).
  UX consult: `no user-facing UI — council-ux consult skipped`.
