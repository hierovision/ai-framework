---
name: debugging-test-failures
description: Diagnose WHY a failing verification won't converge — reproduce first, hypothesis + discriminating experiment, classify the defect (code / test / plan / environment), fix at root cause, run the FULL suite green. Use whenever the user says "this test is failing and I can't tell why", "CI went red", "the e2e suite is flaky", "npm run test fails on X", or a plan's Verification resists focused fix attempts in an implement pass (the honest-stop handoff) — even without saying "debug". Never greens a test by weakening the net (.skip, deleted assertions, widened tolerances, retry-loops); an explicit user order to weaken requires a dated record. Routes plan-internal contradictions to designing-architecture. Not for: writing new tests, executing a converging plan (implementing-features), infra outages, or performance analysis without a failing check.
---

# Debugging Test Failures

The diagnosis discipline of the core loop. Entered from an
`implementing-features` pass that hit its honest-stop (Step 6
non-convergence: N focused fix attempts did not converge), or
standalone ("CI is red", "this test started failing", "the e2e suite
is flaky"). The implement skill converges; this skill explains **why
something will not converge** and removes the cause.

A debug pass is **done** when the root cause is identified and stated in
one sentence, the fix is applied at the root cause, the previously-
failing command exits 0, **and** the full verification suite still
passes (no regression traded in). Or an honest escalation (below). "It
passes now but I'm not sure why" is not closure — that is a refuted
diagnosis.

## The debug pass

Copy this checklist and check off items as you complete them.

```
Debug Progress:
- [ ] 1. Reproduce (run the failing command; read the actual output)
- [ ] 2. Detect stack & load the matching stack reference
- [ ] 3. Form a root-cause hypothesis
- [ ] 4. Design + run the cheapest discriminating experiment
- [ ] 5. Classify the defect (CODE / TEST / DESIGN-PLAN / ENVIRONMENT)
- [ ] 6. Apply the class-specific fix
- [ ] 7. Regression guard (run the FULL suite)
- [ ] 8. Closure (diagnosis record) or escalation
```

### Step 1 — Reproduce before diagnosing

Run the failing command and read the **actual** output before forming
any hypothesis or touching any source. The reported symptom is a
summary; the failure output is the evidence. Two branches:

- **Reproduced** (the command fails on a clean run) → proceed to
  Step 2. Never edit from the reported symptom alone — the symptom
  points at where the assertion tripped, which is often downstream of
  the defect.
- **Cannot reproduce on a single run** → that is the **flake branch**,
  not a license to say "works for me." Rerun the command several times
  (or run the single test in isolation, then in the suite, then in
  reverse order — order/shared-state flakes surface here). A flake is a
  real defect of class 4 (environment/nondeterminism); diagnose it,
  do not dismiss it.

### Step 2 — Detect stack & load the matching stack reference

Identify the project stack from the rules file (`AGENTS.md` /
`.opencode/agents.md`). If this skill bundles a matching stack
reference under `references/stacks/` (resolved against this skill's own
directory — not the project's), read it now and apply its debugging-time
concerns. If none exists, proceed generically and flag the gap to the
user in the handoff — a missing stack reference is a finding, not a
silent "I'll improvise."

Available stack references:

- vue-supabase → [references/stacks/vue-supabase.md](references/stacks/vue-supabase.md)
  Read when the project is Vue 3 + Pinia + Supabase (Postgres + Auth +
  RLS) with Playwright e2e. Applies e2e wait discipline (waitForTimeout
  as a flake suspect), Playwright trace/screenshot evidence, Pinia
  state isolation between tests, Supabase RLS-silently-returns-empty
  diagnosis, and generated-types drift after schema changes.

### Step 3 — Form a root-cause hypothesis

State an explicit, falsifiable hypothesis about **why** the failure
occurs — not just **what** failed (the assertion already says what).
Write it down in the transcript before designing an experiment. A good
hypothesis names a location and a mechanism: "the password-reset flow
rejects a valid token at the accept step because the token was signed
with a different secret than the verifier reads — the assertion trips
at token acceptance, but the defect is in the signing-config wiring
upstream."

### Step 4 — Design + run the cheapest discriminating experiment

Design the cheapest experiment whose outcome **differs depending on
whether the hypothesis is true**. A discriminating experiment is not a
retry; it is a probe:

- a **log / one-off print** of the suspect function's actual return at
  the boundary (e.g. `node -e` calling the module directly) — confirms
  whether the data or the render is wrong;
- a **narrower test invocation** — run just the unit under suspicion,
  then the next one up, to localize which layer flips the result;
- a **bisect over inputs** — feed the suspect function a minimal,
  hand-built input where the bug must show vs. an input where it
  cannot, and observe the difference;
- a **git bisect** over history when "this started failing after the
  merge" — let the binary search find the introducing commit.

Run it. Record the result in the transcript. **Confirm or refute.** If
refuted, form the next hypothesis and narrow — do not edit on a
refuted hypothesis. Every code edit in this skill must be grounded in a
**confirmed** hypothesis. Shotgun edits and speculative retries are the
thrash this skill exists to prevent.

### Step 5 — Classify the defect (the heart of the skill)

The defect is in **exactly one** of four places. The class determines
the response. Classify before fixing; misclassification is how a debug
pass turns into a trap (weakening the net to "win" a test that was
right).

1. **THE CODE** — behavior contradicts the intent the test correctly
   asserts. Fix the code, minimal diff at the root cause.
2. **THE TEST** — the test asserts something the spec/plan does not
   support (wrong expectation, over-specified selector, brittle
   ordering assumption). Fixing the test is legitimate but demands a
   justification from the spec/plan/docs, stated explicitly. The
   assertion after the fix must still verify meaningful behavior.
3. **THE DESIGN/PLAN** — the test is right, the code matches the plan,
   and they still conflict: the plan itself is defective (internally
   inconsistent, or contradicts the spec it cites). STOP. Route to
   `designing-architecture` with the specific conflict. Same
   contract-breaking posture as the implement skill — the debugger
   never silently picks a side in a plan-internal contradiction.
4. **THE ENVIRONMENT** — nondeterminism or infra: timing races, shared
   state between tests, order dependence, external-service flake, clock
   / random sources in a data path the test asserts against. Fix the
   **source** of nondeterminism (deterministic waits on conditions,
   isolated state, seeded data, removing the random/clock source), never
   wrap it in retries-until-green.

See the class details below for the discipline each one demands.

### Step 6 — Apply the class-specific fix

Apply the fix the classification dictates — minimal, at the root cause,
grounded in the confirmed hypothesis. The cardinal rule (below) gates
every edit.

### Step 7 — Regression guard (run the FULL suite)

After any fix, run the project's **full verification suite** from the
rules file — not just the previously-failing test. A debug pass that
fixes one test and breaks another is not closed. "It's green where I
touched it" is intent, not closure; the full suite's exit codes are the
signal.

### Step 8 — Closure or escalation

On green full suite: produce the **diagnosis record** (below). On a
non-fix terminal: produce an **escalation record** (below). Either way,
do not run `git commit` / `push` / merge / PR unless the user asks.

## Failure classification — class details

### 1. THE CODE

The test correctly asserts intended behavior; the code contradicts it.
Fix the code at the root cause with a minimal diff. Resist the pull of
the surface symptom: a failing assertion usually points at the place
the wrong value is *observed*, which is often downstream of the place
the wrong value is *produced*. The discriminating experiment (Step 4)
is what separates the two. If a surface fix (patching where the value
is observed) would leave another assertion of the same contract still
failing, that is the signal you are patching the symptom, not the
cause.

### 2. THE TEST

The test asserts something the spec / plan / docs do not support.
Fixing the test is legitimate **only** with an explicit justification
drawn from the spec or plan — cite the section that the test
contradicted. "The test was annoying" is not a justification; "plan
criterion 2 requires a rejected submission to return 409, the test
asserted 200" is.

After the fix, the assertion must still verify **meaningful** behavior
— a test that can no longer fail is not a test. The check: if you
broke the real behavior, would the fixed test still go red? If not, the
"fix" vacated the assertion. Prefer rewriting the expectation to the
correct value over deleting it; prefer deleting over `.skip`; never
replace an assertion with `assert(true)` or an equivalent tautology.

### 3. THE DESIGN/PLAN

The test is right, the code matches the plan, and they still conflict.
Read the **whole** plan — Goal plus Acceptance Criteria. If the test
matches the Goal but contradicts a criterion, or matches a criterion
but contradicts the Goal, the plan is internally inconsistent. The
defect is in the plan, not the code or the test.

**STOP.** Do not edit source. Picking a side — editing the code to
match the Goal (contradicting the criterion) or to match the criterion
(contradicting the Goal) — is a silent design decision made inside a
debug pass, and it destroys the loop's auditability the same way the
implement skill's scope creep does. Route to `designing-architecture`
with the specific conflict quoted, and let the design stage revise the
plan. The debugger reports the contradiction; design resolves it.

### 4. THE ENVIRONMENT

Nondeterminism or infra. The discipline: fix the **source** of
nondeterminism, never the **symptom**.

- Timing races / e2e flake → wait on **selectors and conditions**
  (`expect(...).toBeVisible()`, `waitForSelector`), never fixed
  timeouts; a `waitForTimeout` left in a failing e2e is a prime
  nondeterminism suspect, not a thing to lengthen.
- Shared state between tests → isolate: reset the store / DB / cache
  per test, seeded deterministically.
- Order dependence → make each test independent of its neighbours;
  if a test only fails when run after another, the first is mutating
  shared state the second reads.
- External-service flake → stub the boundary deterministically with a
  seeded fixture; do **not** mock away the behavior under test (that's
  class "weakening the net").
- Clock / random in a data path the test asserts against → inject a
  deterministic clock / a seeded RNG at the boundary, or remove the
  nondeterminism from the asserted path entirely.

Retries-until-green are the anti-pattern: they make the flake
**invisible** without removing it, and they inflate run time. A green
run achieved by retrying is not closure — it is a silenced alarm.

## The cardinal rule: never green by weakening the net

Never green a test by weakening the verification net. These are all the
same move — making the signal lie:

- deleting or commenting out an assertion;
- widening a tolerance / loosening an equality to a partial match that
  the bug no longer trips;
- adding `.skip` / `.only`-excluding / `@Ignore` to make a test not
  run;
- mocking away the behavior under test so the assertion passes against
  a stub;
- retry-looping a flake until it happens to pass;
- guarding the assertion with a try/catch that swallows the failure.

If the user **explicitly orders** a weakening ("just skip it, demo in
an hour"), comply only with an **explicit record**: a dated note — in
the plan's `## History` when a plan is in play, or a `TODO` the user
names — stating **what** was weakened, **why**, and **what restoring
it takes**. A weakened net with a record is a debt; without a record
it is a trap. The refusal-then-record pattern mirrors
`implementing-features`' scope discipline: refuse by default, record
the urge if it is overridden, never silently comply.

## Closure

Closure is, all of these at once:

1. **Root cause identified** — and stated in **one sentence**.
2. **Fix applied** — at the root cause, grounded in a confirmed
   hypothesis.
3. **The previously-failing command exits 0.**
4. **The FULL verification suite still passes** — no regression traded
   in.

And the deliverable:

- a short **diagnosis record** — symptom, root cause (one sentence),
  fix, evidence (the discriminating experiment that confirmed the
  hypothesis), suite status. When a plan artifact is in play, **append**
  it to the plan's `## History`; standalone, present it in the handoff
  summary.

"It passes now but I'm not sure why" is **not** closure — that is a
refuted diagnosis. Reopen Step 3.

## Escalation honesty (three non-fix terminals)

Three legitimate terminals that produce **no source edit** and **no
fake green**:

- **(a) Design defect** — class 3. Route to `designing-architecture`
  with the specific conflict (quote the contradicting plan sections),
  the failing test, and the code that matches one side. The debugger
  does not rewrite the plan.
- **(b) Genuinely out of scope** — the root cause is real but its fix
  needs access this pass does not have (infra change, upstream-library
  bug, a migration that a separate owner must run). Report with
  evidence and concrete options; do not hack around it silently.
- **(c) Budget exhausted** — hypotheses refuted, root cause not yet
  pinned. Report the **debugging log** — what was tried, what each
  experiment ruled out, the surviving hypotheses. What is eliminated
  IS progress; a narrowed search space is a legitimate handoff.

Never a fake green. A red suite reported honestly is a better terminal
than a green suite bought by weakening the net.

## The debugging log (transcript discipline)

Keep a visible debugging log in the transcript throughout the pass.
For each hypothesis cycle:

```
hypothesis: <one sentence, naming location + mechanism>
experiment: <the cheapest probe whose outcome discriminates the hypothesis>
result:     <confirmed | refuted — with the observed outcome>
next:       <narrow to the next hypothesis, or apply the fix>
```

The log is what makes a budget-exhausted escalation (terminal c)
honest — it is the evidence that the pass was a disciplined search,
not a thrash. It is also what lets a reviewer audit that every edit
was grounded in a confirmed hypothesis.

## Where this skill catches the implement seam

`implementing-features` Step 6 has two honest-stop conditions that
hand off here:

- **N reasonable fix attempts have not converged** — the implement
  pass converges; it does not thrash. That handoff is the canonical
  entry to this skill. Bring the failed attempts into your initial
  hypotheses (they are eliminated search space — terminal-c logic, but
  at the start).
- **The failure reveals the plan itself is wrong** — the implement
  skill classifies that as a contract-breaking deviation and routes to
  design directly. This skill's class 3 is the same posture, reached
  when the plan-internal contradiction surfaces only during diagnosis
  (the test is right, the code matches the plan, they still conflict).

When a plan artifact is in play, the diagnosis record appends to that
plan's `## History` (the audit trail the implement skill maintains);
the debugger does not rewrite prior plan sections, only appends.

## When not to use this skill

- **Writing new tests** — that is the test-authoring skills' job; this
  skill fixes or justifies existing tests, it does not author a suite.
- **Executing an approved plan that is converging** — that is
  `implementing-features`; this skill only owns the non-convergence.
  Do not jump from a green implement pass into a "debug" pass.
- **An infra outage with no code defect** — the test is red because
  the service is down, not because the code is wrong. Report it; do
  not "fix" the test to tolerate the outage.
- **Performance analysis without a failing check** — "why is this
  slow?" with no failing test is profiling, not debugging-test-
  failures.
- **A single trivial fix obvious from the failure output** — if the
  failure names the exact one-line cause and the fix is immediate,
  the implement skill's Step 6 loop handles it; this skill is for the
  non-obvious and the non-converging.

## References

- [references/stacks/vue-supabase.md](references/stacks/vue-supabase.md)
  — debugging-time concerns for Vue 3 + Pinia + Supabase + Playwright
  stacks: e2e wait discipline (waitForTimeout as a flake suspect),
  Playwright trace/screenshot evidence, Pinia state isolation between
  tests, Supabase RLS-silently-returns-empty diagnosis, and generated-
  types drift after schema changes. Read at Step 2 when the project's
  rules file declares stack `vue-supabase`.
- The plan artifact contract is defined in
  [../designing-architecture/references/plan-format.md](../designing-architecture/references/plan-format.md)
  — the `## History` section this skill appends to, and the
  contract-breaking posture class 3 shares with `implementing-features`.
