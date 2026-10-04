---
slug: rm-021-ac9-watch
title: RM-021 AC9 — check the scheduled weekly run on/after Monday 2026-10-06
status: pending
created: 2026-10-04
---

# RM-021 AC9 watch

**Check on or after Monday 2026-10-06 10:30 UTC.** The scheduled weekly
eval run (`eval-behavioral.yml`, default depth, 26 evals) fires
automatically. After it completes:

1. Inspect the uploaded `eval-report-<run_id>` artifacts:
   `failure-taxonomy.json` — all final content verdicts PASS,
   `terminal_infra=0`; `coverage-gaps.json` — no missing evals;
   `green-run-status.json` — within the weekly budget.
2. Run the AC9 record command:

   ```bash
   python3 scripts/eval-report.py green-run-status --record \
     --run-id <id> --date <d> --duration-min <n> --all-pass \
     --quarantine-flips 0 --artifact-url <url>
   ```

3. If `"achieved": true`: update `docs/ROADMAP.md` (RM-021 → done with a
   reconciled remaining-text; RM-003's green-run note updated) and add a
   History entry to `rm-021-eval-reliability.md`. RM-021 is then done.
4. If not achieved: diagnose from the artifacts, apply the fix, and wait
   for the next scheduled run (or dispatch a targeted run to verify).

**AC status at time of writing:** AC1–AC8 met; AC9 is the only open item.
See `rm-021-eval-reliability.md` for full evidence.
