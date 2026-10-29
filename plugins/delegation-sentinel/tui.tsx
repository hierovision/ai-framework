/**
 * Delegation sentinel TUI companion (RM-069 AC11 fallback).
 *
 * Loads independently of the observer. It checks the observer's plugin
 * record, its shared health record, and its TUI presence marker, then renders
 * ONE fallback line in the sidebar/footer when the observer is absent, failed,
 * disabled, disconnected or its TUI is not running. It never renders delegate
 * detail — that would claim visibility it does not have.
 *
 * 2.1.4 does not forward plugin options to the TUI part; the sentinel reads
 * the same documented env source as the observer (`DELEGATION_OBSERVER_*`)
 * plus its own `DELEGATION_SENTINEL_ENABLED`.
 */
import { readFileSync } from "node:fs";
import { Show, createMemo, createSignal, onCleanup } from "solid-js";

import {
  OBSERVER_ID,
  SENTINEL_ID,
  healthRecordPath,
  observerStatePath,
  parsePresence,
  sentinelBanner,
  sentinelEnabled,
} from "./sentinel.ts";

const TICK_MS = 5_000;

function readJson(path: string | null) {
  if (!path) return null;
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return null;
  }
}

export function createSentinelModel(ctx: any) {
  const enabled = sentinelEnabled(process.env);
  const location = ctx?.location?.directory ?? ctx?.location?.path;
  const presencePath = observerStatePath(location);
  const healthPath = healthRecordPath(location);
  const [version, setVersion] = createSignal(0);
  const [observer, setObserver] = createSignal<{ present: boolean; state: string }>({
    present: true, state: "active",
  });
  const bump = () => setVersion((v) => v + 1);

  const refresh = async () => {
    try {
      const result = await ctx?.client?.plugin?.list?.(
        location ? { location: { directory: location } } : {},
      );
      const list = Array.isArray(result) ? result : (result?.data ?? []);
      const entry = list.find((p: any) => p?.id === OBSERVER_ID);
      setObserver(entry
        ? {
          present: true,
          state: entry.state?.status === "failed"
            ? `failed: ${entry.state.error ?? "unknown error"}`
            : "active",
        }
        : { present: false, state: "missing" });
    } catch {
      // An unreachable list is reported as unknown, not healthy.
      setObserver({ present: false, state: "unknown" });
    }
    bump();
  };
  void refresh();
  const timer = setInterval(() => { void refresh(); }, TICK_MS);
  timer?.unref?.();

  const banner = createMemo(() => {
    version();
    const status = observer();
    const health = readJson(healthPath) ?? {};
    const presence = parsePresence(
      (() => {
        try {
          return readFileSync(presencePath ?? "", "utf8");
        } catch {
          return null;
        }
      })(),
    );
    const presenceAgeMs = presence ? Date.now() - presence.ts : null;
    return sentinelBanner({
      observerPresent: status.present,
      observerState: status.state,
      observerDisabled: process.env.DELEGATION_OBSERVER_ENABLED
        ? ["0", "false", "no", "off"].includes(
          String(process.env.DELEGATION_OBSERVER_ENABLED).trim().toLowerCase(),
        )
        : false,
      connection: health.connection ?? "connected",
      degradation: health.degradation ?? null,
      presenceAgeMs,
    });
  });

  const dispose = () => {
    clearInterval(timer);
  };

  return { banner, enabled, refresh, dispose, id: SENTINEL_ID };
}

function SentinelLine(props: any) {
  return (
    <Show when={props.model.enabled && props.model.banner()}>
      <text>! {props.model.banner()}</text>
    </Show>
  );
}

export function createDefinition(Plugin: any) {
  return {
    id: SENTINEL_ID,
    async setup(ctx: any) {
      const model = createSentinelModel(ctx);
      const disposers = [
        ctx.ui.slot({
          append: "sidebar.content",
          render: () => <SentinelLine model={model} />,
        }),
        ctx.ui.slot({
          append: "home.footer.status",
          render: () => <SentinelLine model={model} />,
        }),
      ];
      onCleanup(() => model.dispose());
      return () => {
        model.dispose();
        for (const dispose of disposers) {
          try {
            dispose?.();
          } catch {
            // teardown must not throw
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
  // The package is the runtime dependency; tests never import this module.
}

export default Plugin.define(createDefinition(Plugin));
