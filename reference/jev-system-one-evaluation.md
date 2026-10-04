# Jev (TypeSafe AI "System One") — future-fit evaluation

**evaluated 2026-10-03; review-by 2027-01-31.** Re-verify the volatile
facts (docs.typesafe.ai, the Zen and Go catalogs) on touch. This is the
durable residue of plan `jev-system-one-evaluation` (approved 2026-10-03,
deleted at close per ADR-0008; git history holds the plan). Adoption
status: **not adopted** — one advisory candidate survives the filter
(matrix row 3), trigger-gated in `docs/ROADMAP.md` RM-041; every other
decision point drops with a recorded reason.

## Facts (verified 2026-10-03)

- **What it is.** TypeSafe AI "System One" decision model, not a chat
  model. Send a `state` (text/JSON) plus typed `questions`; receive a value
  + probability per question, evaluated in parallel against the same state.
  Question types: `noul` (yes/no → probability 0–1, no separate
  confidence), `choice` (criteria map → selected key + per-key
  probabilities + confidence), `score` (ordered rubric → numeric score +
  per-level probabilities + confidence + legend).
- **IDs / pricing.** `jev-1.13` ($0.042 per 1M input tokens, output free)
  and `jev-1.13-free` (limited-time free). Underlying versioned ID
  `jev-1.13.0`; vendor aliases `jev-latest` / `jev-preview` move — pin the
  versioned ID in any future integration.
- **Endpoint / tier.** Zen only — `https://opencode.ai/zen/v1/systemone`,
  Zen API key. The Zen catalog (`https://opencode.ai/zen/v1/models`) lists
  both `jev-1.13` and `jev-1.13-free`; the Go catalog
  (`https://opencode.ai/zen/go/v1/models`, 36 IDs fetched 2026-10-03) lists
  **zero** jev entries; the docs endpoint table
  (`https://opencode.ai/docs/zen/` §Jev) binds both IDs to the `systemone`
  endpoint with no AI SDK package (`-`). **Never an agent `model:`
  binding.**
- **Limits (vendor-stated).** 64k context per request (32k for `state` plus
  the longest question); text-only input; 100K tokens/s and 80 requests/s,
  "adjusting dynamically"; 429 on excess.
- **Documented weaknesses** (docs.typesafe.ai jaggedness page, vendor,
  reviewed 2026-10-02). Literal reading; unreliable counting/arithmetic;
  unreliable date comparison; accuracy falls with indirection hops;
  accuracy falls as state grows with irrelevant detail; **adversarial
  content in state can steer the answer**; contradictory
  instructions/criteria confuse it; choice option-order bias (leans first);
  not trained to generate.
- **Confidence semantics (vendor docs).** choice confidence =
  (p_max − 1/n)/(1 − 1/n); score confidence accounts for distance from the
  peak level; `noul` carries no confidence — threshold the probability
  itself. Vendor pattern: high → act, medium → flag, low → route to human.
- **Privacy (Zen docs §Privacy).** "Jev APIs: Prompts and other inputs are
  not used for training. Data is retained in accordance with TypeSafe AI's
  Privacy Policy." The free variant is listed as limited-time with no
  training-use exception noted (unlike Big Pickle / Fledge / MiMo / Ling /
  Nemotron free entries). This repo is public — never send secrets or
  consumer data regardless.
- **Community precedents (weighed, not copied).**
  - `purplesmoke05/opencode-plugin-jev-auto-model-router` (MIT, beta) —
    per-turn typed model selection with sticky pin at confidence ≥ 0.99,
    single-shot no-retry, fail-open to a configured fallback; uses the
    direct TypeSafe API (`TYPESAFE_API_KEY`), not the Zen endpoint.
  - `aaronshaf/opencode-jev-orchestrator` (MIT, npm) — sticky cheap parent,
    Jev flags hard/easy/unsure, escalation via child subagents;
    Go-oriented.
  - TypeSafe official skill/MCP + SDKs and cookbooks (guardrails, citation
    checking, RAG-passage classification, self-consistency → route
    uncertain nouls to human review). The self-consistency and
    confidence-gating patterns are the design idioms worth borrowing if
    the keep candidate is ever built.

## Probe log (2026-10-03, this evaluation session)

Credential: Zen key from `~/.local/share/opencode/auth.json` (provider
`opencode`), read into `$KEY` in-shell; never printed, never recorded.
`OPENCODE_API_KEY` env was unset. Model: `jev-1.13-free` (preferred per the
brief; no paid call was needed). State text in both probes was synthetic,
derived from public repo content only.

