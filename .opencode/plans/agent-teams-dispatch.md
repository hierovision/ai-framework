---
slug: agent-teams-dispatch
title: Agent teams — dispatchable personas, explicit dispatch policy, topology + delegation attribution
status: approved
created: 2026-10-02
revised: [2026-10-02]
---

# Plan: agent-teams-dispatch

## Goal / Approach

Goal: an orchestrating agent can compose the framework's engineering personas
(architect → implementer → reviewing-code passes) as Task subagents in one
session, each dispatched run carrying its declared model binding, wrapper,
tools/permissions, and stop contract, with every delegation attributed
(agent + model) in the run log.

Options evaluated, with the recommendation:

- **(a) `mode: all` on the core persona wrappers — adopted.** opencode's Task
  tool exposes only `mode: all` / `subagent` agents; `primary` agents are absent
  (verified 2026-10-02: `opencode agent list` shows architect/council/curator/
  implementer/planner as `(primary)`; council-* as `(all)`). `all` keeps
  Tab-selectability and adds dispatchability, and is opencode's own default when
  `mode` is unspecified (opencode docs, fetched 2026-10-02). Named dispatch
  honors the target's frontmatter `model` (upstream #35126, fixed 2026-07-09),
  so binding/wrapper/permissions/stop contract travel with the agent.
- **(b) Upstream change — rejected by user directive (2026-10-02).** No external
  communications to opencode, existing issues or new. v1 must not depend on
  upstream behavior changes; the framework fix is (a)+(c). Read-only research
  note (no action): a per-call Task model argument exists in opencode v2 with an
  authorization debate, so a future v2 upgrade could supersede the run-vehicle's
  lane-override role — tracked as Open Question 1, never as an upstream ask.
- **(c) `opencode run --agent` run-vehicle — adopted for the free lane and
  per-call overrides.** The free tier rejects calls made from a nested Task
  subagent (`OpenCode's free tier can only be used from within OpenCode`;
  `docs/COUNCIL.md`, `reference/model-routing.md`, `scripts/ci-lane-overrides.py`),
  and the four core personas are free-bound. `opencode run --agent <name>
  [-m <model>] --format json` is a top-level session (free allowed — the
  pre-2026-09-29 eval lane ran free models this way), carries the agent config,
  supports per-call lane choice and `--session` resume, and its event stream /
  session row yields agent+model attribution.

Dispatch policy uses opencode's native `permission.task` maps (glob, last
match wins; `deny` removes the subagent from the Task tool description). Leaf
lenses get `task: deny`; orchestrators get explicit allow-lists. Topology, lane
rules, depth/fan-out, question relay, and attribution land in a new
`reference/agent-teams.md`, integrated by citation with RM-022 (supervision),
RM-023 (result contract), RM-024 (retry), RM-025 (resume `description`).

## Acceptance Criteria

1. **All registry personas are dispatchable.** Every persona file listed in
   `registry.json` carries `mode: all` (architect, council, curator,
   implementer, planner flipped; council-* already). Verifier:
   `python3 scripts/test_agent_dispatch.py` parses each persona's frontmatter
   and asserts `mode == "all"`; live check
   `opencode agent list | grep -E '^(architect|implementer|curator|planner|council) \(all\)$'`
   exits 0.
2. **Composition is judgment-led; only leaf hygiene is encoded.** No
   orchestrator (architect, curator, implementer, council) carries a
   `permission.task` allow-list — any dispatchable persona may compose any
   other within the bounds in `reference/agent-teams.md`. The one encoded rule
   is leaf hygiene: planner and every council-* deny `task`.
   Verifier: `scripts/test_agent_dispatch.py` asserts the absence of
   orchestrator allow-lists and the leaf deny; the doc states the policy.
3. **Topology contract documented.** `reference/agent-teams.md` exists and
   states: orchestrator → worker topology; depth ≤ 2 and fan-out ≤ 6; the lane
   policy (in-session Task requires a nested-capable tier — Go/Zen/direct-key;
   free-bound targets route through the run-vehicle); both question-relay paths
   (Task `task_id` resume with required `description` per RM-025; run-vehicle
   `--session <id>` resume); and citations to RM-022 / RM-023 / RM-024.
   Verifier: `scripts/test_agent_dispatch.py` structural checks (file exists,
   required headings, phrases, citations).
4. **In-session dispatch carries the contract (live probe).** In a fresh primary
   session, the Task tool lists `architect`; dispatching it returns a non-empty
   result and the child session row shows `agent=architect` with `model` equal
   to the wrapper's declared binding. Verifier: dated probe recorded in
   `## History` — session id plus the read-only `sqlite3` session row.
