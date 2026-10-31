/**
 * Delegation-observer TUI model (RM-069 AC4, AC9, AC11) — no JSX.
 *
 * Everything decision-bearing lives here so `node --test` can construct the
 * real model against a mock host (`model.test.ts`). `tui.tsx` is a thin view:
 * JSX components plus `createDefinition`, nothing else.
 *
 * V2 TUI contract used (verified against @opencode/plugin 2.1.4 /
 * @opencode/client 2.1.4 on 2026-10-29):
 *   - Plugin.define({ id, setup }) from @opencode/plugin/tui
 *   - ctx.data.listen(handler), ctx.data.session.{list,status,permission,form}
 *   - ctx.ui.slot({ append|prepend|before|after|replace, render })
 *     slots: sidebar.content, home.footer.status, session.panel
 *   - ctx.ui.toast.show, ctx.attention.notify, ctx.keymap.layer,
 *     ctx.ui.dialog.{select,prompt}, ctx.ui.tabs.focus, ctx.ui.panel.open
 *   - ctx.client.session.{prompt,interrupt} and ctx.client.plugin.list
 *
 * Declaration order matters: solid's `createMemo` evaluates its callback
 * synchronously, so every binding a memo reads must already be initialized.
 * That is not a style preference — a `const` declared below the memo is in its
 * temporal dead zone and throws `ReferenceError` at model construction, which
 * is how the TUI part fails to load (review F9).
 */
