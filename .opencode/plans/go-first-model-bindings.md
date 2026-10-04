---
slug: go-first-model-bindings
title: Go-first model policy — Go defaults, free opt-in, kimi-k3 removed, consumers propagated
status: approved
created: 2026-10-03
revised: [2026-10-03, 2026-10-03, 2026-10-04]
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
- **What it asked of you** — (settled 2026-10-03 (2)) the four re-opened
  seat decisions, resolved at the per-question gate: OQ7 → `mimo-v2.6-pro`
  on the quality seats (debugger/reviewer/skill-reviewer), OQ8 → keep
  `deepseek-v4.1-flash`, OQ9 → verify `gpt-5.6-luna` first, OQ10 → keep
  `qwen3.8-flash` + mapping check in implementation; Go Plus accepted as the
  funding basis until the 2026-11-01 review. No ongoing maintenance beyond
  the existing model-liveness canary. (First ask, OQ1–6 resolved 2026-10-03:
  per-role binding choices and the council re-seat.)

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
from `reference/model-routing.md` refreshed by the 2026-10-03 live pull —
Evidence basis below; the four contested rows were settled at the
2026-10-03 per-question gate, see Open Questions 7–10):

| Persona | New default | Basis / notes |
|---|---|---|
| architect, planner, curator | `opencode-go/glm-5.3-flash` | AA 42, KingBench 91.25; planner/triager Go pick |
| implementer, test-writer | `opencode-go/deepseek-v4.1-flash` | AA 39 (live 2026-10-03; stored 40 superseded), repo-proven eval lane, 209 t/s; OQ8 resolved 2026-10-03 (keep — throughput + proven lane over glm-5.3-flash's noise-edge score gap); alt/escalation `kimi-k2.7-code` (MCPMark 81.1) |
| debugger, reviewer, skill-reviewer | `opencode-go/mimo-v2.6-pro` | AA 46 = score leader (2026-10-03 live pull), $0.13/task, live 1.83s; OQ7 resolved 2026-10-03 (scores outrank diversity) over `glm-5.3-flash` (AA 42, 1M context) — alt reverts in if the 3-prompt seat validation or a context-window check disqualifies MiMo-Pro |
| skill-author | `opencode-go/minimax-m3` | IFBench 82.9 top eligible; existing Go row |
| vision-critic-fast | `opencode-go/minimax-m3` | unchanged (already Go, native multimodal) |
| vision-critic-final | `opencode-go/deepseek-v4.1-flash` | same model as the validated direct-key `deepseek/deepseek-flash`, on Go; existing acceptance gate retained |
| council (chairman) | `opencode-go/qwen3.8-flash` | user cost directive 2026-10-03: max's AA 45 doesn't justify ~13× flash's price (Qwen3.8 Max $5.41/task confirms); OQ10 resolved 2026-10-03 (keep + verify the Qwen3.8-Flash-Next ↔ `qwen3.8-flash` mapping in implementation; AA 40 if same) — the 3-prompt seat validation gates it (fallback `gpt-5.6-luna`, subject to OQ9's verification) |
| council-performance | `opencode-go/gpt-5.6-luna` | AA 38, OpenAI family; OQ9 resolved 2026-10-03 (verify first — `/responses`-only per the 2026-10-03 probe; gate on the 3-prompt seat validation via the opencode path; on failure reseat `longcat-2.0` or five families) |
| council-architecture / security / ux / product | unchanged | glm-5.3-flash / deepseek-v4.1-flash / minimax-m3 / mimo-v2.6-flash |

### Revised 2026-10-03 (2) — evidence basis (2026-10-03 live pull, absorbed)