Command shape (both probes):

```
curl -s -m 60 -w '\nHTTP_STATUS:%{http_code}' \
  https://opencode.ai/zen/v1/systemone \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"jev-1.13-free","state":"<synthetic public-repo text>","questions":{...}}'
```

Probe 1 — choice + noul (state: the RM-021 weekly-run failure summary,
public ROADMAP text). Questions: `failure_class` (choice: infra/content/mixed),
`quarantine_warranted` (noul). Result: **HTTP 200, 472 ms**, verbatim:

```json
{"model":"jev-1.13-free","answers":{"failure_class":{"type":"choice","choice":"infra","confidence":1,"probabilities":{"infra":1,"content":0,"mixed":0}},"quarantine_warranted":{"type":"noul","noul":0.62}},"usage":{"input_tokens":462,"output_tokens":61}}
```

Probe 2 — score (state: a generic council-review description). Question:
`actionability` (score: Not/Partially/Fully actionable). Result: **HTTP 200,
336 ms**, verbatim:

```json
{"model":"jev-1.13-free","answers":{"actionability":{"type":"score","score":1.01,"confidence":0.98,"legend":{"0":"Not actionable","1":"Partially actionable","2":"Fully actionable"},"probabilities":{"0":0,"1":0.99,"2":0.01}}},"usage":{"input_tokens":334,"output_tokens":20}}
```

Observations for future use: sub-second latency; 334–462 input tokens per
call; the choice answer lands on the correct class (infra — matching the
RM-021 recorded diagnosis) with confidence 1.0; the noul returns a
calibrated mid-range 0.62 rather than forcing a binary. Both answers were
plausible and typed — the API contract works as documented from this
environment with the existing Zen credential.

## Candidate matrix

Filter: keep only where a typed probabilistic judgment concretely saves a
judgment (human/LLM reading time) or a mistake class (misdiagnosis,
false-green) **and** the current mechanism leaves that residue. Anti-goals
enforced: no generation/coding proposals; nothing a deterministic check
already settles; no novelty.

