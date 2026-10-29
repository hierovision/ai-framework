/**
 * Delegation-observer TUI part (RM-069 AC4, AC9, AC11).
 *
 * Renders a persistent sidebar strip + footer count from the connected
 * server's EVENT STREAM (`ctx.data.listen`), never from heartbeat files. The
 * same pure reducer as the server part is used; every field and control is
 * asserted by `tui.test.ts` (the JSX itself is exercised by the live drill).
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
 * The loader resolves this file as <plugin-dir>/tui (binary `Zg` probe).
 */
import { readFileSync } from "node:fs";
import { For, Show, createMemo, createSignal } from "solid-js";

import {
  associateSessionInfo,
  createState,
  healthPath,
  observe,
  parseHealthRecord,
  tick,
  tuiConfig,
} from "./state.ts";
import {
  associationGap,
  createControls,
  degradationBanner,
  footerStatus,
  readStatusSnapshot,
  sidebarLines,
  visibleRows,
} from "./view.ts";

export const PLUGIN_ID = "delegation-observer";
const TICK_MS = 5_000;

function observerOptions(ctx: any) {
  return ctx?.options?.delegationObserver ?? {};
}

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

export function createTuiModel(ctx: any) {
  const config = tuiConfig(ctx);
  const state = createState(config, Date.now);
  const [version, setVersion] = createSignal(0);
  const [pluginStatus, setPluginStatus] = createSignal({ loaded: true, state: "active" });
  const [serverHealth, setServerHealth] = createSignal<string | null>(null);
  const bump = () => setVersion((v) => v + 1);

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

  // Bootstrap: children that already exist when the TUI starts.
  const bootstrap = () => {
    try {
      for (const info of ctx.data.session.list()) {
        associateSessionInfo(state, {
          id: info.id,
          parentID: info.parentID,
          title: info.title,
          agent: info.agent,
          time: info.time,
        });
      }
    } catch {
      // A failed bootstrap is not fatal: events still associate new children.
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

  const rows = createMemo(() => {
    version();
    return visibleRows(state, Date.now());
  });

  const banner = createMemo(() => {
    version();
    const status = pluginStatus();
    let sessions: any[] = [];
    try {
      sessions = ctx.data.session.list().map((s: any) => ({
        ...s,
        status: ctx.data.session.status(s.id),
      }));
    } catch {
      sessions = [];
    }
    const gap = associationGap(sessions, rows());
    const stale = state.lastEventAt !== null
      && rows().some((r) => r.status === "running")
      && Date.now() - state.lastEventAt > state.config.stallSeconds * 2000;
    return degradationBanner({
      pluginLoaded: status.loaded,
      pluginState: status.state,
      connection: stale ? "unavailable" : state.connection,
      disabled: config.enabled === false,
      serverHealth: serverHealth(),
      runningChildren: gap.runningChildren,
      associatedActive: gap.associatedActive,
    });
  });

  async function pickDelegate() {
    const list = rows();
    if (!list.length) {
      ctx.ui.toast.show({ message: "no delegates observed", variant: "info" });
      return null;
    }
    if (list.length === 1) return list[0];
    const sessionID = await ctx.ui.dialog.select({
      title: "Delegate",
      placeholder: "filter",
      options: list.map((row) => ({
        title: `${row.agent} ${row.sessionID}`,
        value: row.sessionID,
        description: `${row.status} · ${row.phase}`,
      })),
    });
    return list.find((row) => row.sessionID === sessionID) ?? null;
  }

  async function runControl(id: string, input?: any) {
    const row = await pickDelegate();
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
    refreshServerHealth();
    const warning = banner();
    if (!warning) {
      await refreshPlugin();
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
        run: () => runControl("focus"),
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
    state.connection = "disconnected";
  };

  return { state, rows, banner, refreshPlugin, version, dispose };
}

function StatusStrip(props: any) {
  return (
    <box flexDirection="column">
      <Show when={props.banner()}>
        <text>! {props.banner()}</text>
      </Show>
      <Show when={props.rows().length > 0}>
        <text>Delegates</text>
        <For each={sidebarLines(props.rows(), 8)}>
          {(line) => <text>{line}</text>}
        </For>
      </Show>
    </box>
  );
}

function FooterCount(props: any) {
  return (
    <Show when={props.banner() || footerStatus(props.rows())}>
      <text>
        {props.banner() ? "! delegates unavailable" : footerStatus(props.rows())}
      </text>
    </Show>
  );
}

function DelegatePanel(props: any) {
  return (
    <box flexDirection="column" padding={1}>
      <text>Delegates — event stream</text>
      <Show when={props.banner()}>
        <text>! {props.banner()}</text>
      </Show>
      <For each={props.rows()}>
        {(row) => (
          <box flexDirection="column">
            <text>
              {row.agent} {row.sessionID} [{row.status}] {row.phase}
            </text>
            <text>
              elapsed {row.elapsed} · quiet {row.quiet} · tok {row.tokensIn}/
              {row.tokensOut} · ${row.cost.toFixed(3)}
              {row.needsInput ? ` · needs ${row.needsInput}` : ""}
              {row.warning ? ` · ! ${row.warning}` : ""}
            </text>
          </box>
        )}
      </For>
      <text>
        thresholds: stall {props.state.config.stallSeconds}s · call{" "}
        {props.state.config.callSeconds}s · loop {props.state.config.loopRepeats}x
        · generation {props.state.config.generationSeconds}s
      </text>
    </box>
  );
}

export function createDefinition(Plugin: any) {
  return {
    id: PLUGIN_ID,
    async setup(ctx: any) {
      const model = createTuiModel(ctx);
      const disposers = [
        ctx.ui.slot({
          append: "sidebar.content",
          render: () => <StatusStrip rows={model.rows} banner={model.banner} />,
        }),
        ctx.ui.slot({
          append: "home.footer.status",
          render: () => <FooterCount rows={model.rows} banner={model.banner} />,
        }),
        ctx.ui.slot({
          append: "session.panel",
          render: (input: any) => (
            <Show when={input?.name === "delegates"}>
              <DelegatePanel rows={model.rows} banner={model.banner} state={model.state} />
            </Show>
          ),
        }),
      ];
      if (observerOptions(ctx).enabled === false) {
        ctx.ui.toast.show({
          message: "delegation-observer disabled — watchdog/observer fallback only",
          variant: "warning",
        });
      }
      return () => {
        model.dispose();
        for (const dispose of disposers) {
          try {
            dispose?.();
          } catch {
            // Slot teardown must not throw out of the plugin cleanup.
          }
        }
      };
    },
  };
}

let Plugin: any = { define: (definition: any) => definition };
try {
  const mod: any = await import("@opencode/plugin/tui");
  Plugin = mod.Plugin ?? mod.default ?? Plugin;
} catch {
  // The package is the runtime dependency; the fallback keeps the module
  // importable where the host provides the real definition.
}

export default Plugin.define(createDefinition(Plugin));
