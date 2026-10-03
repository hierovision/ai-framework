---
slug: go-first-model-bindings
title: Go-first model policy — Go defaults, free opt-in, kimi-k3 removed, consumers propagated
status: approved
created: 2026-10-03
revised: [2026-10-03]
related: [run-vehicle-visibility, rm-021-eval-reliability, jev-system-one-evaluation]
---

# Plan: go-first-model-bindings

## Practical Result (human view)

For: the framework owner (operator of every persona, dispatch, and eval run,
including from consumer repos).

- **Before** — every repo persona defaults to `opencode/nemotron-3-ultra-free`
  (9 of 17 agents), so quality and reliability of every design/implement/review
  pass is capped at the free tier's level; the free default is exactly the
  death-prone lane behind the eval and dispatch failures (today's two architect
  sessions burned their dispatches). Consumer repos hand-pin Go bindings to
  escape it (paragon's 15 wrappers, marvin's delegation registry), so the
  framework's own defaults contradict its consumers' practice, and `kimi-k3`
  still sits in bindings and council seats despite being console-disabled and
  too expensive.
- **After** — one policy: every bound persona runs on Go (the validated Go
  model per role, six live families in the council), free is an explicit
  opt-in (`AI_FRAMEWORK_FREE_TIER=1` / a per-session model switch) used only as
  a last resort, `kimi-k3` never appears in any binding or recommendation, and
  the three consumer repos are verified against the same rule. `docs/CONCEPTS`
  §7c, ADR-0002/0007, the routing table, and CI comments all tell one story.
- **Value** — the free-tier reliability tax disappears from default paths
  (fewer dead sessions, fewer retries, better output), consumer repos stop
  hand-patching framework defaults, and the kimi-k3 cost leak is closed. The
  policy also gets a date: Go Plus ($40/mo) is re-evaluated at the next
  monthly review against measured usage.
- **How you judge it** — `scripts/model-liveness-check.py` green against the
  live catalogs; zero `-free` and zero `kimi-k3` occurrences in reachable
  bindings across this repo and the three consumers (via
  `scripts/check-consumer-bindings.py`); a real dispatch on a persona with no
  `--model` override routes on Go and records the Go model it actually used;
  the council still fields six live families.
- **What it asks of you** — approve the per-role binding choices and the
  council re-seat (Open Questions 1–2), and accept Go Plus as the funding
  basis until the recorded review date. No ongoing maintenance beyond the
  existing model-liveness canary.

## Goal / Approach

Goal: flip the framework's standing model policy from free-first to Go-first —
every persona and workflow binds a live Go model by default, free models
become an explicit opt-in for last-resort use, `kimi-k3` is removed everywhere
(dated user cost directive, console-disabled), and the new bindings are
installed and verified in `../excel-daily-monitor`, `../marvin-slack`, and
`../paragon-learning-network` as the final step.

Directives (user, 2026-10-03): "we have to default to go models vs. free
models. free models need to become the opt-in route rather than the inverse…
I want to use it as a last resort"; "I've upgraded to the go plus plan…
we will re-evaluate later"; "removing kimi k-3 as an option. I disabled it in
the console because it's too expensive"; "install the new bindings into all
consuming repos". This effort "may override some ADRs" — dispositions are
planned below.

Current state (read, not guessed): 9 of 17 `agents/*.md` are bound to
`opencode/nemotron-3-ultra-free` (architect, planner, curator, implementer,
debugger, reviewer, skill-author, skill-reviewer, test-writer); the six
council lenses are already Go except the chairman (`kimi-k3`); vision-critic-fast
is Go (`minimax-m3`); vision-critic-final uses the direct-key lane
(`deepseek/deepseek-flash`). `reference/model-routing.md` documents free-first;
`docs/CONCEPTS.md` §7c is titled "Free by default; escalation is an explicit
opt-in"; ADR-0007 amends the policy to allow the direct-key eval lane "despite
the free-first default"; ADR-0002 puts evals on the direct key. The live eval
lane has actually run on Go (`opencode-go/deepseek-v4.1-flash`) since the
2026-09-29 directive — the ADRs lag practice. `scripts/ci-lane-overrides.py`
exists because the free-bound personas cannot serve nested subagents in CI; it
becomes an empty override once no persona is free-bound (the `/tmp` permission
block stays). `scripts/model-liveness-check.py` validates bound IDs against live
catalogs but does not yet enforce a no-free / no-excluded-ID policy.