| # | Decision point | Current mechanism | Verdict | Fit reasoning (vs filter) | Integration form (if kept) | Adoption trigger / re-open signal |
|---|---|---|---|---|---|---|
| 1 | Model routing / escalation (role→model) | Static, dated, user-approved role table + liveness/bench candidate gate (`reference/model-routing.md`, `skills/optimizing-model-routing/SKILL.md`); community precedent = per-turn router plugins | **Drop** | Per-turn dynamic routing moves a binding decision from an approval gate (AGENTS.md rule 2) to an automated oracle; go-first bindings make Go the default for every role, removing the cheap/expensive per-turn asymmetry the community routers exploit; per-turn routing would send user prompt text (possibly consumer-repo content) to a third-party API; the router plugin uses the direct TypeSafe API + `TYPESAFE_API_KEY`, a credential surface this repo does not carry. No mistake class evidenced — routing errors are caught by the liveness canary and the approval gate | none — plugin/hook form rejected outright | Re-open only if Go allowance exhaustion (5-hr/weekly/monthly caps; model-routing Provider notes) becomes a measured recurring problem **and** a deterministic run-log projection proves insufficient — the projection is arithmetic, so it nearly always suffices |
| 2 | Eval failure taxonomy: infra-vs-content split | Deterministic: `outcome=error` → infra, `outcome=failure` → content; dead-stream = all-error events; signature aggregation (`scripts/eval-report.py failure-taxonomy`, RM-021) | **Drop** | A deterministic check already settles it (anti-goal). Probe 1 confirms Jev *could* classify it (choice=infra, confidence 1.0) but adds cost, latency, and a network dependency where event-type inspection is exact | none — deterministic-settled | `None — deterministic-settled` (event-type inspection is exact); would re-open only if the deterministic signal itself disappears (RM-026 upstream: sessions with zero log lines) **and** stream text remained — then a text-classifier fallback becomes the only option |
| 3 | Content-failure triage *within* the red list (why did this eval miss?) | Human/LLM reads persisted streams per failure (RM-021: 31 content failures in run 36485564689; retune batches found by reading) | **KEEP** | Saves both a judgment (human stream-reading per weekly red) and a mistake class (wording-drift misread as skill regression, or a real regression retuned away — the RM-021 five-expect retune batch is the evidenced error). Not settled deterministically: the infra/content split stops at "content"; the *why* is open judgment. Advisory only — never gates | planned `scripts/jev_decide.py` (stdlib `urllib.request`, no new dependency; build per sketch below) + `scripts/eval-report.py failure-taxonomy --jev-triage` advisory enrichment | T1: a `jev-*` ID appears in the Go flat-rate catalog (checked at the next optimizing-model-routing catalog fetch). T2: `jev-1.13-free` still live (re-probe per the model-routing update procedure) **and** two consecutive post-RM-021 weekly runs each leave ≥10 content failures requiring human stream-reading (checked from failure-taxonomy artifacts) **and** the user accepts the free variant's data terms. T3: dated user directive approving Zen PAYG spend (measured <$0.01/weekly run) + a Zen CI secret |
| 4 | Quarantine flips + green-run qualification | Deterministic counters: 3 consecutive fails → quarantined, 3 passes → rehab (`scripts/quarantine.py`); 4-condition green-run check (`reference/eval-green-run-definition.md`) | **Drop** | Deterministic checks already settle both (anti-goal). A probabilistic input to a gate counter would violate the fail-open rule and the cardinal rule (never green a check by weakening the net) | none — deterministic-settled | `None — deterministic-settled` (consecutive counters + the 4-condition check); re-opens only if those mechanics are removed |
| 5 | Dispatch retry / vehicle-switch classification | Signal-regex classification (transient: `[server_error]`, timeout; deterministic: `invalid_request_error`, model-resolution) + bounded sequence retry→switch→inline (`reference/delegated-result-contract.md`, RM-024) | **Drop** | The bounded sequence caps the cost of a misclassification at ≤2 wasted retries; adding a network call *inside* the retry path creates the dependency the contract exists to survive; the real gap (RM-026: some sessions log zero lines) is upstream and unclassifiable from text that does not exist | none — deterministic-settled | Re-open only if RM-026 lands with logs present but signatures unmatchable by regex **and** mis-retry cost becomes measured (run-log retry counts) |
| 6 | Changed-file → skill mapping (per-change gate) | Deterministic first-match-wins table with a safe harness fallback, by design (`scripts/changed-files-to-skills.py`, `reference/three-layer-gating.md`) | **Drop** | Deterministic by explicit design ("Ambiguous: the fixed harness set is the safe fallback"); a required PR check must never consult an external paid API (gate-blocking + secret in CI + third-party outage becomes a CI outage) | none — deterministic-settled | `None — deterministic-settled` (first-match-wins table + safe fallback); re-opens only if the table is removed |
| 7 | Coverage-gap judgments | Deterministic counts: zero-eval skills, deferred, quarantined, legacy assertions (`skills/observing-runs/scripts/query_runs.py` `coverage_gaps`) | **Drop** | Counting is the documented Jev anti-pattern ("if a regex or parser can find it, the count belongs in code"); gaps are enumerated, not judged | none — deterministic-settled | `None — deterministic-settled` (enumeration in `coverage_gaps`); re-opens only if gap detection stops being enumerable |
| 8 | Triage scoring (impact × urgency) | LLM chat pass with an explicit 1–9 rubric, human confirms cuts (`skills/triaging-requirements/SKILL.md` Step 6/8) | **Drop** | The pass is already human-confirmed and rubric-explicit; cadence is low (per triage); a second scorer adds a disagreement-resolution step without removing the human judgment — no concrete saving | none — chat pass is the mechanism | Re-open if triage volume grows past human confirmation (e.g. managing-github-issues syncing hundreds of rows) — observable from row counts |
| 9 | Issue-refinement AC quality checks | Chat-model rewrite pass against the observable+verifier bar (`skills/refining-issue-acceptance/SKILL.md`) | **Drop** | The chat pass *is* the mechanism; a Jev pre-screen would be two models doing one job on text the chat model must read anyway. The AC-quality judgment needs repo-context reasoning (which verifier commands exist), an indirection hop Jev is documented to weaken on | none — chat pass is the mechanism | Re-open if batch refinement of ≥50 issues becomes routine and a cheap pre-filter shows measured savings |
| 10 | Review / security / a11y finding triage | Review severity = mechanical table (`skills/reviewing-code/SKILL.md` via CONTRIBUTING); a11y = axe rule output + needs-manual-verification bucket (`skills/auditing-accessibility/SKILL.md`); security = traced candidate triage (`skills/reviewing-security/SKILL.md`) | **Drop** | Review and a11y triage are rule-structured (anti-goal: deterministic). Security triage is multi-hop reasoning over traces — Jev's documented weak shape — and the `state` would contain adversarial content (injection payloads, exploit text), the documented steering weakness, in a public repo. A steerable oracle on security verdicts is a false-green risk, not a saving | none — rule-structured / unsafe state | Re-open only if TypeSafe ships a documented adversarial-state hardening (a jaggedness-page revision) **and** a traced-finding benchmark shows calibration — both observable in vendor docs |
| 11 | Council lens confidence / disagreement resolution | Chairman synthesizes; disagreements surfaced, never averaged away (`docs/COUNCIL.md`, `agents/council.md`, model-routing "always surface disagreements") | **Drop** | Policy conflict: the repo deliberately surfaces disagreement to humans instead of resolving it mechanically; a probability oracle resolving lens disputes is exactly the silent override the policy forbids. Lens findings are prose arguments — compressing them to questions loses the trace that makes them reviewable | none — policy forbids mechanical resolution | Re-open only by an explicit user policy reversal (dated directive) |

