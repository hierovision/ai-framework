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
 * Trust boundary (review M6): a title marker is a claim, not proof. Before the
 * first synthetic message to a parent, the parent is looked up and must be a
 * root session (no `parentID`). An unverified parent keeps its delegate row in
 * the local view but receives NO injected message; the drop is logged and
 * surfaced in the shared health record.
 *
 * Degradation is never silent: a failed subscription, a closed stream, a
 * rejected synthetic message, or a dropped unverified milestone is written to
 * stderr AND to the shared health record the TUI part reads
 * (`<location>/.scratch/delegation-observer/health.json`).
 *
 * V2 contract used (validated against @opencode/plugin 2.1.4,
 * @opencode/client 2.1.4, 2026-10-29):
 *   - Plugin.define({ id, setup })                     -> definition
 *   - ctx.event.subscribe({ signal }) -> AsyncIterable  -> OpenCodeEvent
 *   - ctx.session.list() / ctx.session.get({ sessionID })
 *   - ctx.session.synthetic({ sessionID, text, description, metadata })
 *   - entrypoints are resolved by the loader as <dir>/server and <dir>/tui
 *     (`Zg` in the 2.1.4 binary), so no package export map is involved.
 */

import { mkdirSync, renameSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

import {
  DEFAULTS,
  type ObserverConfig,
  associateSessionInfo,
  createState,
  degrade,
  disconnect,
  healthPath,
  observe,
  parseDelegationTitle,
  tick,
} from "./state.ts";

export const PLUGIN_ID = "delegation-observer";
const TICK_MS = 5_000;
const TRUST_RETRY_MS = 60_000;

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
  healthFile?: string | null;
  onHealthWrite?: (record: Record<string, unknown>) => void;
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
  const controller = new AbortController();
  let stopped = false;
  let timer: ReturnType<typeof setInterval> | null = null;
  let lastHealth = "";
  const healthFile = options.healthFile
    ?? config.healthFile
    ?? healthPath(ctx?.location?.directory);

  const writeHealth = () => {
    if (!healthFile) return;
    // Write on a meaningful state change only: a hot event loop must not keep
    // rewriting the health record just to advance a timestamp.
    const signature = `${state.connection}|${state.degradation ?? ""}`;
    if (signature === lastHealth) return;
    lastHealth = signature;
    const record = {
      connection: state.connection,
      degradation: state.degradation,
      updated: state.now(),
    };
    const text = JSON.stringify(record);
    try {
      options.onHealthWrite?.(record);
      mkdirSync(dirname(healthFile), { recursive: true });
      const tmp = `${healthFile}.tmp`;
      writeFileSync(tmp, text + "\n", "utf8");
      renameSync(tmp, healthFile);
    } catch (error) {
      log("warn", "cannot write the observer health record", {
        file: healthFile, error: String((error as Error)?.message ?? error),
      });
    }
  };

  // --- trust (review M6) ---------------------------------------------------
  const trust = new Map<string, {
    trusted: boolean; checkedAt: number; location?: string; rootID?: string;
  }>();
  const warned = new Set<string>();
  const MAX_TREE_HOPS = 8;

  function sameDirectory(a?: string | null, b?: string | null): boolean {
    if (!a || !b) return true; // unknown -> do not suppress
    return a.replace(/\/+$/, "") === b.replace(/\/+$/, "");
  }

  /**
   * Resolve the orchestrator for a delegate. A depth-2 child's immediate
   * parent is a worker (`parentID` set); its milestones belong to the ROOT of
   * that chain. Walk up (bounded), trust only a root, and remember both the
   * root and its location. The location is also the emitter key: a service
   * activates the plugin once per location, so only the owning instance may
   * emit (otherwise every location duplicates the milestone).
   */
  async function resolveParent(parentID: string) {
    if (!parentID) return { trusted: false, rootID: undefined, location: undefined };
    const cached = trust.get(parentID);
    const now = Date.now();
    if (cached && (cached.trusted || now - cached.checkedAt < TRUST_RETRY_MS)) {
      return cached;
    }
    let current: string | undefined = parentID;
    let rootID: string | undefined;
    let location: string | undefined;
    for (let hop = 0; hop < MAX_TREE_HOPS && current; hop += 1) {
      let info: any;
      try {
        info = await ctx.session.get({ sessionID: current });
      } catch {
        info = null;
      }
      if (!info) break;
      if (info.location?.directory) location = info.location.directory;
      if (!info.parentID) {
        // A top-level run-vehicle child has no parentID but names its
        // orchestrator in the title marker; follow it to the real root.
        const marker = parseDelegationTitle(info.title ?? "");
        if (marker?.orchestratorID && marker.orchestratorID !== current) {
          current = marker.orchestratorID;
          continue;
        }
        rootID = current;
        break;
      }
      current = info.parentID;
    }
    const entry = { trusted: Boolean(rootID), checkedAt: now, rootID, location };
    trust.set(parentID, entry);
    if (!entry.trusted) {
      degrade(state, `unverified orchestrator ${parentID}: synthetic milestone dropped`);
      if (!warned.has(parentID)) {
        warned.add(parentID);
        log("warn", "unverified orchestrator: synthetic milestone dropped", { parentID });
      }
    }
    return entry;
  }

  const emit = async (result: {
    milestones: Array<{
      parentID: string; sessionID: string; kind: string;
      text: string; description: string;
    }>;
  }) => {
    for (const m of result.milestones) {
      const parent = await resolveParent(m.parentID);
      if (!parent.trusted) continue;
      if (!sameDirectory(ctx?.location?.directory, parent.location)) continue;
      try {
        // A milestone is context, not work: deliver it as a steer message and
        // never resume generation (AC5). Without `resume:false` the session
        // starts a turn (observed live 2026-10-29).
        await ctx.session.synthetic({
          sessionID: parent.rootID,
          text: m.text,
          description: m.description,
          delivery: "steer",
          resume: false,
          metadata: {
            delegate: m.sessionID, kind: m.kind,
            observer: process.pid, location: ctx?.location?.directory ?? null,
          },
        });
      } catch (error) {
        degrade(state, `synthetic failed: ${(error as Error)?.message ?? error}`);
        log("warn", "synthetic milestone failed", {
          sessionID: m.parentID, kind: m.kind, error: String((error as Error)?.message ?? error),
        });
      }
    }
    writeHealth();
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
    healthFile: healthFile ?? null,
    location: ctx?.location?.directory ?? null,
    pid: process.pid,
  });
  writeHealth();

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
          time: info.time,
          idleOutcome: info.idleOutcome ?? info.idle_outcome ?? null,
          // A list entry that already reports live status is real evidence;
          // everything else is discovery only (live defect, 2026-10-30).
          active: info.status === "running" || info.status === "busy" ? true : undefined,
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
      stream = ctx.event.subscribe({ signal: controller.signal });
    } catch (error) {
      // Some hosts expose only the no-argument form.
      try {
        stream = ctx.event.subscribe();
      } catch (fatal) {
        disconnect(state, `event stream failed: ${(fatal as Error)?.message ?? fatal}`);
        log("warn", `event stream ended: ${(fatal as Error)?.message ?? fatal}`);
        writeHealth();
        return;
      }
    }
    try {
      for await (const event of stream) {
        if (stopped) break;
        const result = observe(state, event);
        if (result.milestones.length) await emit(result);
        else writeHealth();
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
    writeHealth();
  })();

  return {
    state,
    config,
    done,
    healthFile,
    lastLog: () => logs.join("\n"),
    async stop() {
      stopped = true;
      if (timer) clearInterval(timer);
      try {
        controller.abort();
      } catch {
        // abort is best-effort on hosts that ignore the signal
      }
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
