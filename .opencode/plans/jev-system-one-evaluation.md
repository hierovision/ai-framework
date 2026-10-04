---
slug: jev-system-one-evaluation
title: Jev (TypeSafe System One) future-fit evaluation — durable record, trigger-gated, no adoption now
status: approved
created: 2026-10-03
revised: [2026-10-03, 2026-10-04]
related: [go-first-model-bindings]   # additive only; this plan never modifies its decisions
---

# Plan: jev-system-one-evaluation

## Goal / Approach

**Goal:** record a durable, trigger-gated future-fit evaluation of Jev
(TypeSafe AI "System One") for this repo — verified Zen-only, one surviving
advisory candidate, no adoption now — so a future session can pick any
candidate up cold and no routing pass ever mis-binds Jev as a chat model.

**Approach:** docs-only evaluation residue; no code, no CI, no binding
changes. The design session (2026-10-03) verified the tier (live Zen + Go
catalog fetches + the docs endpoint table), ran two live probes against
`jev-1.13-free` with synthetic public-repo state, and scored every decision
point named in the design brief against the filter "would this concretely
save a judgment or a mistake class?" — one candidate survives (advisory
content-failure triage in the weekly eval report), the rest drop with
recorded reasons. The implementation pass extracts the Evaluation Record
below into a dated reference doc, lands one trigger-gated ROADMAP row, and
adds an anti-mis-binding note to `reference/model-routing.md`. Jev is
additive to the in-flight `go-first-model-bindings` effort: this plan
touches no role row, no `agents/*.md`, and no decision that plan owns.

No stack reference applies — framework-internal docs and Python tooling
(same disposition as `run-vehicle-visibility.md`).

**Tier verdict (verified 2026-10-03, stated per the brief):** Jev is a
**Zen endpoint model, not a Go flat-rate model**. The Zen catalog
(`https://opencode.ai/zen/v1/models`) lists `jev-1.13` and `jev-1.13-free`;
the Go catalog (`https://opencode.ai/zen/go/v1/models`, 36 IDs fetched
same-day) lists **zero** jev entries; the docs endpoint table
(`https://opencode.ai/docs/zen/` §Jev) binds both IDs to
`https://opencode.ai/zen/v1/systemone` with no AI SDK package (`-`) — it is
not a chat-completions/messages/responses model, so it can never be an
agent `model:` binding. The repo's strategy is Go-default (Go Plus flat
rate). Therefore: future-fit evaluation, not adoption.

## Practical Result (human view)

For: the framework owner.

- **Before** — Jev appears in the opencode console model toggles, but
  nothing in the repo records what it is, whether it is Go or Zen, or
  whether any repo mechanism should use it. A future session could burn a
  pass re-investigating, or a routing pass could try to rank it as a chat
  model and fail on the `systemone` endpoint shape.
- **After** — one dated reference doc (`reference/jev-system-one-evaluation.md`)
  answers "what is it, does it fit anywhere, and what would re-open that":
  verified facts, the probe log with verbatim responses, an 11-row
  candidate matrix (1 keep, 10 drop, each with the filter reasoning and a
  re-open trigger), and a cold-pickup integration sketch for the survivor.
  One trigger-gated ROADMAP row (RM-041) watches the triggers. One note in
  `reference/model-routing.md` makes jev-* structurally unbindable as a
  role. Zero spend, zero new dependencies, no code, no CI change.
- **Value + how they judge it** — judge by reading the reference doc cold:
  within ~10 minutes you should be able to say "adopt / don't adopt, why,
  and which observable signal re-opens it", without opening this plan or
  re-probing. The ROADMAP row's triggers each name their own verification
  mechanism, so a future triage pass can check them mechanically.
- **What it asks of them** — approve this plan; review a 4-file docs-only
  diff at implementation (branch `feat/jev-system-one-evaluation` per
  `reference/git-workflow.md` derivation). No secrets, no spend, no
  service. If a trigger fires later, re-opening is a design pass, and
  adoption requires an ADR (new external API dependency + CI secret) and
  explicit spend approval — both noted in the row, neither requested now.

## Acceptance Criteria

The criteria verify the **evaluation and its durable residue**, not an
implementation of Jev anything.

1. **Zen-only tier verdict recorded with catalog evidence.** The durable
   doc states: both jev IDs present in the Zen catalog, zero jev entries in
   the Go catalog, the `systemone` endpoint + no-AI-SDK-package fact, and
   the fetch date. Verifier: `grep -c "zen/go/v1/models" reference/jev-system-one-evaluation.md`
   ≥ 1 and the §Facts block names both IDs, both catalog URLs, and the
   date 2026-10-03.
