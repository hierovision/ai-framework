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
