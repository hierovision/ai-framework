# Typed eval assertions — schema and event stream

Reference for the closed typed-assertion protocol in `evals/evals.json`
(RM-003 pass 5). Consumed by `SKILL.md` Step 6 and enforced at Layer 1 by
`validate_skill.py` + `scripts/verify.mjs`, and by
`scripts/check_typed_evals.py` for new/changed evals.

## Contents

- The event stream (`opencode run --format json`)
- The `expect` block (closed schema)
- Class semantics and the nature rule
- Legacy `expected_behavior`
- Fixture replay (`--event-fixture`)
- Diagnosing a red run (failure taxonomy)

## The event stream (`opencode run --format json`)

The runner captures stdout as **newline-delimited JSON** — one event object per
line. Relevant shapes:

```json
{"type":"text","part":{"type":"text","text":"the final response text"}}
{"type":"tool","part":{"type":"tool","tool":"write",
  "state":{"status":"completed","input":{"filePath":"/work/SKILL.md","content":"..."}}}}
{"type":"step_finish","part":{"type":"step-finish","tokens":{"input":1200,"output":340}}}
```

- A **text** event carries `part.type = "text"` and `.text`; the runner
  concatenates the text parts to form the final response.
- A **tool** event carries `part.type = "tool"`, `part.tool` (the tool name),
  and `part.state.input` (the argument object: `filePath`, `content`,
  `command`, ...).
- A **step_finish** event carries token counts.

A non-empty line that is not a JSON object is a parse error. For a typed eval
a parse error **fails closed** — it is never a silent pass.

## The `expect` block (closed schema)

```json
"expect": {
  "action": [
    {"tool": "bash", "args": {"command": "*log_run.py*"}}
  ],
  "artifact": [
    {"path": "**/SKILL.md", "phrases": ["name:", "description:"]}
  ],
  "text": ["out-of-context"]
}
```

Closed form — enforced by both Layer-1 validators:

- `expect` is an object with **at least one** non-empty `action`, `artifact`,
  or `text` entry; unknown top-level keys are rejected. No `exit_code`,
  `database`, or `network` class exists.
- `action[]` entries: `tool` (non-empty string, a glob) required; `args`
  optional object of argument-name -> glob string. Unknown keys rejected.
- `artifact[]` entries: `path` (non-empty glob, resolved under the run
  workdir) and `phrases` (non-empty array of non-empty strings) required.
  Unknown keys rejected.
- `text[]` entries: non-empty strings.

`expected_behavior` is required only when `expect` is absent; when both are
present `expect` wins at run time and `expected_behavior` is kept as
**non-asserted, human-readable intent** — a future reader can check it
against what the typed assertions actually pin, but nothing runs it (an
`expected_behavior` the typed assertions outgrew is intent rot: update it
on touch or delete it).

## Class semantics and the nature rule

| Behavior the eval checks | Class |
|---|---|
| Performs an action / calls a tool | `action` |
| Produces or edits a file | `artifact` |
| Is literally speech (restates, refuses, asks in prose) | `text` |

- **`action`** matches when a tool event's tool name matches the `tool` glob
  and every `args` glob matches the corresponding `state.input` value (string
  form; `fnmatch` semantics, `*` crosses path separators).
- **`artifact`** matches when a file matching `path` exists under the run
  workdir and its content contains every phrase (case-insensitive substring
  after whitespace normalization — phrase checks collapse whitespace runs, so
  markdown line-wraps cannot break a multi-word phrase; 2026-09-28).
- **`text`** matches when the final response text contains every phrase
  (case-insensitive substring after whitespace normalization).

## Legacy `expected_behavior`

An eval without `expect` runs the legacy path: each `expected_behavior` string
must appear (case-insensitive substring after whitespace normalization) in the
final response text. It is the
`text` class by definition, and is flagged `legacy_assertion` in
`coverage-gaps.legacy_assertion_evals` for migration. Migrate on touch: any
eval that fails, is touched, or is selected as a canary migrates to a typed
`expect` in the same change.

## Fixture replay (`--event-fixture`)

`run_behavioral_eval.py --event-fixture <path>` replays a committed stream
(file `events.jsonl`, or the directory containing it) through the matcher with
no model and no network. The directory is the workdir for `artifact`
predicates, so recorded artifact files sit beside the stream. Committed
fixtures live under `evals/fixtures/event-streams/<skill>__<eval-id>/`.

## expected_behavior beside `expect`

When an eval carries both, `expect` is the asserted contract; `expected_behavior` is
retained as HUMAN-READABLE INTENT and is **not cross-checked at runtime**.
It can rot silently — update it alongside `expect` or delete it.

## Diagnosing a red run (failure taxonomy)

A red eval is one of two classes, and the run log now says which (RM-021,
2026-09-28):

- **Content miss** — `outcome: "failure"`, `detail: "missing: <assertions>"`.
  The agent acted (tool events present) and the contract was not met. Routes
  to nudge/continuation and quarantine; never to a fresh-session retry.
- **Infra error** — `outcome: "error"`, `detail: "dead session: <ErrorName>
  ref=err_* — no work produced"`. Every event in the turn is `type:error`
  (a provider/opencode-server error), so resuming cannot help: the runner
  restarts a **fresh session** (`fresh retry N`, bounded by
  `BEVAL_MAX_FRESH_RETRIES`, clamp 2) and logs each attempt. The signature in
  `detail` is the actual cause — not the old opaque "fatal stream".

Every turn of a failed eval is persisted beside the run log, redacted:

```
logs/eval-streams/<skill>__<id>-<UTCstamp>-turn<N>-<label>.jsonl   # event stream
logs/eval-streams/<skill>__<id>-<UTCstamp>-turn<N>-<label>-stderr.log
```

The `-stderr.log` is the point of the diagnostic channel: the runner invokes
`opencode run --print-logs --log-level ERROR`, so the server-side cause behind
an `err_*` ref lands on stderr and is uploaded with the artifact (redacted of
provider keys, capped 8 KiB). Without it, `UnknownError ... Check server logs`
has no logs to check.

Aggregate the picture without downloading streams by hand:

```bash
python3 scripts/eval-report.py failure-taxonomy --logs-dir logs/ --print
```

It reports `infra_error` vs `content_failure` from the run records, then
classifies the persisted streams (`dead_streams` = all-error streams,
`acted_streams` = streams with tool events) and aggregates
`error_signatures` by error **name** with a sampled `error_ref_samples` list
(the count is the signal; a ref lets an operator pull the matching server log).
The weekly workflow writes it to `failure-taxonomy.json`; `failure-taxonomy`
is also part of `all`. This is the artifact that showed weekly run
36455843309's red as provider-driven: 44 dead streams, every one
`UnknownError ref=err_*`, spread across the full hour rather than a burst.