## Keep-candidate integration sketch (row 3 — for the trigger-fired session, cold)

- **Script contract.** Repo script, stdlib only. `scripts/jev_decide.py`:
  `urllib.request` POST to `https://opencode.ai/zen/v1/systemone`; key
  resolution order `$OPENCODE_API_KEY` → `~/.local/share/opencode/auth.json`
  provider `opencode` (never printed); `--model` default `jev-1.13`
  (versioned ID, not the moving alias); `--timeout` default 10 s; CLI:
  single attempt, no retry (the router-plugin discipline); stdout = answers
  JSON; exit 0 = answered, non-zero = any failure.
- **Consumer change.** `scripts/eval-report.py failure-taxonomy
  --jev-triage` adds, per content failure, an advisory `jev_triage` block;
  on any Jev failure the block is `{"status": "unavailable:<reason>"}` and
  the report still emits — **fail-open, never gates** a run, a quarantine
  flip, or the green-run check (cardinal rule: Jev output can never green
  or red anything).
- **Typed question shape (choice, criteria verbatim).**
  `{"type":"choice","instructions":"Classify the most likely reason this
  behavioral eval failed on content, from the repo's own artifacts.",
  "criteria":{"skill_regression":"The skill's behavior genuinely broke
  against its documented contract","assertion_wording_drift":"The skill
  behaved correctly but output wording no longer matches the expected
  phrase","prompt_or_fixture_defect":"The eval prompt or fixture is
  malformed, stale, or ambiguous","environment":"Provider, network, or
  harness plumbing not already classified as infra","unclear":"State is
  insufficient to classify"}}` — plus `unclear` as the honest-exit option
  (self-consistency cookbook idiom: low-confidence/unclear → human, never
  acted on).
- **State budget.** Per failure — eval id, skill name, the `expect` block,
  the final agent output tail, and the assertion-diff detail, truncated to
  ≤ 8k chars (well inside the 32k state limit; jaggedness rule: send only
  what the question needs).
- **Privacy rule.** Public-repo content only; never consumer data, never
  secrets. The HTML/JSON state never carries credentials.
- **Cost estimate.** ~340–470 input tokens per call → ~$0.00002/call paid;
  a 30-failure weekly red list ≈ $0.0006–0.001 (<$0.01/run even 10×);
  `jev-1.13-free` = $0 while it lasts (limited-time).
- **Latency estimate.** 0.3–0.5 s/call → ~15 s serial for 30, inside the
  weekly job's budget; the 80 req/s cap allows parallelism if ever needed.
- **Verification at build time.** Hermetic tests with a stubbed HTTP layer
  (repo pattern `scripts/test_eval_report.py`); one live probe recorded in
  the PR description per the model-routing escalation-gate convention; a
  negative test asserting the report emits unchanged when Jev is
  unreachable.

## Lifecycle

The anti-rot mechanic (user requirement, 2026-10-03): this doc is durable
only while Jev is live and unevaluated-in-place. Deletion triggers — the
doc is removed and RM-041 closes when any one fires:

- **D1 — model retired.** No `jev-*` ID is live in the Zen catalog.
  Enforced mechanically by the `scripts/model-liveness-check.py` D1 alarm:
  with this doc present and zero live `jev-*` IDs in the Zen catalog, the
  canary fails with the remedy "delete the doc + close RM-041".
- **D2 — adopted.** An adoption trigger (T1–T3 in RM-041) fired and the
  integration shipped; the essence moves to the integration's docs.
- **D3 — rejected/superseded.** The candidate is rejected or superseded at
  a `triaging-requirements` pass or the ALM review; close with a dated
  rejection note.
- **D4 — review-by reached.** 2027-01-31 arrives without D1–D3: re-verify
  the volatile facts (docs.typesafe.ai + the Zen catalog) and either
  refresh the dates or delete the doc.
