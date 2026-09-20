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
human-readable intent.

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
  workdir and its content contains every phrase (case-insensitive substring).
- **`text`** matches when the final response text contains every phrase
  (case-insensitive substring).

## Legacy `expected_behavior`

An eval without `expect` runs the legacy path: each `expected_behavior` string
must appear (case-insensitive substring) in the final response text. It is the
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