2. **Probe log recorded, key-free.** Two probe records (choice+noul;
   score) each carry: the exact command with the credential redacted to
   `$KEY`, model ID, HTTP status, wall latency, verbatim response JSON, and
   token usage. Verifier: §Probe log shows two HTTP 200 records with
   response bodies; `grep -nE "Bearer [A-Za-z0-9]|\"key\"" reference/jev-system-one-evaluation.md`
   matches nothing (only the `$KEY` placeholder appears).
3. **Candidate matrix complete against the brief.** Every decision-point
   family named in the design brief (routing/escalation; failure taxonomy;
   quarantine + green-run; dispatch retry/vehicle; changed-file mapping +
   coverage gaps; triage scoring + issue refinement; review/security/a11y
   finding triage; council disagreement) appears as ≥1 row, each with five
   non-empty cells: current mechanism (with file citation), verdict, fit
   reasoning vs the filter, integration form, adoption trigger. Verifier:
   §Candidate matrix has ≥ 8 rows (11 drafted); every cited file path
   resolves (`ls` each); no row has an empty cell.
4. **The keep candidate is cold-pickup-able.** The surviving candidate
   (advisory content-failure triage) carries an integration sketch
   sufficient to build from without re-reading this plan: script contract
   (stdlib HTTP, CLI, exit codes, fail-open rule), consumer change
   (`failure-taxonomy` advisory field), the typed question shape (choice
   criteria verbatim), state budget, privacy rule, and cost + latency
   estimates derived from the measured probe data. Verifier: §Keep-candidate
   sketch contains all seven elements; reviewer records the cold-read
   judgment at review time.
5. **Every drop row states its filter reason and a re-open signal.** Each
   drop row's trigger cell names an observable signal (a catalog fetch
   result, a measured failure count, a dated user directive, an upstream
   fix landing) or an explicit `None — deterministic-settled` with the
   mechanism that settles it; none says "revisit later". Verifier: read
   each drop row's trigger cell against that rule;
   `grep -c "revisit later" reference/jev-system-one-evaluation.md` = 0.
6. **Durable residue landed, go-first untouched.** `docs/ROADMAP.md` gains
   the RM-041 row (trigger-gated per the swamp guards, citing the reference
   doc, noting adoption-requires-ADR); `reference/model-routing.md` gains
   the additive non-chat-models note (never a role-binding candidate).
   Verifier: `grep -n "jev" docs/ROADMAP.md` shows a row containing
   `**Trigger**`; `grep -n "jev" reference/model-routing.md` shows the
   exclusion note; `git diff origin/main...HEAD -- reference/model-routing.md`
   shows no change inside the Core routing table, Hard exclusions table, or
   any role row, and `git diff --name-only origin/main...HEAD` contains no
   `agents/*.md`.
7. **No adoption build.** Verifier: `git diff --name-only origin/main...HEAD`
   lists only `docs/ROADMAP.md`, `reference/model-routing.md`,
   `reference/jev-system-one-evaluation.md`, `scripts/model-liveness-check.py`
   (the D1 alarm), and `.opencode/plans/jev-system-one-evaluation.md` (the
   plan file itself, deleted at close per ADR-0008); nothing else under
   `scripts/`, `.github/`, `skills/`, or `registry.json`; the CONTRIBUTING
   gate battery (Verification section) exits 0.

8. **Anti-rot lifecycle: the evaluation deletes itself when stale (user
   requirement, 2026-10-03).** The reference doc carries the dated header
   and a `## Lifecycle` section stating deletion triggers D1–D4; the RM-041
   row carries the same D1–D4 in its trigger cell (swamp-guard rule: the
   anti-rot mechanic lives in the row); and
   `scripts/model-liveness-check.py` gains the mechanical **D1 alarm** —
   with the doc present, zero live `jev-*` IDs in the Zen catalog fails the
   canary with the remedy "delete the doc + close RM-041". Verifier: the
   canary exits 0 on `main` today (jev-1.13 live); a stub-catalog fixture
   exercises the failure path; the doc and row are grep-checked for D1–D4,
   `evaluated 2026-10-03`, and `review-by 2027-01-31`.

## Evaluation Record

