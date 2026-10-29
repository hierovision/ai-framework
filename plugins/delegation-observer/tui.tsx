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
 *   - ctx.ui.toast.show, ctx.attention.notify, ctx.ui.keymap.layer,
 *     ctx.ui.dialog.{select,prompt}, ctx.ui.tabs.focus, ctx.ui.panel.open
 *   - ctx.client.session.{prompt,interrupt} and ctx.client.plugin.list
 * The loader resolves this file as <plugin-dir>/tui (binary `Zg` probe).
 */
import { For, Show, createMemo, createSignal, onCleanup } from "solid-js";

import {
  associateSessionInfo,
  createState,
  tick,
  observe,
} from "./state.ts";
import {
  createControls,
  degradationBanner,
  footerStatus,
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
export async function readPluginStatus(client: any) {
  try {
    const result = await client?.plugin?.list?.({});
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
  const config = observerOptions(ctx);
  const state = createState(config, Date.now);
  const [version, setVersion] = createSignal(0);
  const [pluginStatus, setPluginStatus] = createSignal({ loaded: true, state: "active" });
  const bump = () => setVersion((v) => v + 1);

  // Bootstrap: children that already exist when the TUI starts.
  const bootstrap = () => {
    try {
      for (const info of ctx.data.session.list()) {
        associateSessionInfo(state, {
          id: info.id,
          parentID: info.parentID,
          title: info.title,
          agent: info.agent,
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
    if (result.milestones.length || result.alerts.length) bump();
  };

  const stopListening = ctx.data.listen((event: any) => {
    apply(observe(state, event?.details ?? event));
  });

  bootstrap();
  const timer = setInterval(() => {
    apply(tick(state));
    bump();
  }, TICK_MS);
  timer?.unref?.();

  const refreshPlugin = async () => {
    setPluginStatus(await readPluginStatus(ctx.client));
    bump();
  };
  void refreshPlugin();

  const rows = createMemo(() => {
    version();
    return visibleRows(state, Date.now());
  });

  const banner = createMemo(() => {
    version();
    const status = pluginStatus();
    let running = 0;
    try {
      running = ctx.data.session.list()
        .filter((s: any) => ctx.data.session.status(s.id) === "running").length;
    } catch {
      running = 0;
    }
    const stale = state.lastEventAt !== null
      && rows().some((r) => r.status === "running")
      && Date.now() - state.lastEventAt > state.config.stallSeconds * 2000;
    return degradationBanner({
      pluginLoaded: status.loaded,
      pluginState: status.state,
      connection: stale ? "unavailable" : state.connection,
      disabled: config.enabled === false,
      runningSessions: running,
      associated: rows().filter((r) => r.status === "running").length,
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
    if (result && result.ok === false) {
      ctx.ui.toast.show({ message: result.reason ?? "failed", variant: "warning" });
    }
  }

  ctx.ui.keymap.layer(() => ({
    commands: [
      {
        id: "delegation.focus",
        title: "Delegation: focus a delegate",
        group: "delegation",
        palette: true,
        run: () => runControl("focus"),
      },
      {
        id: "delegation.steer",
        title: "Delegation: steer a delegate",
        group: "delegation",
        palette: true,
        run: async () => {
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
        run: () => runControl("interrupt"),
      },
      {
        id: "delegation.panel",
        title: "Delegation: open the delegate panel",
        group: "delegation",
        palette: true,
        run: () => { ctx.ui.panel.open("delegates"); },
      },
      {
        id: "delegation.status",
        title: "Delegation: re-check observer status",
        group: "delegation",
        palette: true,
        run: () => refreshPlugin(),
      },
    ],
  }));

  onCleanup(() => {
    stopListening?.();
    clearInterval(timer);
    state.connection = "disconnected";
  });

  return { state, rows, banner, refreshPlugin, version };
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
