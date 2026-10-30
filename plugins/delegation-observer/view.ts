/**
 * Pure projections and command builders for the delegation TUI.
 *
 * The Solid component in `tui.tsx` only renders these values and wires the
 * commands to keymap/slots; every field, state, control and client call is
 * asserted by `tui.test.ts` without a DOM harness.
 */
import type { Delegate, ObserverState } from "./state.ts";
import { parseDelegationTitle } from "./state.ts";

type Status = Delegate["status"];

export interface DelegateRow {
  sessionID: string;
  parentID: string;
  via: string;
  agent: string;
  task: string;
  status: Status;
  phase: string;
  startedAt: number;
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
    startedAt: delegate.startedAt,
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
    const newest = b.startedAt - a.startedAt;
    if (newest !== 0) return newest;
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

// --- association gap (degradation, AC11) -----------------------------------

export interface SessionLike {
  id?: string;
  sessionID?: string;
  parentID?: string | null;
  title?: string | null;
  status?: string;
}

/** A session is a child when it has a parent or the delegation title marker. */
export function isChildSession(session: SessionLike): boolean {
  if (!session) return false;
  if (session.parentID) return true;
  return Boolean(parseDelegationTitle(session.title ?? ""));
}

/**
 * Running children with no delegate row. The orchestrator/root is excluded:
 * a busy owner session is normal, not a visibility gap (review M2).
 */
export function associationGap(sessions: SessionLike[], rows: DelegateRow[]) {
  const children = (sessions ?? []).filter(isChildSession);
  const childIDs = new Set(children.map((s) => s.id ?? s.sessionID));
  const runningChildren = children.filter((s) =>
    s.status === "running" || s.status === "busy" || s.status === undefined).length;
  const associatedActive = (rows ?? []).filter(
    (r) => childIDs.has(r.sessionID) && !r.terminal && r.status !== "completed",
  ).length;
  return {
    runningChildren,
    associatedActive,
    unassociated: Math.max(0, runningChildren - associatedActive),
  };
}

// --- fallback status snapshot (observer --status-file) ----------------------

export interface StatusSnapshot {
  agent: string;
  outcome: string;
  terminal: boolean;
  child: string | null;
  heartbeat: string | null;
  ts: string | null;
}

/** Parse an observer snapshot; null unless it carries a real outcome. */
export function readStatusSnapshot(text: string | null | undefined): StatusSnapshot | null {
  if (!text || !String(text).trim()) return null;
  let data: any;
  try {
    data = JSON.parse(String(text));
  } catch {
    return null;
  }
  if (!data || typeof data !== "object" || !data.outcome) return null;
  return {
    agent: String(data.agent ?? "?"),
    outcome: String(data.outcome),
    terminal: Boolean(data.terminal),
    child: data.child ?? null,
    heartbeat: data.heartbeat ?? null,
    ts: data.ts ?? null,
  };
}

/**
 * Control descriptors. `enabled` is decision logic (tested); `run` performs
 * the exact typed call and is only invoked from the TUI keymap/commands.
 *
 * Only a *terminal* outcome disables controls. A clock-classified `failed`
 * (dead but no terminal event) and `waiting` remain actionable: the owner can
 * interrupt or steer instead of being told to wait for nothing.
 */
export function createControls(
  row: Pick<DelegateRow, "sessionID" | "status" | "terminal">,
  { client, ui }: { client?: any; ui?: any } = {},
) {
  const terminal = Boolean(row.terminal);
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
      enabled: !terminal,
      reason: terminal ? "delegate is terminal" : undefined,
      run: async () => {
        if (terminal) return { ok: false, reason: "terminal" };
        if (!client?.session?.interrupt) return { ok: false, reason: "no-client" };
        const result = await client.session.interrupt({ sessionID: row.sessionID });
        return {
          ok: true,
          call: "session.interrupt",
          interrupted: result?.interrupted ?? null,
        };
      },
    },
  ];
}

/**
 * Visible degradation (AC11). Every condition names the fallback; a healthy
 * observer returns null and the TUI shows no banner. Server-side failures
 * arrive through the shared health record (`serverHealth`), not only logs.
 */
export function degradationBanner({
  pluginLoaded = true,
  pluginState = "active",
  connection = "connected",
  disabled = false,
  serverHealth = null,
  runningChildren = 0,
  associatedActive = 0,
}: {
  pluginLoaded?: boolean;
  pluginState?: string;
  connection?: string;
  disabled?: boolean;
  serverHealth?: string | null;
  runningChildren?: number;
  associatedActive?: number;
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
  if (serverHealth) {
    return `delegation-observer server degraded: ${serverHealth} — milestones may be missing; the watchdog/observer fallback is authoritative.`;
  }
  if (connection === "disconnected") {
    return "delegation-observer event stream disconnected — showing last known state only; the watchdog/observer fallback is authoritative.";
  }
  if (connection === "unavailable") {
    return "delegation-observer is not receiving events — no live visibility; the watchdog/observer fallback is authoritative.";
  }
  if (runningChildren > associatedActive) {
    const missing = runningChildren - associatedActive;
    return `${runningChildren} running child session(s), ${missing} with no delegate association — no live visibility for them; the watchdog/observer fallback is authoritative.`;
  }
  return null;
}