Authoritative draft — the implementation pass extracts this section into
`reference/jev-system-one-evaluation.md` (dated header "evaluated
2026-10-03; re-verify volatile facts on touch"), condensing prose but
preserving every fact, verdict, reason, and trigger.

### Facts (verified 2026-10-03)

- **What it is:** TypeSafe AI "System One" decision model, not a chat
  model. Send a `state` (text/JSON) plus typed `questions`; receive a value
  + probability per question, evaluated in parallel against the same state.
  Question types: `noul` (yes/no → probability 0–1, no separate
  confidence), `choice` (criteria map → selected key + per-key
  probabilities + confidence), `score` (ordered rubric → numeric score +
  per-level probabilities + confidence + legend).
- **IDs / pricing:** `jev-1.13` ($0.042 per 1M input tokens, output free)
  and `jev-1.13-free` (limited-time free). Underlying versioned ID
  `jev-1.13.0`; vendor aliases `jev-latest`/`jev-preview` move — pin the
  versioned ID in any future integration.
- **Endpoint / tier:** Zen only — `https://opencode.ai/zen/v1/systemone`,
  Zen API key. Zen catalog lists both jev IDs; Go catalog
  (`https://opencode.ai/zen/go/v1/models`, 36 IDs) lists none; docs
  endpoint table shows no AI SDK package. Never an agent `model:` binding.
- **Limits (vendor-stated):** 64k context per request (32k for `state`
  plus the longest question); text-only input; 100K tokens/s and 80
  requests/s, "adjusting dynamically"; 429 on excess.
- **Documented weaknesses (docs.typesafe.ai jaggedness page, vendor,
  reviewed 2026-10-02):** literal reading; unreliable counting/arithmetic;
  unreliable date comparison; accuracy falls with indirection hops;
  accuracy falls as state grows with irrelevant detail; **adversarial
  content in state can steer the answer**; contradictory
  instructions/criteria confuse it; choice option-order bias (leans first);
  not trained to generate.
- **Confidence semantics (vendor docs):** choice confidence =
  (p_max − 1/n)/(1 − 1/n); score confidence accounts for distance from the
  peak level; noul carries no confidence — threshold the probability
  itself. Vendor pattern: high → act, medium → flag, low → route to human.
- **Privacy (Zen docs §Privacy):** "Jev APIs: Prompts and other inputs are
  not used for training. Data is retained in accordance with TypeSafe AI's
  Privacy Policy." The free variant is listed as limited-time with no
  training-use exception noted (unlike Big Pickle / Fledge / MiMo / Ling /
  Nemotron free entries). The repo is public — never send secrets or
  consumer data regardless.
- **Community precedents (weighed, not copied):**
  `purplesmoke05/opencode-plugin-jev-auto-model-router` (MIT, beta) —
    per-turn typed model selection with sticky pin at confidence ≥ 0.99,
    single-shot no-retry, fail-open to a configured fallback; uses the
    direct TypeSafe API (`TYPESAFE_API_KEY`), not the Zen endpoint.
  `aaronshaf/opencode-jev-orchestrator` (MIT, npm) — sticky cheap parent,
    Jev flags hard/easy/unsure, escalation via child subagents; Go-oriented.
  TypeSafe official skill/MCP + SDKs and cookbooks (guardrails, citation
    checking, RAG-passage classification, self-consistency → route
    uncertain nouls to human review). The self-consistency and
    confidence-gating patterns are the design idioms worth borrowing if the
    keep candidate is ever built.

### Probe log (2026-10-03, this design session)

Credential: Zen key from `~/.local/share/opencode/auth.json` (provider
`opencode`), read into `$KEY` in-shell; never printed, never recorded.
`OPENCODE_API_KEY` env was unset. Model: `jev-1.13-free` (preferred per
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
public ROADMAP text). Questions: `failure_class` (choice:
infra/content/mixed), `quarantine_warranted` (noul). Result: **HTTP 200,
472 ms**, verbatim:

```json
{"model":"jev-1.13-free","answers":{"failure_class":{"type":"choice","choice":"infra","confidence":1,"probabilities":{"infra":1,"content":0,"mixed":0}},"quarantine_warranted":{"type":"noul","noul":0.62}},"usage":{"input_tokens":462,"output_tokens":61}}
```

Probe 2 — score (state: a generic council-review description). Question:
`actionability` (score: Not/Partially/Fully actionable). Result: **HTTP
200, 336 ms**, verbatim:

```json
{"model":"jev-1.13-free","answers":{"actionability":{"type":"score","score":1.01,"confidence":0.98,"legend":{"0":"Not actionable","1":"Partially actionable","2":"Fully actionable"},"probabilities":{"0":0,"1":0.99,"2":0.01}}},"usage":{"input_tokens":334,"output_tokens":20}}
```

Observations for future use: sub-second latency; 334–462 input tokens per
call; the choice answer lands on the correct class (infra — matching the
RM-021 recorded diagnosis) with confidence 1.0; the noul returns a
calibrated mid-range 0.62 rather than forcing a binary. Both answers were
plausible and typed — the API contract works as documented from this
environment with the existing Zen credential.

### Candidate matrix

Filter: keep only where a typed probabilistic judgment concretely saves a
judgment (human/LLM reading time) or a mistake class (misdiagnosis,
false-green) **and** the current mechanism leaves that residue. Anti-goals
enforced: no generation/coding proposals; nothing a deterministic check
already settles; no novelty.

| # | Decision point | Current mechanism | Verdict | Fit reasoning (vs filter) | Integration form (if kept) | Adoption trigger / re-open signal |
|---|---|---|---|---|---|---|
| 1 | Model routing / escalation (role→model) | Static, dated, user-approved role table + liveness/bench candidate gate (`reference/model-routing.md`, `skills/optimizing-model-routing/SKILL.md`); community precedent = per-turn router plugins | **Drop** | Per-turn dynamic routing moves a binding decision from an approval gate (AGENTS.md rule 2) to an automated oracle; go-first bindings make Go the default for every role, removing the cheap/expensive per-turn asymmetry the community routers exploit; per-turn routing would send user prompt text (possibly consumer-repo content) to a third-party API; the router plugin uses the direct TypeSafe API + `TYPESAFE_API_KEY`, a credential surface this repo does not carry. No mistake class evidenced — routing errors are caught by the liveness canary and the approval gate | — (plugin/hook form rejected outright) | Re-open only if Go allowance exhaustion (5-hr/weekly/monthly caps, model-routing Provider notes) becomes a measured recurring problem **and** a deterministic run-log projection proves insufficient — the projection is arithmetic, so it nearly always suffices |
| 2 | Eval failure taxonomy: infra-vs-content split | Deterministic: `outcome=error` → infra, `outcome=failure` → content; dead-stream = all-error events; signature aggregation (`scripts/eval-report.py failure-taxonomy`, RM-021) | **Drop** | A deterministic check already settles it (anti-goal). Probe 1 confirms Jev *could* classify it (choice=infra, confidence 1.0) but adds cost, latency, and a network dependency where event-type inspection is exact | — | None; would re-open only if the deterministic signal itself disappears (RM-026 upstream: sessions with zero log lines) **and** stream text remained — then a text-classifier fallback becomes the only option |
| 3 | Content-failure triage *within* the red list (why did this eval miss?) | Human/LLM reads persisted streams per failure (RM-021: 31 content failures in run 36485564689; retune batches found by reading) | **KEEP** | Saves both a judgment (human stream-reading per weekly red) and a mistake class (wording-drift misread as skill regression, or a real regression retuned away — the RM-021 five-expect retune batch is the evidenced error). Not settled deterministically: the infra/content split stops at "content"; the *why* is open judgment. Advisory only — never gates | `scripts/jev_decide.py` (stdlib `urllib.request`, no new dependency) + `eval-report.py failure-taxonomy --jev-triage` advisory enrichment; sketch below | T1: a `jev-*` ID appears in the Go flat-rate catalog (checked at the next optimizing-model-routing catalog fetch). T2: `jev-1.13-free` still live (re-probe per the model-routing update procedure) **and** two consecutive post-RM-021 weekly runs each leave ≥10 content failures requiring human stream-reading (checked from failure-taxonomy artifacts) **and** the user accepts the free variant's data terms. T3: dated user directive approving Zen PAYG spend (measured <$0.01/weekly run) + a Zen CI secret |
| 4 | Quarantine flips + green-run qualification | Deterministic counters: 3 consecutive fails → quarantined, 3 passes → rehab (`scripts/quarantine.py`); 4-condition green-run check (`reference/eval-green-run-definition.md`) | **Drop** | Deterministic checks already settle both (anti-goal). A probabilistic input to a gate counter would violate the fail-open rule and the cardinal rule (never green a check by weakening the net) | — | None — deterministic-settled (consecutive counters + the 4-condition check); re-opens only if those mechanics are removed |
| 5 | Dispatch retry / vehicle-switch classification | Signal-regex classification (transient: `[server_error]`, timeout; deterministic: `invalid_request_error`, model-resolution) + bounded sequence retry→switch→inline (`reference/delegated-result-contract.md`, RM-024) | **Drop** | The bounded sequence caps the cost of a misclassification at ≤2 wasted retries; adding a network call *inside* the retry path creates the dependency the contract exists to survive; the real gap (RM-026: some sessions log zero lines) is upstream and unclassifiable from text that does not exist | — | Re-open only if RM-026 lands with logs present but signatures unmatchable by regex, and mis-retry cost becomes measured (run-log retry counts) |
| 6 | Changed-file → skill mapping (per-change gate) | Deterministic first-match-wins table with a safe harness fallback, by design (`scripts/changed-files-to-skills.py`, `reference/three-layer-gating.md`) | **Drop** | Deterministic by explicit design ("Ambiguous: the fixed harness set is the safe fallback"); a required PR check must never consult an external paid API (gate-blocking + secret in CI + third-party outage becomes a CI outage) | — | None — deterministic-settled (first-match-wins table + safe fallback); re-opens only if the table is removed |
| 7 | Coverage-gap judgments | Deterministic counts: zero-eval skills, deferred, quarantined, legacy assertions (`query_runs.coverage_gaps`) | **Drop** | Counting is the documented Jev anti-pattern ("if a regex or parser can find it, the count belongs in code"); gaps are enumerated, not judged | — | None — deterministic-settled (enumeration in `query_runs.coverage_gaps`); re-opens only if gap detection stops being enumerable |
| 8 | Triage scoring (impact × urgency) | LLM chat pass with an explicit 1–9 rubric, human confirms cuts (`skills/triaging-requirements` Step 6/8) | **Drop** | The pass is already human-confirmed and rubric-explicit; cadence is low (per triage); a second scorer adds a disagreement-resolution step without removing the human judgment — no concrete saving | — | Re-open if triage volume grows past human confirmation (e.g. managing-github-issues syncing hundreds of rows) — observable from row counts |
| 9 | Issue-refinement AC quality checks | Chat-model rewrite pass against the observable+verifier bar (`skills/refining-issue-acceptance`) | **Drop** | The chat pass *is* the mechanism; a Jev pre-screen would be two models doing one job on text the chat model must read anyway. The AC-quality judgment needs repo-context reasoning (which verifier commands exist), an indirection hop Jev is documented to weaken on | — | Re-open if batch refinement of ≥50 issues becomes routine and a cheap pre-filter shows measured savings |
| 10 | Review / security / a11y finding triage | Review severity = mechanical table (`reviewing-code` via CONTRIBUTING); a11y = axe rule output + needs-manual-verification bucket (`auditing-accessibility`); security = traced candidate triage (`reviewing-security`) | **Drop** | Review and a11y triage are rule-structured (anti-goal: deterministic). Security triage is multi-hop reasoning over traces — Jev's documented weak shape — and the `state` would contain adversarial content (injection payloads, exploit text), the documented steering weakness, in a public repo. A steerable oracle on security verdicts is a false-green risk, not a saving | — | Re-open only if TypeSafe ships a documented adversarial-state hardening (a jaggedness-page revision) **and** a traced-finding benchmark shows calibration — both observable in vendor docs |
| 11 | Council lens confidence / disagreement resolution | Chairman synthesizes; disagreements surfaced, never averaged away (`docs/COUNCIL.md`, `agents/council.md`, model-routing "always surface disagreements") | **Drop** | Policy conflict: the repo deliberately surfaces disagreement to humans instead of resolving it mechanically; a probability oracle resolving lens disputes is exactly the silent override the policy forbids. Lens findings are prose arguments — compressing them to questions loses the trace that makes them reviewable | — | Re-open only by an explicit user policy reversal (dated directive) |

### Keep-candidate integration sketch (row 3 — for the trigger-fired session, cold)

- **Form:** repo script, stdlib only. `scripts/jev_decide.py`:
  `urllib.request` POST to `https://opencode.ai/zen/v1/systemone`; key
  resolution order: `$OPENCODE_API_KEY` → `~/.local/share/opencode/auth.json`
  provider `opencode` (never printed); `--model` default `jev-1.13`
  (versioned ID, not the moving alias); `--timeout` default 10 s;
  single attempt, no retry (the router-plugin discipline); stdout =
  answers JSON; exit 0 = answered, non-zero = any failure. Consumer:
  `scripts/eval-report.py failure-taxonomy --jev-triage` adds, per content
  failure, an advisory `jev_triage` block; on any Jev failure the block is
  `{"status": "unavailable:<reason>"}` and the report still emits —
  **fail-open, never gates** a run, a quarantine flip, or the green-run
  check (cardinal rule: Jev output can never green or red anything).
- **Question shape (choice, criteria verbatim):**
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
- **State budget:** per failure — eval id, skill name, the `expect` block,
  the final agent output tail, and the assertion-diff detail, truncated to
  ≤ 8k chars (well inside the 32k state limit; jaggedness rule: send only
  what the question needs). Public-repo content only; never consumer data,
  never secrets (privacy rule).
- **Cost / latency (from measured probes):** ~340–470 input tokens per
  call → ~$0.00002/call paid; a 30-failure weekly red list ≈ $0.0006–0.001
  (<$0.01/run even 10×); 0.3–0.5 s/call → ~15 s serial for 30, inside the
  weekly job's budget; 80 req/s cap allows parallelism if ever needed.
  `jev-1.13-free` = $0 while it lasts (limited-time).
- **Verification at build time:** hermetic tests with a stubbed HTTP layer
  (repo pattern: `scripts/test_eval_report.py`); one live probe recorded in
  the PR description per the model-routing escalation-gate convention; a
  negative test asserting the report emits unchanged when Jev is
  unreachable.

### Durable home (planned record — the implementation pass lands these; nothing edited yet)

1. **`reference/jev-system-one-evaluation.md` (new):** this Evaluation
   Record, extracted with a dated header (`evaluated 2026-10-03; review-by
   2027-01-31`) and a `## Lifecycle` section carrying the user-required
   deletion triggers (AC-8): **D1** no `jev-*` ID live in the Zen catalog
   (model retired); **D2** an adoption trigger fired and shipped (essence
   moves to the integration's docs); **D3** superseded or rejected at
   triage / the ALM review; **D4** review-by reached without D1–D3 —
   re-verify volatile facts (docs.typesafe.ai + the Zen catalog) or delete.
   This is the cold-pickup doc that survives plan deletion (ADR-0008:
   plans are deleted after essence extraction; git history is the recovery
   path — but the essence must live in a durable tier, and a matrix of
   this size overflows a ROADMAP cell).
2. **`docs/ROADMAP.md` — RM-041 row (draft text):**

   > | RM-041 | evaluation | Jev (System One) advisory eval content-failure triage — trigger-gated | 5 | 3 | backlog | jev-system-one-evaluation plan 2026-10-03; `reference/jev-system-one-evaluation.md` | Advisory `jev_triage` classification of weekly-run content failures (skill_regression / assertion_wording_drift / prompt_or_fixture_defect / environment / unclear) enriching `eval-report.py failure-taxonomy` via a stdlib `scripts/jev_decide.py` against the Zen `systemone` endpoint; fail-open (unreachable → status field, report still emits), never gates a run, quarantine, or green-run; state = public-repo artifacts only, never secrets/consumer data; adoption requires an ADR (new external API dependency + CI secret) and explicit spend approval. **Trigger** (any one re-opens; each carries its verification mechanic): T1 a `jev-*` ID appears in the Go flat-rate catalog — checked at the next optimizing-model-routing catalog fetch; T2 `jev-1.13-free` still live on re-probe **and** two consecutive post-RM-021 weekly runs each leave ≥10 content failures needing human stream-reading — checked from failure-taxonomy artifacts — **and** the user accepts the free variant's data terms; T3 a dated user directive approving Zen PAYG spend (<$0.01/weekly run, measured) + a Zen CI secret. **Delete** (the reference doc is removed and this row closes when any of): D1 no `jev-*` ID live in the Zen catalog — enforced by the model-liveness alarm; D2 T1–T3 fired and the integration shipped (essence absorbed there); D3 superseded/rejected at triage or the ALM review; D4 review-by 2027-01-31 reached without D1–D3 (re-verify or delete). If a trigger fires and the candidate no longer survives the filter, close with a dated rejection note in the evaluation doc. |

   Landed as a proposed row at priority 5 / backlog; the next
   `triaging-requirements` pass ratifies or re-scores it (ingestion never
   bypasses scoring, RM-028 convention).
3. **`reference/model-routing.md` — additive note (draft text), new
   subsection "Non-chat models (decision endpoints)" after Provider
   notes:**

   > - **Jev 1.13** (`jev-1.13`, `jev-1.13-free`) — TypeSafe AI "System
   >   One" decision model; Zen-only (absent from the Go catalog, verified
   >   2026-10-03). Endpoint `https://opencode.ai/zen/v1/systemone` (typed
   >   questions → values + probabilities; no AI SDK package). $0.042/1M
   >   input, output free; free variant limited-time. **Never a role-binding
   >   candidate** — not a chat model; no routing pass may rank or bind it
   >   in any tier. Evaluated for advisory use 2026-10-03:
   >   `reference/jev-system-one-evaluation.md` (trigger-gated; ROADMAP
   >   RM-041).

   Deliberately **not** a Hard-exclusions row: that table records
   user-directive bans on bindable chat models; Jev is categorically
   unbindable, and a row there would imply it once was a candidate. No
   role row, no `agents/*.md`, no go-first decision is touched.
4. **ADR assessment: none now.** "Don't adopt yet" is carried by the
   ROADMAP row + evaluation doc; this repo's ADRs record binding/structure
   decisions, and no structure changes. **Adoption would warrant one**
   (new external API dependency, a CI secret, a privacy posture) — the
   RM-041 row says so explicitly, so the trigger-fired session cannot skip
   it.

## Files to Modify

- `.opencode/plans/jev-system-one-evaluation.md` — this plan (created by
  the design pass; tracked per AGENTS.md rule 4; deleted after essence
  extraction at close, ADR-0008)
- `reference/jev-system-one-evaluation.md` — new; the Evaluation Record
  above extracted verbatim-in-substance with a dated header (`evaluated
  2026-10-03; review-by 2027-01-31`) and a `## Lifecycle` section carrying
  deletion triggers D1–D4 (AC-8)
- `docs/ROADMAP.md` — add the RM-041 row (draft text in Durable home,
  including the D1–D4 deletion triggers); no other row touched
- `scripts/model-liveness-check.py` — add the D1 stale-evaluation alarm
  (doc present + zero live `jev-*` IDs in the Zen catalog → fail with the
  delete remedy)
- `reference/model-routing.md` — add the "Non-chat models (decision
  endpoints)" note (draft text in Durable home); additive; no role row,
  table, or existing section modified. Sequencing: if the go-first
  bindings branch lands first, rebase this note on top (different
  section; no textual conflict expected)