Source: the 2026-10-03 peer-evidence pack (`.scratch/dispatch/
pln-model-peer-evidence-2026-10-03.md`) — gitignored scratch, so its essence
is copied here, never linked. Re-verify liveness before binding; this is a
point-in-time pass. It supersedes the plan's stored 2026-09-25 AA figures:
**glm-5.3-flash AA 45 → 42**, **deepseek-v4.1-flash AA 40 → 39**,
**MiMo-V2.6-Pro AA 46 = the new score leader** (re-entered candidacy —
non-live 2026-09-25, live 1.83s on 2026-10-03), **Nemotron 3 Ultra AA 23 =
the free-tier baseline** this policy removes as a default. Seat-table rows
above are updated inline from this pull.

**User directives captured 2026-10-03 (same pass):**
1. Objective benchmark scores outrank family diversity — diversity is a
   soft tie-breaker only (council seats excepted as already specified).
2. Liveness gate: 15–20s cap on a trivial probe. A candidate that cannot
   answer `Reply with exactly: OK` within 20s is "not live for that check";
   never extend the timeout to rescue it (a 90s cap earlier that day
   produced a false "dead" reading for a model that answered in 2.3s under
   a healthy route).
3. Context: PLN is selecting an i18n reviewer on the Go lane from the same
   evidence; this Go-first bindings effort consumes it too.

**AA Intelligence Index — live pull 2026-10-03** (independent,
artificialanalysis.ai/leaderboards/models; replaces the stored 2026-09-25
AA v4.3.2 rows for these models; AA rows are reasoning-config-specific —
"max" etc. — a tier filter, not a ranking; gaps ≤2–3 are noise):

| Model (AA row) | AA II | AA $/task | AA t/s |
|---|---|---|---|
| MiMo-V2.6-Pro | 46 | $0.13 | 46 |
| GLM-5.3 (max) — hard-excluded (cost, 2026-10-01) | 45 | $2.01 | 71 |
| Qwen3.8 Max (0902) — expensive | 45 | $5.41 | 39 |
| Kimi K3 (max) — excluded 2026-10-03 (console disabled, cost) | 44 | $2.00 | 34 |
| GLM-5.3-Flash | 42 | $0.25 | 54 |
| Gemini 3.8 Flash (high) — Zen lane | 41 | $1.24 | 249 |
| Qwen3.8-Flash-Next | 40 | $0.37 | 54 |
| DeepSeek V4.1 Flash (max) | 39 | $0.27 | 209 |
| GPT-6 Luna (max) | 38 | $0.07 | 131 |
| MiMo-V2.6-Flash | 38 | $0.06 | 51 |
| GPT-5.6 Terra (xhigh) | 38 | $0.63 | 91 |
| DeepSeek V4 Pro (max) | 36 | $0.67 | 107 |
| MiniMax-M3 | 29 | $0.51 | 88 |
| Kimi K2.7 Code | 26 | $0.54 | 90 |
| Hy3 | 25 | $0.07 | 87 |
| Qwen3.7 Plus | 25 | $0.22 | 56 |
| Nemotron 3 Ultra | 23 | $0.60 | 164 |

**Go token prices** (docs, fetched 2026-10-03; per 1M tokens). AA $/task is
a cross-provider estimate — compute per-workload cost from measured tokens,
not from AA $/task.

| Go model | In | Out | Notes |
|---|---|---|---|
| MiMo-V2.6-Flash | $0.14 | $0.28 | |
| MiMo-V2.6-Pro | $0.435 | $0.87 | |
| GPT-6 Luna | $0.10 | $0.50 | ≤272K tier; `/responses` protocol only |
| GPT-5.6 Luna | $0.20 | $1.20 | `/responses` protocol only |
| Qwen3.8-Flash | $0.15 | $0.47 | |
| GLM-5.3-Flash | $0.15 | $0.50 | |
| DeepSeek V4.1 Flash | $0.15 | $0.60 | off-peak; peak $0.30/$1.20 Mon–Fri 01:00–04:00, 06:00–10:00 UTC; weekends off-peak |
| LongCat-2.0 | $0.30 | $1.20 | unbenched (no AA reading found) |
| Hy3 | $0.14 | $0.58 | |

