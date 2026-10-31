/**
 * Delegation-observer TUI view (RM-069 AC4, AC9, AC11).
 *
 * THIN VIEW ONLY: the model (`model.ts`) owns every read, timer, command and
 * decision and is exercised by `model.test.ts` against a mock host; this file
 * renders the projections and registers the slots. Nothing here may be the
 * only implementation of a behavior, because `node --test` cannot import JSX.
 *
 * V2 TUI contract used (verified against @opencode/plugin 2.1.4 /
 * @opencode/client 2.1.4 on 2026-10-29):
 *   - Plugin.define({ id, setup }) from @opencode/plugin/tui
 *   - ctx.ui.slot({ append|prepend|before|after|replace, render })
 *     slots: sidebar.content, home.footer.status, session.panel
 * The loader resolves this file as <plugin-dir>/tui (binary `Zg` probe).
 */
import { For, Show } from "solid-js";

import { PLUGIN_ID, createTuiModel } from "./model.ts";
import { footerStatus, sidebarLines } from "./view.ts";
import { tuiConfig } from "./state.ts";

export { PLUGIN_ID, TICK_MS, createTuiModel, readPluginStatus } from "./model.ts";

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
  const live = () => props.rows().filter((row: any) => !row.stale);
  const stale = () => props.rows().length - live().length;
  return (
    <box flexDirection="column" padding={1}>
      <text>Delegates — event stream</text>
      <Show when={props.banner()}>
        <text>! {props.banner()}</text>
      </Show>
      <For each={live()}>
        {(row: any) => (
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
      <Show when={stale() > 0}>
        <text>{stale()} stale delegates hidden (alt+g to inspect)</text>
      </Show>
      <text>
        thresholds: stall {props.state.config.stallSeconds}s · call{" "}
        {props.state.config.callSeconds}s · loop {props.state.config.loopRepeats}x
        · generation {props.state.config.generationSeconds}s · stale grace{" "}
        {props.state.config.staleGraceSeconds}s
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
      if (tuiConfig(ctx).enabled === false) {
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