## Scope

**Included:**

- The evaluation record: verified tier facts, probe log, 11-row candidate
  matrix, keep-candidate integration sketch, durable-home drafts
- Landing the durable residue: one new reference doc, one ROADMAP row, one
  additive model-routing note
- The anti-rot lifecycle (user requirement): D1–D4 deletion triggers in the
  doc + RM-041 row, the model-liveness D1 alarm, and the review-by date

**Excluded:**

- Any adoption build: no `scripts/jev_decide.py`, no `eval-report.py`
  change, no CI workflow change, no secret provisioning, no new dependency
- Any modification to the go-first-model-bindings effort's decisions or
  files: no role rows in `reference/model-routing.md`, no `agents/*.md`
  `model:` lines, no `scripts/ci-lane-overrides.py`
- ADR creation (assessed: not warranted until adoption)
- Skill, persona, or `registry.json` changes; installing or wrapping the
  community plugins/MCP
- Sending any consumer-repo content, secret, or non-public text to Jev —
  in this pass or any future one (the two probes used synthetic
  public-repo text only)
- Re-litigating dropped candidates absent their recorded re-open signals

## Schema / Type Impacts

None. No database, no generated types, no shared contract changes. The
RM-001 run-log schema is untouched; a future adoption would add an
advisory `jev_triage` field to the `failure-taxonomy.json` **report
artifact** (not the run-log schema) and would need the observing-runs
schema owner's sign-off at that time — noted here so the trigger-fired
session does not discover it late.