import { mkdirSync, readFileSync, renameSync, unlinkSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { createMemo, createSignal } from "solid-js";

import {
  associateSessionInfo,
  createState,
  healthPath,
  markActive,
  observe,
  parseHealthRecord,
  tick,
  tuiConfig,
} from "./state.ts";
import {
  associationGap,
  createControls,
  degradationBanner,
  readLiveMap,
  readStatusSnapshot,
  selectableRows,
  visibleRows,
} from "./view.ts";

export const PLUGIN_ID = "delegation-observer";
export const TICK_MS = 5_000;

/** The live inbox a row belongs to: action targets vs collapsed history. */
export type ModelMode = "live" | "history";

/**
 * The server-side plugin record, via the typed client. Absence is a real
 * answer (not loaded); an unreachable list is reported as unknown and the
 * banner says so instead of pretending the observer is healthy.
 */
export async function readPluginStatus(client: any, directory?: string) {
  try {
    // /api/plugin is location-scoped: without the TUI's location the list is
    // empty on a shared service, which would read as "not loaded" (review M4).
    const input = directory ? { location: { directory } } : {};
    const result = await client?.plugin?.list?.(input);
    const list = Array.isArray(result) ? result : (result?.data ?? []);
    const entry = list.find((p: any) => p?.id === PLUGIN_ID);
    if (!entry) return { loaded: false, state: "missing", tui: false };
    const state = entry.state?.status === "failed"
      ? `failed: ${entry.state.error ?? "unknown error"}`
      : "active";
    return { loaded: true, state, tui: Boolean(entry.features?.tui) };
  } catch (error) {
    return { loaded: false, state: "unknown", tui: false, error: String(error) };
  }
}

/**
 * Build the TUI model against a plugin context. Every external read is
 * guarded: a host that throws or returns a non-array list degrades to a
 * visible banner, never to a startup crash.
 */
export function createTuiModel(ctx: any) {
  const config = tuiConfig(ctx);
  const state = createState(config, Date.now);
  const [version, setVersion] = createSignal(0);
  const [pluginStatus, setPluginStatus] = createSignal({ loaded: true, state: "active" });
  const [serverHealth, setServerHealth] = createSignal<string | null>(null);
  const [liveMap, setLiveMap] = createSignal<"ok" | "unavailable">("ok");
  const bump = () => setVersion((v) => v + 1);

  // Presence marker for the independent sentinel: when this TUI part fails to
  // load, no marker exists and the sentinel shows the fallback line.
  const presenceFile = config.presenceFile
    ?? (ctx?.location?.directory
      ? join(ctx.location.directory, ".scratch", "delegation-observer", "tui.json")
      : null);
  const writePresence = () => {
    if (!presenceFile) return;
    try {
      mkdirSync(dirname(presenceFile), { recursive: true });
      const tmp = `${presenceFile}.tmp`;
      writeFileSync(tmp, JSON.stringify({ pid: process.pid, ts: Date.now() }) + "\n", "utf8");
      renameSync(tmp, presenceFile);
    } catch {
      // presence is advisory; the banner covers absence
    }
  };
  writePresence();
  const presenceTimer = setInterval(writePresence, 10_000);
  presenceTimer?.unref?.();

  // Shared degradation channel (server -> TUI). Read on events/degradation
  // checks only, never as the progress source, and throttled so a busy stream
  // does not turn into file polling.
  const healthFile = config.healthFile
    ?? healthPath(ctx?.location?.directory ?? ctx?.location?.path);
  let lastHealthRead = 0;
  const refreshServerHealth = () => {
    if (!healthFile) return;
    const now = Date.now();
    if (now - lastHealthRead < 1_000) return;
    lastHealthRead = now;
    try {
      const record = parseHealthRecord(readFileSync(healthFile, "utf8"));
      setServerHealth(record?.degradation ?? null);
    } catch {
      // Absent health file is not degradation by itself.
    }
  };

  // --- host reads (total: a failure is a banner, never an exception) -------

  // The raw read keeps "no answer" distinguishable from "no sessions": the
  // live map must report unavailability, while bootstrap only needs a safe
  // iterable. A null/undefined/non-array list is never a `for...of` crash
  // (review F10).
  const rawSessionList = (): unknown => ctx?.data?.session?.list?.();
  const sessionList = (): any[] => {
    try {
      const listed = rawSessionList();
      return Array.isArray(listed) ? listed : [];
    } catch {
      return [];
    }
  };
  const sessionStatus = (sessionID: string) => ctx.data.session.status(sessionID);

  /**
   * Refresh the live active map — the only evidence a discovered row may use.
   * Returns false when the host could not answer, which the banner reports
   * instead of letting every discovered row silently age into "stale".
   */
  const refreshActive = () => {
    const map = readLiveMap(rawSessionList, sessionStatus);
    setLiveMap(map.available ? "ok" : "unavailable");
    for (const entry of map.entries) {
      markActive(state, entry.sessionID, entry.live);
    }
    return map.available;
  };

  const bootstrap = () => {
    refreshActive(); // fill the map first: association consults it
    for (const info of sessionList()) {
      associateSessionInfo(state, {
        id: info?.id,
        parentID: info?.parentID,
        title: info?.title,
        agent: info?.agent,
        time: info?.time,
        outcome: info?.outcome,
        active: info?.active,
      });
    }
  };

  const alertFor = (milestone: any) => {
    if (!milestone.attention && milestone.kind !== "terminal") return;
    try {
      ctx.ui.toast.show({
        title: `delegate ${milestone.kind}`,
        message: milestone.text,
        variant: milestone.kind === "terminal" ? "success" : "warning",
      });
    } catch {
      // Toasts are advisory; the strip still renders.
    }
    const sound = milestone.kind === "needs-input" ? "permission"
      : milestone.kind === "terminal" ? "subagent_done" : "question";
    try {
      void ctx.attention?.notify?.({
        title: `delegate ${milestone.kind}`,
        message: milestone.text,
        sound: { name: sound },
      });
    } catch {
      // Attention is best-effort on every host.
    }
  };

  const apply = (result: any) => {
    for (const milestone of result.milestones) alertFor(milestone);
  };

  // AC3: every event re-renders. The interval below exists only for the
  // clock-driven classification (quiet/stall/dead), never as the refresh path.
  const stopListening = ctx.data.listen((event: any) => {
    apply(observe(state, event?.details ?? event));
    refreshServerHealth();
    bump();
  });

  bootstrap();
  const timer = setInterval(() => {
    refreshActive();
    apply(tick(state));
    refreshServerHealth();
    bump();
  }, TICK_MS);
  timer?.unref?.();

  const refreshPlugin = async () => {
    setPluginStatus(await readPluginStatus(ctx.client, ctx?.location?.directory));
    refreshServerHealth();
    bump();
  };
  void refreshPlugin();
  refreshServerHealth();

  // --- projections ---------------------------------------------------------
  //
  // The `live*` functions are the single implementation; the memos only add
  // the reactive version dependency for the client renderer. Tests read the
  // functions (fresh on every call), the view reads the memos.

  const liveRows = () => visibleRows(state, Date.now());

  /** Sessions with their live status, for the association-gap count only. */
  const liveSessionRows = () => {
    const map = readLiveMap(rawSessionList, sessionStatus);
    if (!map.available) return [];
    const live = new Map(map.entries.map((entry) => [entry.sessionID, entry.live]));
    return map.sessions.map((session) => ({
      ...session,
      status: live.get(session.id ?? session.sessionID ?? "") ? "running" : "idle",
    }));
  };

  const liveBanner = () => {
    const status = pluginStatus();
    const current = liveRows();
    const gap = associationGap(liveSessionRows(), current);
    const stale = state.lastEventAt !== null
      && current.some((r) => r.status === "running")
      && Date.now() - state.lastEventAt > state.config.stallSeconds * 2000;
    return degradationBanner({
      pluginLoaded: status.loaded,
      pluginState: status.state,
      connection: stale ? "unavailable" : state.connection,
      disabled: config.enabled === false,
      serverHealth: serverHealth(),
      runningChildren: gap.runningChildren,
      associatedActive: gap.associatedActive,
      liveMap: liveMap(),
    });
  };

  // Eager by contract: solid's createMemo evaluates here, so every binding
  // read above must already be initialized (review F9).
  const rows = createMemo(() => {
    version();
    return liveRows();
  });

  const banner = createMemo(() => {
    version();
    return liveBanner();
  });

  // --- owner actions ------------------------------------------------------

  async function choose(mode: ModelMode, title: string) {
    const current = liveRows();
    const list = mode === "history"
      ? current.filter((row) => row.stale)
      : selectableRows(current);
    if (!list.length) {
      ctx.ui.toast.show({
        message: mode === "history" ? "no delegate history" : "no delegates observed",
        variant: "info",
      });
      return null;
    }
    if (list.length === 1) return list[0];
    const sessionID = await ctx.ui.dialog.select({
      title,
      placeholder: "filter",
      options: list.map((row) => ({
        title: `${row.agent} ${row.sessionID}`,
        value: row.sessionID,
        description: `${row.status} · ${row.phase}`,
      })),
    });
    return list.find((row) => row.sessionID === sessionID) ?? null;
  }

  /** Focus a delegate. `history` reaches collapsed rows (read-only there). */
  async function focusDelegate(mode: ModelMode = "live") {
    const row = await choose(mode, mode === "history" ? "Delegate history" : "Delegate");
    if (!row) return null;
    if (ctx.ui?.tabs?.focus?.(row.sessionID)) return row;
    ctx.ui?.router?.navigate?.({ type: "session", sessionID: row.sessionID });
    return row;
  }

  async function runControl(id: string, input?: any) {
    const row = await choose("live", "Delegate");
    if (!row) return;
    const control = createControls(row, { client: ctx.client, ui: ctx.ui })
      .find((c) => c.id === id);
    if (!control) return;
    if (!control.enabled) {
      ctx.ui.toast.show({ message: control.reason ?? "unavailable", variant: "warning" });
      return;
    }
    const result: any = input === undefined
      ? await control.run()
      : await control.run(input);
    if (id === "interrupt" && result?.ok) {
      ctx.ui.toast.show({
        message: `interrupt accepted (session ${row.sessionID}${result.interrupted === null ? "" : `, interrupted=${result.interrupted}`})`,
        variant: "info",
      });
      return;
    }
    if (result && result.ok === false) {
      ctx.ui.toast.show({ message: result.reason ?? "failed", variant: "warning" });
    }
  }

  async function showStatus() {
    // Check the plugin record first: the banner must reflect the host's
    // current answer, not the one captured at construction.
    await refreshPlugin();
    refreshServerHealth();
    const warning = liveBanner();
    if (!warning) {
      ctx.ui.toast.show({ message: "delegation observer healthy", variant: "info" });
      return;
    }
    let fallback = "";
    if (config.statusFile) {
      try {
        const snapshot = readStatusSnapshot(readFileSync(config.statusFile, "utf8"));
        if (snapshot) {
          fallback = ` · watchdog: ${snapshot.agent} ${snapshot.outcome}`
            + (snapshot.terminal ? " (terminal)" : "");
        }
      } catch {
        fallback = "";
      }
    }
    ctx.ui.toast.show({
      title: "delegation degraded",
      message: `${warning}${fallback}`,
      variant: "warning",
    });
  }

  ctx.keymap.layer(() => ({
    group: "delegation",
    commands: [
      {
        id: "delegation.focus",
        title: "Delegation: focus a delegate",
        group: "delegation",
        palette: true,
        bind: "alt+d",
        slash: { name: "delegation-focus" },
        run: () => focusDelegate("live"),
      },
      {
        id: "delegation.steer",
        title: "Delegation: steer a delegate",
        group: "delegation",
        palette: true,
        bind: "alt+s",
        slash: { name: "delegation-steer", arguments: true },
        run: async (input?: string) => {
          if (typeof input === "string" && input.trim()) {
            await runControl("steer", input);
            return;
          }
          const text = await ctx.ui.dialog.prompt({
            title: "Steer delegate",
            description: "Sent to the same session id (delivery=steer)",
            placeholder: "additional instruction",
          });
          if (text !== undefined) await runControl("steer", text);
        },
      },
      {
        id: "delegation.interrupt",
        title: "Delegation: interrupt a delegate",
        group: "delegation",
        palette: true,
        bind: "alt+x",
        slash: { name: "delegation-interrupt" },
        run: () => runControl("interrupt"),
      },
      {
        id: "delegation.history",
        title: "Delegation: inspect collapsed delegate history",
        group: "delegation",
        palette: true,
        bind: "alt+g",
        slash: { name: "delegation-history" },
        run: () => focusDelegate("history"),
      },
      {
        id: "delegation.panel",
        title: "Delegation: open the delegate panel",
        group: "delegation",
        palette: true,
        bind: "alt+p",
        slash: { name: "delegation-panel" },
        run: () => { ctx.ui.panel.open("delegates"); },
      },
      {
        id: "delegation.status",
        title: "Delegation: check observer health",
        group: "delegation",
        palette: true,
        bind: "alt+h",
        slash: { name: "delegation-status" },
        run: () => showStatus(),
      },
    ],
  }));

  const dispose = () => {
    try {
      stopListening?.();
    } catch {
      // ignore teardown faults
    }
    clearInterval(timer);
    clearInterval(presenceTimer);
    if (presenceFile) {
      try {
        unlinkSync(presenceFile);
      } catch {
        // already gone
      }
    }
    state.connection = "disconnected";
  };

  return {
    state,
    rows,
    banner,
    liveRows,
    liveBanner,
    refreshPlugin,
    version,
    dispose,
    focusDelegate,
    showStatus,
  };
}

export type TuiModel = ReturnType<typeof createTuiModel>;