**Liveness probes (2026-10-03, 20s cap) + endpoint facts.** Probe form:
`POST https://opencode.ai/zen/go/v1/chat/completions` (Go; `/zen/v1/*` for
Zen), **bare catalog IDs** (no lane prefix — config bindings keep their
`opencode-go/` prefix), `Authorization: Bearer $OPENCODE_API_KEY`,
`Content-Type: application/json`, **`x-opencode-session: <stable id>`
required**, body `{"model": M, "messages":[{"role":"user","content":"Reply
with exactly: OK"}], "max_tokens":16}`. Endpoint drift: the old
`https://opencode.ai/api/*` endpoints 404.

| Model | Result | Time |
|---|---|---|
| deepseek-v4.1-flash | 200 | 1.14s |
| glm-5.3-flash | 200 | 1.23s |
| qwen3.8-flash | 200 | 1.44s |
| longcat-2.0 | 200 | 1.53s |
| mimo-v2.6-pro | 200 | 1.83s |
| kimi-k3 | 200 | 1.91s |
| hy3 | 200 | 2.32s |
| mimo-v2.6-flash | 200 | 3.97s |
| gpt-6-luna | 400 `ModelProtocolUnsupported` | 0.23s |
| gpt-5.6-luna | 400 `ModelProtocolUnsupported` | 0.22s |

**Operational findings.** (a) GPT-6 Luna and GPT-5.6 Luna do not serve
`/chat/completions` (`ModelProtocolUnsupported`); the Go docs route them via
`https://opencode.ai/zen/go/v1/responses` — any OpenAI-compatible chat
client must account for this (OQ9). (b) Route degradation window 2026-10-03
~17:00–20:10 UTC: mimo-v2.6-flash full review → upstream 502 at 601s;
glm-5.3-flash full request → 0 bytes at 900s; qwen3.8-flash → 503 at 281s;
hy3 trivial probe → timeout at 90s. All cleared on the 20s re-probe later
the same day — transient load/provider flakiness, not model death, but
reliability under load is a watch item for the re-opened seats. (c) Framework
history carried forward: `gpt-6-luna` rejected on 3/3 CI canary failures
(2026-09-29 eval-lane pass); `mimo-v2.6-flash` on wall time (2× slower) in
the same pass. (d) Uncertainties from the pack land in OQ7–10: AA rows are
configuration-specific (gaps ≤2–3 are noise); the Qwen3.8-Flash-Next ↔
`qwen3.8-flash` mapping is unverified; LongCat-2.0 and Qwen3.8-Flash have no
AA reading (task-level evidence is not a benchmark substitute).

## Acceptance Criteria

1. **Every persona binds Go.** No `agents/*.md` `model:` line is `*-free` or
   `kimi-k3`; the new defaults from the table are in place. Verifier: new
   `scripts/test_model_policy.py` (hermetic, fixture-driven) exits 0 and
   `grep -rn "nemotron\|kimi-k3" agents/` returns nothing.

2. **Routing table tells one story.** `reference/model-routing.md`'s core
   table is restructured so the default column is Go and the free column is
   the documented opt-in; `kimi-k3` is added to hard exclusions (dated user
   cost directive) alongside glm-5.3/glm-5.2, and (extended 2026-10-03 (2))
   `gpt-6-luna` is added (dated 2026-10-03: 3/3 CI canary failures,
   2026-09-29 eval-lane pass) with the peak-tier note carried forward
   explicitly (the whole peak-pricing class — gpt-5.5 / gpt-5.5-pro and any
   $10/$50-tier ID — stays excluded); the exclusions section states they sit
   **above all scores** — a live probe or a high AA score never overrides an
   exclusion (kimi-k3 probes live at 1.91s and scores AA 44 and stays
   excluded); council seats and the free-tier section match the new
   bindings; the retrieval date is bumped. Verifier:
   `python3 scripts/model-liveness-check.py` exits 0 live (Go IDs present in
   the Go catalog, no excluded ID bound), and the policy test checks the
   table shape plus the exclusion list (`kimi-k3`, `glm-5.3`, `glm-5.2`,
   `gpt-6-luna`, peak-tier note, above-all-scores clause all present).