## Verification

Docs-only change; the full CONTRIBUTING gate battery must stay green:

- `python3 skills/authoring-skills/scripts/validate_skill.py --all`
- `python3 scripts/check_typed_evals.py --base main`
- `python3 scripts/test_changed_files.py && python3 scripts/test_eval_report.py && python3 scripts/test_eval_workflows.py && python3 scripts/test_quarantine.py && python3 scripts/test_stall_timeout.py && python3 scripts/test_typed_evals.py`
- `node skills/managing-github-issues/evals/fixtures/unit.test.mjs`
- `node skills/refining-issue-acceptance/evals/fixtures/unit.test.mjs`
- `bash -n install.sh`
- `python3 -m yamllint -c .yamllint.yaml .github/workflows/`
- `python3 scripts/model-liveness-check.py` → exits 0 with the evaluation
  doc present and `jev-1.13` live (the D1 alarm dormant, not red)
- `git diff --name-only origin/main...HEAD` → exactly the five files in
  Files to Modify (AC7)
- `grep -n "jev" docs/ROADMAP.md reference/model-routing.md` → RM-041 row
  + non-chat note present (AC6)
- `python3 scripts/changed-files-to-skills.py --format object docs/ROADMAP.md reference/model-routing.md reference/jev-system-one-evaluation.md`
  → expected: `reference/model-routing.md` is **evaluable** → the
  per-change PR check runs the `optimizing-model-routing` canary (the
  other two paths are non_evaluable). This is correct behavior, not a
  surprise red: the canary must pass against an additive note.

