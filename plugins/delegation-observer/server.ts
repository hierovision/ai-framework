/**
 * Delegation-observer server part (RM-069).
 *
 * Subscribes to the connected server's event stream, associates every child
 * session with its orchestrator (parent_id or the run-vehicle title marker;
 * no side registry), reduces the stream with the shared pure reducer, and
 * appends rate-limited SYNTHETIC messages to the orchestrator session at
 * meaningful transitions. Synthetic messages add no model turn — the only
 * progress-path prompt remains the RM-058 terminal wake.
 *
 * Degradation is never silent: a failed subscription, a closed stream, or a
 * rejected synthetic message is logged to stderr (2.1.4's plugin context has
 * no log domain) and recorded on the state the TUI mirrors.
 *
 * V2 contract used (validated against @opencode/plugin 2.1.4,
 * @opencode/client 2.1.4, 2026-10-29):
 *   - Plugin.define({ id, setup })                     -> definition
 *   - ctx.event.subscribe({ signal }) -> AsyncIterable  -> OpenCodeEvent
 *   - ctx.session.list() -> { data: SessionInfo[] }
 *   - ctx.session.synthetic({ sessionID, text, description, metadata })
 *   - entrypoints are resolved by the loader as <dir>/server and <dir>/tui
 *     (`Zg` in the 2.1.4 binary), so no package export map is involved.
 */

import {
  DEFAULTS,
  type ObserverConfig,
  associateSessionInfo,
  createState,
  degrade,
  disconnect,
  observe,
  tick,
} from "./state.ts";

export const PLUGIN_ID = "delegation-observer";
const TICK_MS = 5_000;

function writeLog(level: string, message: string, extra: Record<string, unknown> = {}) {
  const line = JSON.stringify({ service: PLUGIN_ID, level, message, extra });
  try {
    if (process?.stderr?.write) {
      process.stderr.write(line + "\n");
      return line;
    }
  } catch {
    // Logging must never break observation.
  }
  return line;
}

/**
 * Start the observer against a plugin context. Exported separately from the
 * `Plugin.define` wrapper so tests can drive it with a fake context and clock.
 */
export function startObserver(ctx: any, options: {
  now?: () => number;
  intervalMs?: number;
  config?: Partial<ObserverConfig>;
} = {}) {
  const config = {
    ...DEFAULTS,
    ...(ctx?.options?.delegationObserver ?? {}),
    ...(options.config ?? {}),
  };
  const state = createState(config, options.now ?? Date.now);
  const intervalMs = options.intervalMs ?? TICK_MS;
  const logs: string[] = [];
  const log = (level: string, message: string, extra: Record<string, unknown> = {}) => {
    logs.push(writeLog(level, message, extra));
  };
  let stopped = false;
  let timer: ReturnType<typeof setInterval> | null = null;

  const emit = async (result: { milestones: Array<{ parentID: string; sessionID: string; kind: string; text: string; description: string }> }) => {
    for (const m of result.milestones) {
      try {
        await ctx.session.synthetic({
          sessionID: m.parentID,
          text: m.text,
          description: m.description,
          metadata: { delegate: m.sessionID, kind: m.kind },
        });
      } catch (error) {
        degrade(state, `synthetic failed: ${(error as Error)?.message ?? error}`);
        log("warn", "synthetic milestone failed", {
          sessionID: m.parentID, kind: m.kind, error: String((error as Error)?.message ?? error),
        });
      }
    }
  };

  const flush = async () => {
    const result = tick(state);
    if (result.milestones.length) await emit(result);
  };

  log("info", "delegation-observer initialized", {
    version: "2.1.4",
    enabled: config.enabled,
    stallSeconds: config.stallSeconds,
    callSeconds: config.callSeconds,
    loopRepeats: config.loopRepeats,
    generationSeconds: config.generationSeconds,
    milestoneMinIntervalSeconds: config.milestoneMinIntervalSeconds,
  });

  const done = (async () => {
    if (!config.enabled) return;
    try {
      const listed = await ctx.session.list();
      const sessions = Array.isArray(listed) ? listed : (listed?.data ?? []);
      for (const info of sessions) {
        associateSessionInfo(state, {
          id: info.id,
          parentID: info.parentID,
          title: info.title,
          agent: info.agent,
        });
      }
    } catch (error) {
      log("warn", "session bootstrap failed", { error: String((error as Error)?.message ?? error) });
    }
    if (intervalMs > 0 && typeof setInterval === "function") {
      timer = setInterval(() => { void flush(); }, intervalMs);
      timer?.unref?.();
    }
    let stream;
    try {
      stream = ctx.event.subscribe();
    } catch (error) {
      disconnect(state, `event stream failed: ${(error as Error)?.message ?? error}`);
      log("warn", `event stream ended: ${(error as Error)?.message ?? error}`);
      return;
    }
    try {
      for await (const event of stream) {
        if (stopped) break;
        const result = observe(state, event);
        if (result.milestones.length) await emit(result);
      }
      if (!stopped) {
        disconnect(state, "event stream ended");
        log("warn", "event stream ended: closed by the server");
      }
    } catch (error) {
      if (!stopped) {
        disconnect(state, `event stream ended: ${(error as Error)?.message ?? error}`);
        log("warn", `event stream ended: ${(error as Error)?.message ?? error}`);
      }
    }
  })();

  return {
    state,
    config,
    done,
    lastLog: () => logs.join("\n"),
    async stop() {
      stopped = true;
      if (timer) clearInterval(timer);
      return undefined;
    },
  };
}

/**
 * Build the V2 definition. The default export is what the loader consumes;
 * `createDefinition` is exported for `node --test`.
 */
export function createDefinition(Plugin: any) {
  return {
    id: PLUGIN_ID,
    async setup(ctx: any) {
      if (ctx?.options?.delegationObserver?.enabled === false) {
        logDisabled();
        return () => {};
      }
      const handle = startObserver(ctx);
      return () => handle.stop();
    },
  };
}

function logDisabled() {
  writeLog("info", "delegation-observer disabled by configuration", {});
}

let Plugin: any = { define: (definition: any) => definition };
try {
  const mod: any = await import("@opencode/plugin");
  Plugin = mod.Plugin ?? mod.default ?? Plugin;
} catch {
  // The package is the runtime dependency; the fallback keeps `node --test`
  // importable in a checkout without node_modules.
}

export default Plugin.define(createDefinition(Plugin));