3. **Policy canary cannot drift.** `scripts/model-liveness-check.py` (or the
   policy test it invokes) fails on (a) a bound `-free` ID, (b) a bound
   hard-excluded ID (`kimi-k3`, `glm-5.3`, `glm-5.2`, `gpt-6-luna`, grok
   family, fable/astra/peak-tier class), (c) a routing-table Go cell absent
   from the live Go catalog. Extended 2026-10-03 (2) — (d) the liveness
   probe contract: probes use the trivial prompt `Reply with exactly: OK`
   with a **20s cap** (15–20s working rule) against
   `POST https://opencode.ai/zen/go/v1/chat/completions` (`/zen/v1/*` for
   Zen), **bare catalog IDs** (no lane prefix in the gateway request),
   and the required `x-opencode-session` header; a candidate that cannot
   answer within 20s is "not live for that check" — the timeout is never
   extended to rescue it, and the old `https://opencode.ai/api/*` endpoints
   are not used (they 404). Verifier: hermetic cases in
   `scripts/test_model_policy.py` feed fixtures for each failure class and
   assert non-zero (including a >20s responder classified not-live and a
   probe-shape fixture asserting endpoint + `x-opencode-session` + bare ID);
   the live canary runs green on `main` in the `model-liveness` workflow.

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
  opt-in), add `kimi-k3` and `gpt-6-luna` to hard exclusions with the
  peak-tier note and the exclusions-above-all-scores clause (2026-10-03 (2)),
  update council seats + provider notes + update procedure, bump the
  retrieval date (2026-10-03 AA rows: glm-5.3-flash 42, deepseek-v4.1-flash
  39, MiMo-V2.6-Pro 46).
- `docs/CONCEPTS.md` — §7c rewrite; scan Choice 7 for other free-first text.
- `reference/agent-teams.md`, `reference/opencode-integration.md`,
  `docs/COUNCIL.md` — lane/binding wording that assumes free-bound personas.
- `scripts/model-liveness-check.py` — policy assertions (no free bindings, no
  hard-excluded bindings, table/live consistency) and the 20s trivial-probe
  contract (`/zen/go/v1` / `/zen/v1`, bare catalog IDs, required
  `x-opencode-session`; never extend the timeout to rescue a candidate).
- `scripts/test_model_policy.py` — new hermetic test (fixture-driven failure
  classes incl. a >20s not-live case and a probe-shape assertion;
  `ci-lane-overrides` empty-agent assertion).
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

### Open Questions 7–10 — re-opened 2026-10-03 (2) by the evidence pack; resolved same day at the per-question gate

The 2026-10-03 live pull superseded the figures these four seats were
decided on. Each carries the pack's evidence and the user's 2026-10-03
decision. (Note: gaps ≤2–3 AA points are noise per the pack; scores outrank
family diversity per directive 1 above.)