5. **Run-vehicle dispatches free-bound personas.** `python3
   scripts/dispatch_agent.py --agent architect --prompt-file <f>` exits 0 on the
   free lane, prints the session id, and writes the captured result;
   `--contract` validation exits non-zero on empty/malformed output. Verifier:
   `scripts/test_dispatch_agent.py` (stub `opencode` on PATH; valid / empty /
   malformed / timeout cases) plus a dated live probe in `## History`.
6. **Attribution through delegation.** Every delegated run emits exactly one
   `kind=agent` run-log record with non-null `agent` and `model`: the run-vehicle
   emits it mechanically (agent name + resolved model + tokens/cost from the
   JSON stream); in-session dispatch records it by the documented convention;
   `watch_agent.py --json` exposes the session `model`. Verifier:
   `scripts/test_dispatch_agent.py` asserts the emitted record's
   `agent`/`model`/`outcome` from the stub stream; `scripts/test_watch_agent.py`
   asserts `model` in the JSON output; a live probe record is visible via
   `python3 skills/observing-runs/scripts/query_runs.py aggregate`.
7. **Question relay works on both lanes.** The topology doc documents both
   resume paths, and `dispatch_agent.py` prints the session id at dispatch; the
   Task path records RM-025's `description` requirement at the call site.
   Verifier: structural test asserts the phrases; the stub test asserts the
   printed session id.
8. **Volatile facts updated and dated.** `reference/opencode-integration.md`
   carries a 2026-10-02 block: `mode` `primary`/`subagent`/`all` semantics;
   `permission.task` allow/deny semantics; named dispatch honors frontmatter
   `model`; the session-store `model` column (JSON blob) in the read-only DB
   section; the free-tier nested-call restriction. Verifier:
   `scripts/test_agent_dispatch.py` asserts the dated block and the phrases.
9. **Roadmap row persisted.** `docs/ROADMAP.md` gains the RM-032 row at
   priority 1 (acceptance mirroring ACs 1–8, source = this plan, status + PR
   link at closure). No GitHub issue is created — the consumer-issue intake flow
   is deliberately skipped (user directive 2026-10-02). Verifier:
   `grep -n "RM-032" docs/ROADMAP.md` exits 0 and the row carries priority 1.
10. **CI green.** `scripts/test_agent_dispatch.py` and
    `scripts/test_dispatch_agent.py` are wired into the `quality-gates` job of
    `.github/workflows/ci.yml`; the full Verification list exits 0 locally and
    the PR CI run is green. Verifier: the commands below plus the CI run URL.

## Files to Modify

- `agents/architect.md` — `mode: primary` → `all`; no task allow-list
  (composition judgment-led); cite `reference/agent-teams.md`.
- `agents/curator.md` — same flip; no task allow-list; cite.
- `agents/implementer.md` — same flip; no task allow-list; cite.
- `agents/planner.md` — same flip; `permission.task: {"*": "deny"}` (leaf);
  cite.
- `agents/council.md` — same flip; no task allow-list; cite.
- `agents/council-architecture.md`, `agents/council-performance.md`,
  `agents/council-product.md`, `agents/council-security.md`,
  `agents/council-ux.md` — add `task: deny` (leaf lenses).
- `reference/agent-teams.md` (new) — composition guidance (judgment-led, no
  matrix), lane policy, topology / depth / fan-out, question relay, attribution
  contract, RM-022/023/024/025 integration.
- `reference/opencode-integration.md` — dated mode / task / session-model facts
  (AC8).
- `reference/subagent-supervision.md` — add the run-vehicle dispatch form and
  the attribution line; cite `agent-teams.md`.
- `scripts/dispatch_agent.py` (new) — run-vehicle: `opencode run --agent` with
  stream capture, session/model resolution, `--contract` validation, run-log
  emission via `log_run.py`, session-id print.
- `scripts/test_dispatch_agent.py` (new) — hermetic stub-`opencode` tests:
  valid / empty / malformed / timeout, emitted record fields, session-id print.
- `scripts/test_agent_dispatch.py` (new) — offline frontmatter mode/leaf
  checks + doc/citation structural checks.
- `scripts/watch_agent.py` — expose `model` (parsed from the session `model`
  JSON blob) in the `--json` output and status line.
- `scripts/test_watch_agent.py` — assert `model` exposure and graceful
  degradation on a missing/odd model blob.
- `.github/workflows/ci.yml` — add the two new suites to the offline-unit step.
- `docs/ROADMAP.md` — add the RM-032 row.
- `docs/COUNCIL.md` — one-line citation of the lane policy in
  `reference/agent-teams.md` (avoid duplicating the policy).

