# Deviation protocol (Step 4)

Read this when a plan-vs-repo mismatch is ambiguous. The SKILL.md body carries
the rule; this file the full classification.

## Classify before editing

Match every `Files to Modify` entry against what is actually on disk and read
each named file. The dividing question: **does the difference change the
feature being built?**

| Mismatch type | Action |
|---|---|
| File moved / renamed / path alias differs | Mechanical: proceed at the corrected path; dated `## History` note with the reason |
| Exact line numbers / import specifiers drift | Mechanical: proceed; record in History |
| Different feature than the plan's Goal | Contract-breaking: STOP, report, route to `designing-architecture` |
| Schema / Type Impacts differ from the schema source of truth | Contract-breaking: STOP, report, route to design |
| Acceptance criterion untestable as written (names a file / service / table the plan does not add) | Contract-breaking: STOP, report, route to design |
| Verifier cannot pass for any in-scope implementation (the plan omits a dependency) | Contract-breaking: STOP, report, route to design |
| AC verifier cannot produce a red-first test (Step 5) | Contract-breaking (Step 4 path): STOP, report, route to design |
| N reasonable fix attempts do not converge (Step 7) | Honest-stop: STOP, report, hand to the debug stage (do not thrash) |
| Red-first test never fails for the right reason (Step 5) | Honest-stop (Step 7 path): STOP, report, hand to `debugging-test-failures` |

A moved file is mechanical; a moved feature is contract-breaking. Recorded
deviations are honest; silent ones are not. When in doubt, stop — stops are
recoverable, a built-wrong-feature is not.