7. **Quality seats (debugger / reviewer / skill-reviewer) —
   `mimo-v2.6-pro` vs `glm-5.3-flash`.** The row's stored basis ("AA 45")
   is superseded: live 2026-10-03 gives glm-5.3-flash AA 42 ($0.25/task,
   Go $0.15/$0.50, live 1.23s, 1M context), while MiMo-V2.6-Pro is the new
   score leader at AA 46 ($0.13/task — cheapest per task in the top band;
   Go $0.435/$0.87, live 1.83s) and re-entered candidacy (excluded
   2026-09-25 only for non-liveness). 46 vs 42 is above the noise band, and
   the 2026-10-03 directive puts scores ahead of diversity; glm-5.3-flash's
   counter-case is ~3× cheaper Go tokens and the 1M-context / defect-catch
   basis the row was built on (MiMo-Pro's context window is unverified).
   Reliability watch: glm-5.3-flash returned 0 bytes at 900s during the
   2026-10-03 degradation window (cleared on re-probe). Scope note: the
   architect/planner/curator row is not re-opened — its basis is KingBench
   91.25 and its AA 42 figure already matches the live pull. Resolved (user,
   2026-10-03): `opencode-go/mimo-v2.6-pro` on the score directive; recorded
   alt `glm-5.3-flash` (cost/context), reverting in if the 3-prompt seat
   validation or a context-window check disqualifies MiMo-Pro.

8. **Implementer / test-writer — `glm-5.3-flash` vs
   `deepseek-v4.1-flash`.** The stored basis ("AA 40, ~3× cheaper") is
   superseded: live pull gives deepseek-v4.1-flash AA 39 ($0.27/task; Go
   $0.15/$0.60 off-peak, peak $0.30/$1.20 Mon–Fri 01:00–04:00 and
   06:00–10:00 UTC) vs glm-5.3-flash AA 42 at comparable cost
   ($0.25/task). Case for glm-5.3-flash: +3 AA (at the noise edge — strict
   reading of "scores outrank diversity"), slightly cheaper tokens. Case for
   keeping deepseek-v4.1-flash: 209 t/s vs 54 t/s (wall time — the 2026-09-29
   pass rejected `mimo-v2.6-flash` on 2× wall time), repo-proven as the
   validated CI eval lane (3/3 probes), and a soft tie-breaker keeps
   implement/test-writing off the family holding the planning/quality seats.
   Scope note: this re-opens the persona bindings only — the CI eval lane
   (Excluded above) stays `opencode-go/deepseek-v4.1-flash` either way;
   `kimi-k2.7-code` stays the code-heavy escalation (AA 26, MCPMark 81.1).
   Resolved (user, 2026-10-03): keep `opencode-go/deepseek-v4.1-flash`
   (throughput + proven lane; the 3-point gap sits at the noise boundary);
   `glm-5.3-flash` stays the recorded alt.

9. **council-performance — `gpt-5.6-luna` verify-or-reseat (/responses
   protocol).** The 2026-10-03 probe returns 400 `ModelProtocolUnsupported`
   for `gpt-5.6-luna` on `/zen/go/v1/chat/completions` (0.22s): the Go docs
   serve these models only via `https://opencode.ai/zen/go/v1/responses`
   (AA 38; Go $0.20/$1.20). A raw chat-completions 400 does not prove the
   seat dead — the opencode runtime serving a bound
   `opencode-go/gpt-5.6-luna` may speak `/responses` natively — but no
   framework path has exercised that protocol, and the liveness canary's
   chat-completions probe must not misread it as death. Resolved (user,
   2026-10-03): **verify first** — bind `opencode-go/gpt-5.6-luna` and gate
   on the
   existing 3-prompt seat validation through the opencode path; on failure,
   reseat to `longcat-2.0` (live 1.53s, Go $0.30/$1.20, unbenched — task-
   level evidence only: PLN canary 8/8 reject, 59-key review pass, not a
   benchmark substitute) or fall back to a five-family council. `gpt-6-luna`
   is not a fallback — hard-excluded (3/3 CI canary failures) and shares the
   protocol limit.

10. **Council chairman — `qwen3.8-flash` identity (Qwen3.8-Flash-Next
    mapping).** The pack's AA pull lists "Qwen3.8-Flash-Next" at AA 40
    ($0.37/task, 54 t/s); its mapping to the Go catalog ID `qwen3.8-flash`
    is unverified. If they are the same model, the chair is not "unbenched"
    and the seat basis changes from cost-only to measured (AA 40; live
    1.44s; Go $0.15/$0.47). Supporting evidence: Qwen3.8 Max (0902) is AA 45
    at $5.41/task (confirms the user's cost challenge against max);
    `qwen3.8-flash` 503'd at 281s during the 2026-10-03 degradation window
    (cleared on re-probe — reliability watch). Resolved (user, 2026-10-03):
    keep `opencode-go/qwen3.8-flash` and verify the mapping during
    implementation (vendor/docs check; record the result in History) — the
    2026-10-03 cost directive and the 3-prompt seat-validation gate hold
    either way; the fallback stays `gpt-5.6-luna` as chairman (subject to
    OQ9's protocol verification) with the performance seat re-opening.

## History

- 2026-10-03 — per-question gate (user): OQ7–10 settled — quality seats
  (debugger/reviewer/skill-reviewer) → `opencode-go/mimo-v2.6-pro` (AA 46
  score leader; recorded alt `glm-5.3-flash` reverts in on failed seat
  validation / context-window check), implementer/test-writer keep
  `deepseek-v4.1-flash`, council-performance verify `gpt-5.6-luna` first
  (3-prompt seat validation via the opencode path; reseat `longcat-2.0` or
  five families only on failure), chairman keep `qwen3.8-flash` +
  Qwen3.8-Flash-Next mapping check in implementation. All ten Open Questions
  resolved; status → approved. Implementation stays queued behind RM-021 and
  `run-vehicle-visibility`.
- 2026-10-03 — revision (2), user-requested design pass: absorbed the
  2026-10-03 peer-evidence pack (gitignored `.scratch/dispatch/
  pln-model-peer-evidence-2026-10-03.md`) into Goal/Approach as the copied
  evidence basis — AA live pull, Go token prices, 20s-capped probe table,
  three user directives, endpoint facts, operational findings. Supersessions
  applied inline: glm-5.3-flash AA 45→42, deepseek-v4.1-flash AA 40→39,
  MiMo-V2.6-Pro AA 46 = new score leader (candidacy re-opened), Nemotron 3
  Ultra AA 23 = free-tier baseline. Four seat decisions re-opened as OQ7–10
  (quality seats mimo-v2.6-pro vs glm-5.3-flash; implementer/test-writer
  glm-5.3-flash vs deepseek-v4.1-flash; council-performance gpt-5.6-luna
  /responses verify-or-reseat; chairman qwen3.8-flash Qwen3.8-Flash-Next
  mapping), each with the pack's evidence and a proposed default; the four
  seat-table rows marked provisional. AC2/AC3 extended: hard exclusions gain
  `gpt-6-luna` (3/3 CI canary failures) plus the peak-tier note, framed
  above all scores; AC3 gains the 20s trivial-probe rule and the
  `/zen/go/v1` endpoint facts (`x-opencode-session` required, bare catalog
  IDs). Status → draft pending per-question approval of OQ7–10.
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

- 2026-10-04 — implementation on `feat/go-first-model-bindings` (this pass;
  the working-tree round-2 revision is the staged approved revision). All
  AC1–AC9 delivered. Verification: `python3 scripts/model-liveness-check.py`
  exits 0 live (policy assertions + catalogs/docs); `scripts/test_model_policy.py`
  17/17 hermetic cases green (AC1–AC4, AC7, incl. the AC3(d) probe contract);
  full offline suite green (`test_eval_workflows`, `test_agent_dispatch`,
  `test_dispatch_agent`, `test_runner`, `test_registry`, `validate_skill.py
  --all`, observing-runs suites, typed-eval check, yamllint); the policy grep
  shows only exclusion/opt-in mentions.

  **AC evidence.** (1) all 17 persona bindings are the planned Go defaults; no
  `-free`/`kimi-k3` in `agents/`. (2) routing table restructured (Go default
  column / free opt-in column); hard exclusions gained `kimi-k3` + `gpt-6-luna`
  with the peak-tier note and the exclusions-above-all-scores clause. (3)
  canary enforces no-free / no-excluded / table-catalog consistency; the 20s
  probe contract (bare IDs, `x-opencode-session`, `/zen/go/v1`) is
  hermetic-tested incl. >20s not-live, protocol-unsupported≠death, and
  timeout-never-extended. (4) CONCEPTS §7c + Choice 10 rewritten; routing
  documents `AI_FRAMEWORK_FREE_TIER=1` + per-session switch as the only free
  paths; runner tests green. (5) council: six seats / six families, changed
  seats validated. (6) ADR-0013 accepted; ADR-0002/0007 superseded with
  pointers; index updated; ADR-0001 carries a dated superseded-premise note.
  (7) `ci-lane-overrides.py` docstring updated; its output for this repo is an
  empty `agent` map with the `/tmp` permission block kept; workflow comments
  updated. (8) consumer propagation verified — excel 17 / marvin 18 / paragon
  23 reachable bindings, all Go, no free/excluded, all catalog-live; marvin
  `npm test` 196/196. (9) ROADMAP RM-039 + RM-040 (2026-11-01 review trigger)
  added.

  **Seat validations (opencode path, run-vehicle dispatches).**
  - chairman `opencode-go/qwen3.8-flash`: 3/3 prompts answered (trivial OK; a
    two-lens synthesis; a five-lens question list). One run dispatched a
    nested fast council (3 Go seats) and synthesized — nested Go dispatch
    works.
  - performance `opencode-go/gpt-5.6-luna`: 3/3 answered through opencode
    (trivial OK; N+1/index concerns; cache comparison) — OQ9 passes, no reseat
    to `longcat-2.0`; the raw chat-completions 400 is gateway-protocol-specific,
    not model death.
  - quality seats `opencode-go/mimo-v2.6-pro` (debugger/reviewer/skill-reviewer):
    context-window check passes (models.dev `opencode-go/mimo-v2.6-pro`
    1,048,576 tokens) and role-shaped prompts answered correctly (a blocker
    authz-bypass finding; an environment-class root cause). Two first-attempt
    reviewer dispatches with heartbeat injection were distorted by run-vehicle
    supervision interactions (one ended empty after a bash `date` auto-reject
    and, with no `--contract` passed, was still recorded `success`; one hit
    the 240s timeout mid-process) — agent posture, not the seat; clean retries
    without heartbeat injection answered correctly. OQ7 alt `glm-5.3-flash`
    not needed.
  - OQ10 mapping: Go catalog `qwen3.8-flash` displays as "Qwen3.8 Flash"
    (opencode Go docs); the canonical upstream model for that family is
    `Qwen/Qwen3.8-Flash-Next` (HF) and no conflicting flash variant exists —
    corroborated, not vendor-explicit; the seat basis (cost directive +
    validation) holds either way.
  - Live routing proof: `dispatch_agent.py --agent reviewer` with no `--model`
    printed `binding=opencode-go/mimo-v2.6-pro`, session-resolved
    `model=opencode-go/mimo-v2.6-pro`, and emitted one `kind=agent` record
    with that model (outcome success).

  **Mechanical deviations (Step 4).** The flip necessarily updated policy
  surfaces and tests the plan did not enumerate: `scripts/test_eval_workflows.py`
  (override map is now empty), `scripts/test_agent_dispatch.py` and
  `scripts/test_dispatch_agent.py` (old bindings / example model),
  `skills/optimizing-model-routing/SKILL.md` (the plan's "sweep every policy
  text" mandate — Step 5/8 taught free-first), and the dated ADR-0001 note
  (AC6 "no ADR claims a free-first default"). No contract change.

  **Follow-ups.** (a) Wire `scripts/test_model_policy.py` into the CI offline
  suite (ci.yml was outside this plan's workflow scope, which allowed
  comments-only edits to the three named workflows). (b) Re-align the
  `optimizing-model-routing` deferred evals/fixture — the miniframework still
  encodes its own free-default policy. (c) Heartbeat injection + bash-`ask`
  personas interact badly in non-interactive run-vehicle dispatches (two
  reviewer seat-validation attempts were distorted this way), and an empty
  final result without `--contract` is still recorded `success` — consider
  requiring a contract for seat validations. (d) Consumer-repo commits
  left to the repo owners (working trees updated and verified; diffs in the
  handoff).

  UX consult: no user-facing UI — council-ux consult skipped (unchanged from
  design).

PR: https://github.com/hierovision/ai-framework/pull/96 (user merges; squash-only).