Dispatch policy (amended 2026-10-02, user directive): composition is
judgment-led — no per-persona allow-lists. The only encoded rule is leaf
hygiene: planner and every council-* deny `task`. `mode: all` keeps every
persona dispatchable.

## Scope

**Included:** dispatchability of all framework personas (`mode: all`);
leaf-lens `task: deny` hygiene (orchestrators unrestricted); the
`reference/agent-teams.md` topology/lane/attribution contract; the run-vehicle
helper with tests; run-log attribution on both lanes; `watch_agent` model
exposure; dated opencode facts; the RM-032 row; CI wiring.

**Excluded:**

- Any external communication to opencode — no new issues, no comments on
  existing ones (user directive 2026-10-02). Upstream behavior is read-only
  research, never a dependency or an ask.
- The consumer-issue intake flow — no GitHub issue is opened on this repo or
  upstream; this item goes directly to implementation and the RM-032 row is the
  sole tracker (user directive 2026-10-02).
- Rebinding the core personas to Go — free-first routing stays; lane choice is
  per-call/session.
- Task-tool schema changes and the free-tier nested-call policy (upstream;
  RM-025 is cited, not implemented).
- Run-log schema changes (owned by `observing-runs`; `agent`/`model` fields
  already exist).
- An auto-orchestrator/scheduler process — the orchestrating agent applies the
  policy; no new daemon.
- Consumer-repo changes (PLN) — consumers inherit after a framework update.
- Depth/fan-out beyond the documented defaults; revisit with supervision
  evidence.
- A dedicated ADR (Open Question 4).

## Schema / Type Impacts

None. No database, generated types, or repo schema change. The run-log schema
is unchanged (`agent`, `model` already exist); `registry.json` is unchanged.
External read-only dependency: opencode's session store carries a `model` JSON
column — volatile, documented in `reference/opencode-integration.md`, parsed
defensively.

## Verification

```
python3 scripts/test_agent_dispatch.py
python3 scripts/test_dispatch_agent.py
python3 scripts/test_watch_agent.py
python3 skills/authoring-skills/scripts/validate_skill.py --all
python3 scripts/test_registry.py
python3 scripts/check_typed_evals.py --base HEAD
node scripts/verify.mjs
bash -n install.sh
python3 -m yamllint -c .yamllint.yaml .github/workflows/
```

Live probes (dated, recorded in `## History`, not CI-gated): `opencode agent
list` mode check; one in-session `architect` dispatch; one
`dispatch_agent.py` free-lane run.

## Open Questions

1. **Free-lane vehicle.** Default: ship `scripts/dispatch_agent.py` and keep
   personas free-bound; alternative: permanently rebind the four core personas
   to Go (flat rate) — rejected as default because it reverses the free-first
   routing policy. If the workspace later moves to opencode v2 (per-call Task
   model argument), re-evaluate whether the run-vehicle is still needed for lane
   overrides — no upstream communication either way. Confirm.
2. **RM id.** Default: allocate RM-032 (next free per the 2026-10-02 triage) at
   implementation; if triage assigns differently, use the next free id.
3. **Depth/fan-out defaults.** Default: depth ≤ 2, fan-out ≤ 6 (council
   precedent). Revisit with evidence.
4. **ADR.** Default: reference doc only (RM-022 / RM-023 precedent); promote to
   `docs/ADRs/ADR-0013` if the policy later changes structure.
5. **Policy strictness.** Default: encode deny-by-default maps on personas
   (enforceable, testable); alternative: documentation-only. Users can still
   @-mention any agent regardless (upstream semantics). **Resolved 2026-10-02
   (user directive):** documentation-only — orchestrators carry no allow-list;
   composition is judgment-led; leaf-lens `task: deny` retained as the one
   encoded rule.

## History

- 2026-10-02 — plan created from the dispatchability item (PLN session; no RM
  existed — RM-032 proposed). Options (a)/(b)/(c) evaluated; recommendation
  (a)+(c), with (b) filed upstream. Research evidence: `opencode agent list`
  1.18.18 shows the five personas `(primary)`; opencode docs fetched 2026-10-02
  (`mode`, `permission.task`, model inheritance); session-store `model` JSON
  column observed on the probe's `general` child session (inherited the parent
  Go model — the workaround cost this plan removes). UX consult skipped: `no
  user-facing UI — council-ux consult skipped`. Stack reference: none matches
  this repo (framework/library, not an app stack) — generic planning applied.
- 2026-10-02 — revised per user directive: option (b) dropped — no external
  communications to opencode issues, existing or new. Upstream references are
  read-only research notes only; the old upstream-ask AC removed; Open Questions
  renumbered; Excluded list now states the no-external-communication boundary.
