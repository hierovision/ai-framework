// ASPIRATIONAL EXAMPLE — not production code, not enabled by default.
//
// This stub is NOT schema-honest and must not be enabled as-is:
//   - it hardcodes `outcome:"success"` because `session.idle` cannot observe a
//     run's real outcome, so it can silently report failure as success;
//   - it omits skill/model/tokens/duration (no per-skill attribution exists);
//   - it fires on every `session.idle` with no dedup, and swallows all errors.
//
// Convention-based `log_run.py --record` remains the default. See the dated
// facts in ../../../reference/opencode-integration.md and the schema owner in
// ./schema.md.
export const ObserveRunsPlugin = async ({ $, directory }) => {
  return {
    "session.idle": async (input, output) => {
      try {
        await $`python3 ${directory}/skills/observing-runs/scripts/log_run.py --record '{"kind":"skill","outcome":"success"}'`.quiet();
      } catch {
      }
    },
  };
};