## Open Questions

Non-blocking; each has a proposed default the approver can swap.

- **OQ-1 — Durable home shape.** Resolved (user, 2026-10-03): reference doc
  + ROADMAP row, **conditional on an explicit anti-rot lifecycle** — the
  doc must never become a stale file. Deletion triggers D1–D4 live in the
  doc's `## Lifecycle` section and the RM-041 row; the model-liveness D1
  alarm and the review-by date enforce them; see AC-8.
- **OQ-2 — RM-041 priority/status.** Resolved (user, 2026-10-03): priority 5,
  `backlog`, marked as proposed-by-this-plan; the next triage pass ratifies
  or re-scores (RM-028: ingestion never bypasses scoring).
- **OQ-3 — model-routing note placement.** Resolved (user, 2026-10-03): a new
  "Non-chat models (decision endpoints)" subsection after Provider notes —
  not a Hard-exclusions row (that table is for directive-banned bindable chat
  models; a row would imply Jev was once a candidate).
- **OQ-4 — Re-probe at implementation time?** Resolved (user, 2026-10-03): no —
  the 2026-10-03 probes are the evaluation's dated evidence; the T1/T2
  triggers carry their own re-probe requirement per the model-routing update
  procedure.
- **OQ-5 — Sequencing vs go-first-model-bindings.** Resolved (user,
  2026-10-03): land this residue after that branch merges, rebased on top —
  both touch `reference/model-routing.md`, and the go-first pass
  restructures the routing table, so landing earlier would rebase over a
  live file.

