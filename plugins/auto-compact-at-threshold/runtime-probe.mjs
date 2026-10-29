// Runtime evidence for post_smoke: load the real plugin module, run setup,
// emit the startup marker, then prove cleanup aborts the subscription.
import definition, { PLUGIN_ID, createDefinition } from "./index.js";

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const logs = [];
let signalRef = null;
let subscriptionEnded = false;

const ctx = {
  model: {
    list: async () => [
      { providerID: "opencode-go", id: "probe", limit: { context: 100 } },
    ],
  },
  session: { compact: async () => {} },
  log: {
    info: async (message, extra) => logs.push({ level: "info", message, extra }),
    warn: async (message, extra) => logs.push({ level: "warn", message, extra }),
    error: async (message, extra) => logs.push({ level: "error", message, extra }),
  },
  event: {
    subscribe: ({ signal } = {}) => {
      signalRef = signal;
      return {
        async *[Symbol.asyncIterator]() {
          while (!signal?.aborted) await sleep(5);
          subscriptionEnded = true;
        },
      };
    },
  },
};

const cleanup = await createDefinition({ define: (d) => d }).setup(ctx);
await sleep(10);
const startup = logs.some((entry) => entry.message.includes("initialized"));
cleanup();
await sleep(25);

const result = {
  plugin_id: PLUGIN_ID,
  default_id: definition.id,
  source: import.meta.url,
  startup_marker: startup,
  cleanup_returned: typeof cleanup === "function",
  subscription_aborted: Boolean(signalRef?.aborted),
  subscription_ended: subscriptionEnded,
};
console.log(JSON.stringify(result));
if (!startup || !result.subscription_aborted || !result.subscription_ended) {
  process.exitCode = 1;
}