- 2026-10-02 — revised: consumer-issue intake flow skipped (no GitHub issue on
  this repo or upstream) — this item goes directly to implementation; the
  RM-032 row (priority 1) is the sole tracker.
- 2026-10-02 — approved by user ("approved/go"); status → approved. Handoff:
  fresh `implementer` session executes this plan; branch
  `feat/agent-teams-dispatch` per `reference/git-workflow.md`.
- 2026-10-02 — amended mid-implementation (user directive, confirmed in the
  implement session): the per-persona `permission.task` allow-lists are
  dropped. AC2 rewritten to judgment-led composition with leaf hygiene only;
  `reference/agent-teams.md` carries guidance (no matrix); architect / curator
  / implementer / council keep `mode: all` with no task map; planner and
  council-* keep deny-all `task`. Reason: a hard allow-list is a design-time
  guess that forbids task-driven composition (e.g. implementer → architect on
  a contract-breaking discovery) and taxes every new persona across all
  dispatchers; the lane rule, depth/fan-out bounds, RM-022/023/024 and the
  attribution record already bound the real risks.
- 2026-10-02 — implemented (implement pass on `feat/agent-teams-dispatch`).
  Delivered: `mode: all` on architect / curator / implementer / planner /
  council; leaf `task: deny` on planner + council-*; new
  `reference/agent-teams.md` (topology, composition, lane policy, question
  relay, attribution, RM-022/023/024/025 integration); dated 2026-10-02
  opencode dispatch facts + session `model` blob in
  `reference/opencode-integration.md`; run-vehicle `scripts/dispatch_agent.py`
  (+ hermetic `scripts/test_dispatch_agent.py`); `watch_agent.py` session-model
  exposure (+ tests); RM-032 row; COUNCIL lane-policy citation; both new suites
  CI-wired. Red evidence (pre-implementation): `test_agent_dispatch.py` failed
  on the missing doc, `mode='primary'`, missing leaf policy, missing RM-032 row
  and CI wiring; `test_dispatch_agent.py` on the missing vehicle;
  `test_watch_agent.py` on `KeyError: 'model'`. Live probes: `opencode agent
  list` shows all five personas `(all)`; a Go-bound parent dispatched the
  free-bound `architect` in-session (child `ses_f019d3ba2ffe5MYxghW62j2JB`,
  `agent=architect`, `model=opencode/nemotron-3-ultra-free`, result `pong`) —
  the categorical free-nested premise was corrected to environment-dependent
  in the docs (mechanical deviation, evidence recorded); `dispatch_agent.py
  --agent architect` exited 0 on the free lane (session
  `ses_f019dde93ffenWjNN282D5IBX6`, contract-valid result written) and emitted
  `{"kind":"agent","agent":"architect","model":"opencode/nemotron-3-ultra-free",
  "outcome":"success",...}`, visible via `query_runs.py aggregate`.
  Coverage gate: no layer rebalance (AC tests are offline structural/unit; the
  live probes are manual by design); expansion — the non-zero-opencode-exit
  branch was uncovered, so `test_nonzero_exit_records_error` was added and
  proven break → red → restore → green, with spot re-proofs on frontmatter
  model resolution and session-model parsing. Runtime UI: no visible UI —
  `council-ux` consult skipped. Verification: 8 of 9 commands exit 0; the 9th
  (`python3 scripts/test_watch_agent.py`) is blocked by a pre-existing main
  regression (below), so commit/push/PR are held pending its resolution.
  BLOCKER (awaiting user authorization): `test_watch_agent.py` has been red on
  main since PR #82 — the implementing-features body trim dropped the
  `reference/subagent-supervision.md` citation its RM-022 test asserts; main's
  CI `quality-gates` fails at the offline-unit step for the same reason. AC10's
  "PR CI green" cannot be satisfied without a one-line restore in
  `skills/implementing-features/SKILL.md` (outside this plan's Files to
  Modify). Recommended: authorize the restore; never weaken the assertion.

- 2026-10-02 — blocker resolved (user authorized the out-of-scope mechanical
  repair): restored the dropped `reference/subagent-supervision.md` citation in
  `skills/implementing-features/SKILL.md` Step 8 (RM-022's delivered contract;
  the assertion was not touched). The full Verification list now exits 0;
  commit / push / PR proceed.
- 2026-10-02 — PR opened:
  [PR #86](https://github.com/hierovision/ai-framework/pull/86) on branch
  `feat/agent-teams-dispatch`; RM-032 row carries the link (in-progress,
  flips to done at merge).

### Follow-ups

- ~~Restore the dropped `reference/subagent-supervision.md` citation in
  `skills/implementing-features/SKILL.md` (PR #82 regression; main CI red).~~
  Resolved 2026-10-02 — citation restored (user-authorized); assertion intact.