Approach: flip the bindings per role (table below), restructure the routing
table so Go is the default column and free is the opt-in column, sweep every
policy text and CI comment that says otherwise, extend the model-liveness
canary with policy assertions (no `-free` bindings, no hard-excluded IDs),
record ADR-0013 plus ADR-0002/0007 supersessions, re-seat the council, then
propagate via `install.sh` + per-consumer verification. No new runtime
mechanics: free use stays available through the existing
`AI_FRAMEWORK_FREE_TIER=1` path and per-session model selection, now as the
documented exception.

Proposed defaults per persona (all IDs live in the Go catalog; bench basis
from `reference/model-routing.md`; alternatives in Open Questions):

| Persona | New default | Basis / notes |
|---|---|---|
| architect, planner, curator | `opencode-go/glm-5.3-flash` | AA 42, KingBench 91.25; planner/triager Go pick |
| implementer, test-writer | `opencode-go/deepseek-v4.1-flash` | AA 40, repo-proven eval lane, ~3× cheaper; alt/escalation `kimi-k2.7-code` (MCPMark 81.1) |
| debugger, reviewer, skill-reviewer | `opencode-go/glm-5.3-flash` | AA 45 / 1M context; defect-catch basis |
| skill-author | `opencode-go/minimax-m3` | IFBench 82.9 top eligible; existing Go row |
| vision-critic-fast | `opencode-go/minimax-m3` | unchanged (already Go, native multimodal) |
| vision-critic-final | `opencode-go/deepseek-v4.1-flash` | same model as the validated direct-key `deepseek/deepseek-flash`, on Go; existing acceptance gate retained |
| council (chairman) | `opencode-go/qwen3.8-flash` | user cost directive 2026-10-03: max's AA 45 doesn't justify ~13× flash's price; unbenched, so the 3-prompt seat validation gates it (fallback `gpt-5.6-luna`) |
| council-performance | `opencode-go/gpt-5.6-luna` | AA 38, OpenAI family; alt `longcat-2.0` pending bench |
| council-architecture / security / ux / product | unchanged | glm-5.3-flash / deepseek-v4.1-flash / minimax-m3 / mimo-v2.6-flash |

## Acceptance Criteria

1. **Every persona binds Go.** No `agents/*.md` `model:` line is `*-free` or
   `kimi-k3`; the new defaults from the table are in place. Verifier: new
   `scripts/test_model_policy.py` (hermetic, fixture-driven) exits 0 and
   `grep -rn "nemotron\|kimi-k3" agents/` returns nothing.

2. **Routing table tells one story.** `reference/model-routing.md`'s core
   table is restructured so the default column is Go and the free column is
   the documented opt-in; `kimi-k3` is added to hard exclusions (dated user
   cost directive) alongside glm-5.3/glm-5.2; council seats and the free-tier
   section match the new bindings; the retrieval date is bumped. Verifier:
   `python3 scripts/model-liveness-check.py` exits 0 live (Go IDs present in
   the Go catalog, no excluded ID bound), and the policy test checks the table
   shape.

3. **Policy canary cannot drift.** `scripts/model-liveness-check.py` (or the
   policy test it invokes) fails on (a) a bound `-free` ID, (b) a bound
   hard-excluded ID (`kimi-k3`, `glm-5.3`, `glm-5.2`, grok family,
   fable/astra class), (c) a routing-table Go cell absent from the live Go
   catalog. Verifier: hermetic cases in `scripts/test_model_policy.py` feed
   fixtures for each failure class and assert non-zero; the live canary runs
   green on `main` in the `model-liveness` workflow.

