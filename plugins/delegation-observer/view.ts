/**
 * Pure projections and command builders for the delegation TUI.
 *
 * The Solid component in `tui.tsx` only renders these values and wires the
 * commands to keymap/slots; every field, state, control and client call is
 * asserted by `tui.test.ts` without a DOM harness.
 */

import type { Delegate, ObserverState } from "./state.ts";

type Status = Delegate["status"];

export interface DelegateRow {
  sessionID: string;
  parentID: string;
  via: string;
  agent: string;
  task: string;
  status: Status;
  phase: string;
  elapsedMs: number;
  quietMs: number;
  elapsed: string;
  quiet: string;
  tokensIn: number;
  tokensOut: number;
  cost: number;
  warning: string | null;
  needsInput: string | null;
  terminal: string | null;
}

const STATUS_ORDER: Record<Status, number> = { waiting: 0, warning: 1, failed: 2, running: 3, completed: 4 };
const FOOTER_ORDER: Record<Status, number> = { running: 0, waiting: 1, warning: 2, failed: 3, completed: 4 };

export function projectDelegate(delegate: Delegate, now: number = Date.now()): DelegateRow {
  const elapsedMs = Math.max(0, now - delegate.startedAt);
  const quietMs = Math.max(0, now - delegate.lastActivityAt);
  return {
    sessionID: delegate.sessionID,
    parentID: delegate.orchestratorID,
    via: delegate.via,
    agent: delegate.agent,
    task: delegate.task,
    status: delegate.status,
    phase: delegate.phase,
    elapsedMs,
    quietMs,
    elapsed: formatDuration(elapsedMs),
    quiet: formatDuration(quietMs),
    tokensIn: delegate.tokens.input,
    tokensOut: delegate.tokens.output,
    cost: delegate.cost,
    warning: delegate.warning,
    needsInput: delegate.needsInput
      ? `${delegate.needsInput.kind}: ${delegate.needsInput.detail}`
      : null,
    terminal: delegate.terminal ? delegate.terminal.outcome : null,
  };
}

export function visibleRows(state: ObserverState, now: number = Date.now()): DelegateRow[] {
  const rows = [...state.delegates.values()].map((d) => projectDelegate(d, now));
  rows.sort((a, b) => {
    const attention = statusRank(a) - statusRank(b);
    if (attention !== 0) return attention;
    return a.sessionID.localeCompare(b.sessionID);
  });
  return rows;
}

function statusRank(row: DelegateRow): number {
  return STATUS_ORDER[row.status] ?? 5;
}

export function formatDuration(ms: number): string {
  const total = Math.max(0, Math.round(ms / 1000));
  if (total < 90) return `${total}s`;
  const minutes = Math.floor(total / 60);
  if (minutes < 90) return `${minutes}m${String(total % 60).padStart(2, "0")}s`;
  return `${Math.floor(minutes / 60)}h${String(minutes % 60).padStart(2, "0")}m`;
}

export function footerStatus(rows: DelegateRow[]): string {
  if (!rows.length) return "";
  const counts = new Map<Status, number>();
  for (const row of rows) counts.set(row.status, (counts.get(row.status) ?? 0) + 1);
  const parts = [...counts.entries()]
    .sort((a, b) => (FOOTER_ORDER[a[0]] ?? 5) - (FOOTER_ORDER[b[0]] ?? 5))
    .map(([status, count]) => `${count} ${status}`);
  return `delegates ${rows.length} · ${parts.join(" · ")}`;
}

/** One compact line per delegate, clipped so the sidebar never reflows. */
export function sidebarLines(rows: DelegateRow[], max: number = 8): string[] {
  return rows.slice(0, max).map((row) => {
    const mark = row.status === "waiting" || row.status === "warning" || row.status === "failed" ? "!" : "·";
    const detail = row.needsInput ?? row.phase;
    const line = `${mark} ${row.agent} ${row.status}: ${detail} · ${row.elapsed} · q${row.quiet}`;
    return line.length <= 64 ? line : `${line.slice(0, 61)}...`;
  });
}

/**
 * Control descriptors. `enabled` is decision logic (tested); `run` performs
 * the exact typed call and is only invoked from the TUI keymap/commands.
 */
export function createControls(row: Pick<DelegateRow, "sessionID" | "status" | "terminal">, { client, ui }: { client?: any; ui?: any } = {}) {
  const terminal = Boolean(row.terminal) || row.status === "completed" || row.status === "failed";
  const running = row.status === "running" || row.status === "warning";
  return [
    {
      id: "focus",
      title: "Focus delegate",
      enabled: true,
      run: async () => {
        if (ui?.tabs?.focus) {
          const ok = ui.tabs.focus(row.sessionID);
          if (ok) return { ok: true, call: "tabs.focus" };
        }
        ui?.router?.navigate?.({ type: "session", sessionID: row.sessionID });
        return { ok: true, call: "router.navigate" };
      },
    },
    {
      id: "steer",
      title: "Steer delegate",
      enabled: !terminal,
      reason: terminal ? "delegate is terminal" : undefined,
      run: async (text?: string) => {
        const prompt = String(text ?? "").trim();
        if (!prompt) return { ok: false, reason: "empty-prompt" };
        if (terminal) return { ok: false, reason: "terminal" };
        if (!client?.session?.prompt) return { ok: false, reason: "no-client" };
        await client.session.prompt({
          sessionID: row.sessionID,
          text: prompt,
          delivery: "steer",
        });
        return { ok: true, call: "session.prompt", delivery: "steer" };
      },
    },
    {
      id: "interrupt",
      title: "Interrupt delegate",
      enabled: running,
      reason: running ? undefined : "delegate is not running",
      run: async () => {
        if (!running) return { ok: false, reason: "not-running" };
        if (!client?.session?.interrupt) return { ok: false, reason: "no-client" };
        await client.session.interrupt({ sessionID: row.sessionID });
        return { ok: true, call: "session.interrupt" };
      },
    },
  ];
}

/**
 * Visible degradation (AC11). Every condition names the fallback; a healthy
 * observer returns null and the TUI shows no banner.
 */
export function degradationBanner({
  pluginLoaded = true,
  pluginState = "active",
  connection = "connected",
  disabled = false,
  runningSessions = 0,
  associated = 0,
}: {
  pluginLoaded?: boolean;
  pluginState?: string;
  connection?: string;
  disabled?: boolean;
  runningSessions?: number;
  associated?: number;
} = {}): string | null {
  if (!pluginLoaded) {
    return "delegation-observer not loaded — no live delegate view; the watchdog/observer fallback (heartbeat, wake) is authoritative.";
  }
  if (typeof pluginState === "string" && pluginState.startsWith("failed")) {
    return `delegation-observer load failed: ${pluginState.replace(/^failed:?\s*/, "")} — no live delegate view; the watchdog/observer fallback is authoritative.`;
  }
  if (disabled) {
    return "delegation-observer disabled by configuration — no live delegate view; the watchdog/observer fallback is authoritative.";
  }
  if (connection === "disconnected") {
    return "delegation-observer event stream disconnected — showing last known state only; the watchdog/observer fallback is authoritative.";
  }
  if (connection === "unavailable") {
    return "delegation-observer is not receiving events — no live visibility; the watchdog/observer fallback is authoritative.";
  }
  if (runningSessions > associated) {
    const missing = runningSessions - associated;
    return `${runningSessions} running session(s), ${missing} with no delegate association — no live visibility for them; the watchdog/observer fallback is authoritative.`;
  }
  return null;
}
