/**
 * Auto-compact at a fraction of the active model's context window — V2 plugin.
 *
 * `@opencode/plugin@2.1.4` contract (validated 2026-10-27): a default
 * `Plugin.define({ id, setup })` definition, domain methods on `ctx`
 * (`ctx.model.list()`, `ctx.session.compact({ sessionID })`), an aborted
 * `ctx.event.subscribe()` loop, and a cleanup function returned from setup.
 *
 * Behaviour is the V1 plugin's, ported:
 * - fires when an assistant message's context usage reaches
 *   OPENCODE_AUTOCOMPACT_THRESHOLD (default 0.5) of the model's
 *   `limit.context`, on session idle;
 * - one compaction per threshold crossing (re-arms below the line);
 * - never while a compaction is in flight;
 * - unknown context limit -> skip (no guessing);
 * - a dated startup marker makes the load observable.
 *
 * Usage is counted like opencode's overflow check:
 *   tokens.total || input + output + cache.read + cache.write
 */

const DEFAULT_THRESHOLD = 0.5;
const PLUGIN_ID = "auto-compact-at-threshold";

function readThreshold(raw = process.env.OPENCODE_AUTOCOMPACT_THRESHOLD) {
  if (raw === undefined || raw === null || raw === "") return DEFAULT_THRESHOLD;
  if (typeof raw !== "string") return DEFAULT_THRESHOLD;
  const value = raw.trim().endsWith("%")
    ? Number(raw.trim().slice(0, -1)) / 100
    : Number(raw);
  return Number.isFinite(value) && value > 0 && value <= 1
    ? value
    : DEFAULT_THRESHOLD;
}

function countTokens(tokens) {
  if (!tokens || typeof tokens !== "object") return null;
  if (typeof tokens.total === "number" && tokens.total > 0) return tokens.total;
  const cache = tokens.cache ?? {};
  const count =
    (tokens.input ?? 0) +
    (tokens.output ?? 0) +
    (cache.read ?? 0) +
    (cache.write ?? 0);
  return count > 0 ? count : null;
}

function eventType(event) {
  return event?.type ?? event?.event?.type ?? event?.event;
}

function eventProperties(event) {
  return event?.properties ?? event?.data ?? event?.event?.properties ?? {};
}

function sessionIDOf(props) {
  return props?.sessionID ?? props?.session?.id ?? props?.info?.sessionID;
}

async function log(ctx, level, message, extra = {}) {
  const entry = { service: PLUGIN_ID, level, message, extra };
  const sink = ctx?.log ?? ctx?.logger ?? ctx?.app;
  try {
    if (sink && typeof sink[level] === "function") {
      await sink[level](message, extra);
      return;
    }
    if (sink && typeof sink.log === "function") {
      await sink.log(entry);
      return;
    }
  } catch {
    // Logging must never break the plugin.
  }
  // A startup marker must be observable even without a logger domain.
  console.log(JSON.stringify(entry));
}

function limitsFromModels(models) {
  const limits = new Map();
  const list = Array.isArray(models)
    ? models
    : (models?.models ?? models?.data ?? []);
  for (const model of list ?? []) {
    const provider =
      model?.providerID ?? model?.provider?.id ?? model?.provider;
    const id = model?.id ?? model?.modelID ?? model?.model;
    const context = model?.limit?.context ?? model?.context;
    if (provider && id && typeof context === "number" && context > 0) {
      limits.set(`${provider}/${id}`, context);
    }
  }
  return limits;
}

async function loadLimits(ctx) {
  try {
    const result = await ctx?.model?.list?.();
    return limitsFromModels(result);
  } catch (error) {
    await log(ctx, "warn", `could not load model limits: ${error?.message ?? error}`);
    return new Map();
  }
}

async function contextLimit(ctx, limits, providerID, modelID) {
  let limit = limits.get(`${providerID}/${modelID}`);
  if (limit === undefined) {
    const refreshed = await loadLimits(ctx);
    for (const [key, value] of refreshed) limits.set(key, value);
    limit = limits.get(`${providerID}/${modelID}`);
  }
  return limit;
}