4. **Free is an explicit opt-in, and the docs say exactly how.** `docs/CONCEPTS.md`
   §7c is retitled and rewritten ("Go by default; free is the explicit
   opt-in"); `reference/model-routing.md` free section documents
   `AI_FRAMEWORK_FREE_TIER=1` plus the per-session model switch as the only
   ways to run free; the eval runner's free-tier path is unchanged. Verifier:
   the policy test greps CONCEPTS/routing for the old "free-first" phrasing
   (must be absent); `python3 skills/authoring-skills/scripts/test_runner.py`
   exits 0.

5. **Council re-seated and validated.** Six seats, six distinct live Go
   families, no `kimi-k3`; the changed seats carry a recorded 3-prompt seat
   validation (per the routing file's existing seat-validation precedent) or
   an explicit "validation pending" note in `agents/council.md`. Verifier:
   seat table and bindings agree (`grep`), each seat ID is live
   (`opencode models`), and the validation transcript is cited in the plan
   History.

6. **ADR records match the flip.** New
   `docs/ADRs/ADR-0013-go-first-model-policy.md` records the decision (Go
   default, free opt-in, kimi-k3 exclusion, Go Plus review trigger); ADR-0002
   and ADR-0007 are marked superseded with pointers to ADR-0013; the ADR index
   table is updated. Verifier: file/status greps; no ADR claims a free-first
   default.

7. **CI plumbing is coherent.** `scripts/ci-lane-overrides.py`'s docstring no
   longer claims free-bound personas; its output for this repo yields zero
   agent overrides while keeping the `/tmp` permission block; eval workflow
   comments no longer describe nested free-bound agents. Verifier:
   `python3 scripts/test_eval_workflows.py` exits 0 and a new assertion in the
   policy test runs `ci-lane-overrides.py --model opencode-go/deepseek-v4.1-flash`
   and expects an empty `agent` map.

8. **Consumer propagation verified (final step).** After `bash install.sh`:
   `../excel-daily-monitor` has no local bindings and resolves global Go
   agents; `../marvin-slack`'s delegation registry default is flipped from
   `opencode/nemotron-3-ultra-free` to a Go model with its own tests green
   (`npm test`); `../paragon-learning-network`'s 15 project wrappers are all
   Go with no `kimi-k3` (its `opencode.json` is already Go). Verifier: new
   `scripts/check-consumer-bindings.py <repo-dir>` exits 0 for each repo
   (project wrappers win over global; flags `-free`/`kimi-k3`/non-live IDs);
   each repo's result is recorded in the plan History.

9. **Go Plus review trigger recorded.** A dated re-evaluation entry exists at
   the next monthly review (proposed 2026-11-01) covering Go Plus spend vs
   per-model caps and whether free-lane viability warrants revisiting. Verifier:
   the roadmap row or ADR-0013 review clause exists and is grep-able.

## Files to Modify

- `agents/architect.md`, `planner.md`, `curator.md`, `implementer.md`,
  `debugger.md`, `reviewer.md`, `skill-author.md`, `skill-reviewer.md`,
  `test-writer.md` — `model:` → the new Go defaults.
- `agents/vision-critic-final.md` — `model:` → `opencode-go/deepseek-v4.1-flash`.
- `agents/council.md`, `agents/council-performance.md` — re-seat chairman and
  performance; update the seat table and the free-toggle note.
- `reference/model-routing.md` — restructure the core table (Go default / free
  opt-in), add `kimi-k3` to hard exclusions, update council seats + provider
  notes + update procedure, bump the retrieval date.
- `docs/CONCEPTS.md` — §7c rewrite; scan Choice 7 for other free-first text.
- `reference/agent-teams.md`, `reference/opencode-integration.md`,
  `docs/COUNCIL.md` — lane/binding wording that assumes free-bound personas.
- `scripts/model-liveness-check.py` — policy assertions (no free bindings, no
  hard-excluded bindings, table/live consistency).
- `scripts/test_model_policy.py` — new hermetic test (fixture-driven failure
  classes; `ci-lane-overrides` empty-agent assertion).
- `scripts/ci-lane-overrides.py` — docstring/comment update; keep the
  forward-compatible free-override loop and the `/tmp` permission block.
- `.github/workflows/eval-behavioral.yml`, `eval-per-change.yml`,
  `model-liveness.yml` — comments only (lane model and behavior unchanged).
- `docs/ADRs/ADR-0013-go-first-model-policy.md` — new; `ADR-0002`,
  `ADR-0007` — superseded markers; `docs/ADRs/README.md` — index.
- `scripts/check-consumer-bindings.py` — new verifier for the three consumer
  repos (reachable bindings: project wrappers > global agents; flags
  `-free`/`kimi-k3`/non-live).
- `../marvin-slack/src/model-prefs.js` (+ its registry source and tests) — flip
  the `default: true` candidate to a Go model; keep `free`/`zen`/`direct` tiers
  selectable.
- `../paragon-learning-network` — aligned in-session (council chairman →
  `opencode-go/qwen3.8-flash`, performance → `opencode-go/gpt-5.6-luna`,
  `vision-critic-final` policy-table row → Go; wrapper bodies untouched).
  `scripts/check-consumer-bindings.py` remains the standing verification.
- `docs/ROADMAP.md` — at closure: the effort's row + the 2026-11-01 review
  trigger.

## Scope

**Included**
- The Go-default binding flip for all personas, the free opt-in semantics, and
  `kimi-k3` removal (bindings, docs, exclusions, canary).
- Routing-table restructure, CONCEPTS §7c, ADR-0013 + ADR-0002/0007
  supersessions.
- Council re-seat with seat validation.
- Policy canary extension + hermetic test.
- Consumer propagation and verification in the three named repos (final step),
  including marvin's delegation registry default.
- The dated Go Plus sustainability review trigger.

**Excluded**
- Changing the CI eval lane (`opencode-go/deepseek-v4.1-flash`) or the eval
  depth/sharding policy.
- Jev / System One — separate plan (`jev-system-one-evaluation`), additive.
- Retiring the Zen/direct-key lanes — they remain explicit opt-in escalation.
- RM-015's general consumer-override mechanism — this plan reports wrapper
  drift; it does not redesign shadowing.
- Upstream opencode free-tier behavior and the dispatch permission fix
  (in `run-vehicle-visibility`).

## Schema / Type Impacts

None. Changes are agent frontmatter `model:` values, reference/ADR prose, and
two scripts. The registry (`registry.json`, ADR-0009) continues to reference
model-routing, never duplicate bindings. No DB, generated types, or API
contracts.

## Verification

```markdown
- python3 scripts/model-liveness-check.py                     # live canary, AC2/AC3
- python3 scripts/test_model_policy.py                        # AC1–AC4, AC7
- python3 scripts/test_eval_workflows.py                      # AC7
- python3 skills/authoring-skills/scripts/test_runner.py      # AC4
- python3 skills/authoring-skills/scripts/validate_skill.py --all
- python3 scripts/check_typed_evals.py --base main
- python3 -m yamllint -c .yamllint.yaml .github/workflows/
- grep -rn "nemotron\|kimi-k3" agents/ reference/model-routing.md docs/CONCEPTS.md   # expect only exclusion/opt-in mentions
```

Consumer step (AC8, run after `bash install.sh`):

```markdown
- python3 scripts/check-consumer-bindings.py ../excel-daily-monitor
- python3 scripts/check-consumer-bindings.py ../marvin-slack
- python3 scripts/check-consumer-bindings.py ../paragon-learning-network
- cd ../marvin-slack && npm test
```

Live routing proof: dispatch one persona with no `--model` override after the
flip and confirm the run header and the `kind=agent` record name the Go binding
(eventually via the `run-vehicle-visibility` dispatcher, which resolves the
record from the session row).

## Open Questions

1. **Council re-seat.** Resolved (user, 2026-10-03; revised same day):
   chairman `qwen3.8-flash` — user cost challenge: max's AA 45 is a 3-point
   edge over `glm-5.3-flash` at ~13× the price, and no independent AA reading
   exists for flash, so the 3-prompt seat validation is the acceptance gate;
   performance `gpt-5.6-luna` (AA 38, OpenAI family). Fallback if chairman
   validation fails: `gpt-5.6-luna` as chairman and the performance seat
   re-opens (`longcat-2.0` pending bench, or five families).
2. **Implementer default.** Resolved (user, 2026-10-03): default
   `deepseek-v4.1-flash` (AA 40, repo-proven eval lane, ~3× cheaper) with
   `kimi-k2.7-code` (MCPMark 81.1, strong tool use, AA 26) as the code-heavy
   escalation. Rationale recorded: AA 26 is weak for planning/debugging;
   K2.7's tool-use strength is real but narrow for a default seat.
3. **Free opt-in mechanism.** Accepted as proposed (user, 2026-10-03): keep
   `AI_FRAMEWORK_FREE_TIER=1` plus per-session model selection; no new
   rebinding script. Recorded alternative: a `scripts/free-tier-overrides.py`
   mirror if usage shows a need.
4. **vision-critic-final.** Accepted as proposed (user, 2026-10-03):
   `opencode-go/deepseek-v4.1-flash` (same model as the validated direct-key
   binding, on Go; acceptance gate retained).
5. **Paragon wrapper alignment.** Resolved (user, 2026-10-03): align ASAP,
   not verify-only. Done in-session — council chairman →
   `opencode-go/qwen3.8-flash`, council-performance → `opencode-go/gpt-5.6-luna`,
   the `vision-critic-final` policy-table row → Go; wrapper bodies untouched,
   only `model:` lines and the policy table (also fixes paragon's duplicated
   DeepSeek family in the six-seat council).
6. **Review date.** Accepted as proposed (user, 2026-10-03): 2026-11-01
   (next monthly review) for the Go Plus spend/viability re-evaluation.

## History

- 2026-10-03 — user review: chairman binding revised `qwen3.8-max` →
  `qwen3.8-flash` (cost challenge: no independent score justifies max's ~13×
  price for the synthesis seat; flash is unbenched, so the 3-prompt seat
  validation gates it; fallback `gpt-5.6-luna`). Paragon `council.md`
  re-aligned. No other binding changed.
- 2026-10-03 — approved (user, in-session) after OQ2 confirmation:
  implementer/test-writer default `deepseek-v4.1-flash`, escalation
  `kimi-k2.7-code`. All six Open Questions resolved; status → approved.
  Implementation queued behind RM-021 and `run-vehicle-visibility`.
- 2026-10-03 — user review: Open Questions 1, 3, 4, 5, 6 accepted as
  proposed; 2 under review (revised recommendation: `deepseek-v4.1-flash`
  default, `kimi-k2.7-code` escalation). Paragon aligned in-session on the
  user's "ASAP" directive — council chairman/performance bindings and the
  `vision-critic-final` policy-table row (wrapper bodies untouched; also
  resolves paragon's duplicated DeepSeek council family).
- 2026-10-03 — initial draft, authored inline after two run-vehicle architect
  sessions failed with `failure: empty result`
  (`ses_efd9815fdffepLG4xeD2n3d6xS` on glm-5.3-flash;
  `ses_efd8a001dffePR1M6prjSgCrcL` on deepseek-v4.1-flash). Root cause:
  external_directory permission auto-reject on the sibling-repo reads the
  brief required; the fix is folded into `run-vehicle-visibility` (AC12–AC14).
  User confirmed inline takeover. UX consult: `no user-facing UI — council-ux
  consult skipped`. Research basis: `reference/model-routing.md` (full),
  `agents/*.md` frontmatter, `agents/council.md`, `docs/CONCEPTS.md` §7c,
  ADR-0002/0004/0007 + index, `scripts/ci-lane-overrides.py`,
  `scripts/model-liveness-check.py`, `install.sh`,
  `reference/opencode-integration.md`, the three consumer repos' layouts
  (paragon 15 Go wrappers + opencode.json + own k3 exclusion; marvin
  `src/model-prefs.js` free default; excel no local bindings), and the live
  `opencode models` / `/zen/go/v1/models` catalogs.