## History

- 2026-10-03 — approved (user, in-session). All five Open Questions resolved;
  OQ-1 carries the anti-rot lifecycle (AC-8), OQ-2 the triage-ratified
  priority. Implementation queued after the go-first branch merges (OQ-5);
  no adoption build.
- 2026-10-03 — OQ-5 resolved (user): land after the go-first branch merges,
  rebased on top. All five Open Questions resolved; awaiting plan approval.
- 2026-10-03 — OQ-4 resolved (user): no re-probe at implementation time — the
  2026-10-03 probes are the dated evidence; T1/T2 carry re-probe
  requirements. OQ-5 under review.
- 2026-10-03 — OQ-3 resolved (user): the Jev note lands as a new "Non-chat
  models (decision endpoints)" subsection in `reference/model-routing.md`.
  Remaining OQs 4–5 under review.
- 2026-10-03 — OQ-2 resolved (user): RM-041 lands priority 5 / `backlog`,
  marked proposed-by-this-plan; next triage pass ratifies or re-scores
  (RM-028). Remaining OQs 3–5 under review.
- 2026-10-03 — user review: OQ-1 resolved as reference doc + RM-041,
  conditional on an explicit anti-rot lifecycle (deletion triggers D1–D4 in
  both artifacts, a model-liveness D1 alarm, review-by 2027-01-31); AC-8
  added, AC-7/AC-8 diff lists and Verification updated. Remaining OQs
  2–5 under review.
- 2026-10-03: Design pass created this plan (user directive 2026-10-03,
  re-scoped from "incorporate Jev" to "future-fit evaluation in a plan
  doc" after the Zen-only tier fact emerged). No user-facing UI —
  council-ux consult skipped. Probe result: two live `jev-1.13-free`
  probes via the Zen key in `~/.local/share/opencode/auth.json` (provider
  `opencode`) — HTTP 200, 472 ms (choice+noul) and 336 ms (score),
  verbatim responses recorded in the Probe log; no key material recorded
  or printed. Catalogs fetched same day: Zen lists both jev IDs; Go lists
  none. Consult outcome recorded per the design-consult contract
  (`reference/delegated-result-contract.md`): skip, reason above.

- 2026-10-04 — mechanical renumber: the reserved trigger-gated row moves
  **RM-039 → RM-041** — RM-039 was claimed while this plan was queued and is
  now the go-first model-policy row (merged #96); RM-040 is the Go Plus
  review. No scope, acceptance, or decision changed. Implementation is
  unblocked (the go-first branch merged 2026-10-04, satisfying OQ-5).
