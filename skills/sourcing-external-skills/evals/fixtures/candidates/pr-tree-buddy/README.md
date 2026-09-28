# pr-tree-buddy

Agentic PR review companion: walks the branch's changed files, drafts
review comments ranked by severity, and posts them to the PR thread.
Includes an `evals/` harness with recorded fixtures and typed `expect`
blocks for fresh-agent regression gating (the same protocol this
library's behavioral runner uses — see scripts/grade.py and
evals/fixtures/event-streams/).

License: none. Internal project; consider it all-rights-reserved.
Take this as inspiration only.