/**
 * Build the plugin definition. Exported for `node --test`; the default export
 * is the `Plugin.define` result the V2 loader consumes.
 */
export function createDefinition(Plugin) {
  return {
    id: PLUGIN_ID,
    async setup(ctx) {
      const threshold = readThreshold();
      const controller = new AbortController();
      const usage = new Map();
      const armed = new Map();
      const compacting = new Set();
      const limits = await loadLimits(ctx);

      await log(ctx, "info", "auto-compact-at-threshold initialized", {
        version: "2.1.4",
        threshold,
      });

      async function handle(event) {
        const type = eventType(event);
        const props = eventProperties(event);
        if (type === "session.compacted") {
          const sid = sessionIDOf(props);
          if (sid) {
            usage.delete(sid);
            armed.set(sid, true);
          }
          return;
        }
        if (type === "message.updated") {
          const info = props?.info ?? props?.message ?? props;
          if (!info || (info.role && info.role !== "assistant")) return;
          const tokens = countTokens(info.tokens);
          const providerID = info.providerID ?? info.model?.providerID;
          const modelID = info.modelID ?? info.model?.id;
          const sid = info.sessionID ?? sessionIDOf(props);
          if (tokens === null || !providerID || !modelID || !sid) return;
          usage.set(sid, { providerID, modelID, tokens });
          const limit = await contextLimit(ctx, limits, providerID, modelID);
          if (limit !== undefined && tokens < limit * threshold) {
            armed.set(sid, true);
          }
          return;
        }
        if (type === "session.idle") {
          const sid = sessionIDOf(props);
          if (!sid) return;
          const current = usage.get(sid);
          if (!current || compacting.has(sid)) return;
          if (armed.get(sid) === false) return;
          const limit = await contextLimit(ctx, limits, current.providerID,
            current.modelID);
          if (limit === undefined) return; // unknown limit: fail safe
          if (current.tokens < limit * threshold) return;
          compacting.add(sid);
          armed.set(sid, false);
          const percent = ((current.tokens / limit) * 100).toFixed(1);
          try {
            await ctx.session.compact({ sessionID: sid });
            await log(ctx, "info", `compacted at ${percent}% of context`, {
              sessionID: sid,
              providerID: current.providerID,
              modelID: current.modelID,
              tokens: current.tokens,
              limit,
              threshold,
            });
          } catch (error) {
            await log(ctx, "error", `auto-compaction failed: ${error?.message ?? error}`,
              { sessionID: sid });
            armed.set(sid, true);
          } finally {
            compacting.delete(sid);
          }
        }
      }

      let finished = false;
      (async () => {
        try {
          const subscription = ctx.event.subscribe({ signal: controller.signal });
          if (subscription && typeof subscription[Symbol.asyncIterator] === "function") {
            for await (const event of subscription) {
              if (controller.signal.aborted) break;
              await handle(event);
            }
          } else if (typeof ctx.event.subscribe === "function") {
            // callback form: subscribe(handler, { signal })
            const sub = ctx.event.subscribe((event) => { void handle(event); },
              { signal: controller.signal });
            if (sub && typeof sub[Symbol.asyncIterator] === "function") {
              for await (const event of sub) {
                if (controller.signal.aborted) break;
                await handle(event);
              }
            }
          }
        } catch (error) {
          if (!controller.signal.aborted) {
            await log(ctx, "warn", `event subscription ended: ${error?.message ?? error}`);
          }
        } finally {
          finished = true;
        }
      })();

      return () => {
        controller.abort();
        finished = true;
      };
    },
  };
}

let Plugin = { define: (definition) => definition };
try {
  const mod = await import("@opencode/plugin");
  Plugin = mod.Plugin ?? mod.default ?? Plugin;
} catch {
  // The package is the runtime dependency; the fallback keeps `node --test`
  // importable in a checkout without node_modules.
}

const definition = createDefinition(Plugin);

export { readThreshold, countTokens, limitsFromModels, PLUGIN_ID };
export default Plugin.define(definition);
