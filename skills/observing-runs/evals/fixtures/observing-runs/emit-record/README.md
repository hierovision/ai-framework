# Scenario: emit a run record

You are evaluating the `observing-runs` skill. The working directory contains
the skill at `skills/observing-runs/`.

Task: record a single behavioral-eval run of the hypothetical skill
`writing-unit-tests` using the skill's `log_run.py` helper. Use: model tier
`go`, tokens_in 812, tokens_out 305, duration_ms 142000, outcome `success`,
eval_pass `true`. Then state, in one sentence, the ROI guardrail — i.e. why a
run log must never be read back into the agent's own live prompt.

Grade by reading the resulting `logs/run-<date>.jsonl` line and the agent's
transcript. Do not grade the author's own memory.
