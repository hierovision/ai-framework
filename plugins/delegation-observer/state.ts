/**
 * Pure delegation-observer state (RM-069).
 *
 * One reducer, shared by the server part (which emits synthetic parent
 * milestones) and the TUI part (which renders the status surface from the
 * same event stream). No I/O, no timers, no file reads: quiet/elapsed values
 * are computed from local observation times, never from heartbeat files.
 *
 * Supervision semantics are the documented watchdog ones (RM-022/RM-059):
 * busy is never stalled, an open assistant step gets the generation budget,
 * a call in flight gets the blocking budget, and everything else gets the
 * stall window. The numeric thresholds come from
 * `scripts/supervision_contract.json`; `state.test.ts` fails if they drift.
 *
 * Milestone policy (AC6 + AC7):
 * - routine (start, first-tool, resume): at most one per delegate per
 *   `milestoneMinIntervalSeconds`;
 * - attention (needs-input, stall, thrash): fire once per distinct condition,
 *   immediately — a waiting owner is never made to sit out a cooldown;
 * - terminal: exactly once per delegate, always.
 */

export interface ObserverConfig {
  enabled: boolean;
  stallSeconds: number;
  callSeconds: number;
  loopRepeats: number;
  generationSeconds: number;
  milestoneMinIntervalSeconds: number;
  milestoneDescription: string;
  titleMaxLength: number;
  /**
   * How old a *discovered* (bootstrap-only) session may be before it is
   * collapsed as stale. `session.list()` returns every child the store has
   * ever seen; without this window the strip lists months of finished work.
   */
  staleGraceSeconds: number;
}

/** Mirrors scripts/supervision_contract.json (asserted by state.test.ts). */
export const DEFAULTS: ObserverConfig = {
  enabled: true,
  stallSeconds: 240,
  callSeconds: 300,
  loopRepeats: 3,
  generationSeconds: 600,
  milestoneMinIntervalSeconds: 30,
  milestoneDescription: "delegation-observer milestone",
  titleMaxLength: 160,
  staleGraceSeconds: 600,
};

export const TITLE_PREFIX = "[delegate:";
const TITLE_RE = /^\[delegate:([A-Za-z0-9_-]+)\]\s+([A-Za-z0-9_.-]+):\s*(.*)$/;

/**
 * `unknown` is a first-class answer: a session we merely discovered is not
 * evidence of life (live defect, 2026-10-30). The next real event promotes it
 * to `running`.
 */
export type DelegateStatus = "running" | "waiting" | "warning" | "failed"
  | "completed" | "unknown";
export type Association = "parent" | "title";
/** `observed` = this process saw an event for it; `discovered` = listed only. */
export type Provenance = "observed" | "discovered";

export interface Delegate {
  sessionID: string;
  orchestratorID: string;
  via: Association;
  agent: string;
  task: string;
  status: DelegateStatus;
  phase: string;
  /** The session's created time when the store exposes it; never faked. */
  startedAt: number | null;
  /** The session's real last event; null when unavailable — never `now`. */
  lastActivityAt: number | null;
  provenance: Provenance;
  /**
   * Collapsed history, not current work: archived, terminal in the store but
   * not observed here, or discovered and past the grace window.
   */
  stale: boolean;
  /** `time.archived` is final: an archived session is never live again. */
  archived: boolean;
  busy: boolean;
  openStep: boolean;
  toolInFlight: boolean;
  tool: { name: string; target: string; id: string } | null;
  calls: Map<string, true>;
  loop: { key: string; count: number } | null;
  needsInput: { kind: "permission" | "form"; detail: string; since: number } | null;
  warning: string | null;
  tokens: { input: number; output: number };
  cost: number;
  terminal: { outcome: "completed" | "failed"; detail: string | null; at: number } | null;
  lastRoutineMilestoneAt: number | null;
  emitted: Set<string>;
}

export interface ObserverState {
  config: ObserverConfig;
  now: () => number;
  delegates: Map<string, Delegate>;
  /**
   * The host's live active map (session id -> busy right now). Filled by
   * `session.list()`/`session.status()` on every refresh; it is the only
   * evidence that makes a discovered-only session `running`.
   */
  active: Map<string, boolean>;
  connection: "connected" | "disconnected" | "unavailable";
  degradation: string | null;
  lastEventAt: number | null;
  pending: Milestone[];
}

export interface Milestone {
  sessionID: string;
  parentID: string;
  kind: "start" | "first-tool" | "needs-input" | "denied" | "stall" | "thrash"
    | "retry" | "resume" | "terminal";
  text: string;
  description: string;
  attention: boolean;
}

export interface Alert {
  sessionID: string;
  kind: Milestone["kind"];
  severity: "info" | "warning" | "error";
  title: string;
  message: string;
}

export interface ObserveResult {
  milestones: Milestone[];
  alerts: Alert[];
}

export interface SessionInfoLike {
  id?: string;
  sessionID?: string;
  parentID?: string | null;
  parent_id?: string | null;
  title?: string | null;
  agent?: string | null;
  /**
   * The store's terminal outcome. `SessionInfo.outcome` is the real 2.1.4
   * field (`"succeeded" | "failed" | "interrupted"`, client types
   * `promise/generated/types.d.ts`); the snake/camel aliases are accepted as
   * defence so a host that mirrors DB columns still works.
   */
  outcome?: string | null;
  idleOutcome?: string | null;
  idle_outcome?: string | null;
  /** `SessionInfo.time`: `created`, `updated`, `idle`, `viewed`, `archived`. */
  time?: {
    created?: number | null;
    updated?: number | null;
    archived?: number | null;
  } | null;
  /** Live status from the host's active map, when it is already known. */
  active?: boolean;
}

// --- title marker contract -------------------------------------------------

export function parseDelegationTitle(title: unknown) {
  if (typeof title !== "string") return null;
  const match = TITLE_RE.exec(title.trim());
  if (!match) return null;
  return { orchestratorID: match[1], agent: match[2], task: match[3].trim() };
}

export function sanitizeSessionID(value: unknown): string {
  const flat = String(value ?? "").replace(/[^A-Za-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return flat || "unknown";
}

export function sanitizeAgent(value: unknown): string {
  const flat = String(value ?? "").replace(/[^A-Za-z0-9_.-]+/g, "-")
    .replace(/^[-.]+|[-.]+$/g, "");
  return flat || "unknown";
}

export function delegationTitle({ orchestratorID, agent, task }: {
  orchestratorID: string;
  agent: string;
  task?: string;
}, config: ObserverConfig = DEFAULTS) {
  const flat = String(task ?? "").replace(/\s+/g, " ").trim();
  const head = `${TITLE_PREFIX}${sanitizeSessionID(orchestratorID)}] `
    + `${sanitizeAgent(agent)}: `;
  const room = Math.max(8, config.titleMaxLength - head.length);
  const body = flat.length > room ? flat.slice(0, room - 3).trimEnd() + "..." : flat;
  return (head + body).slice(0, config.titleMaxLength);
}

// --- state construction ----------------------------------------------------

/**
 * The TUI host does not forward a plugin entry's `options` to the TUI part on
 * 2.1.4 (probed 2026-10-29: the server saw `stallSeconds: 5`, the TUI did
 * not). The documented env source carries every TUI-relevant value end to end:
 *
 *   DELEGATION_OBSERVER_ENABLED                 1|0 / true|false (default: options)
 *   DELEGATION_OBSERVER_STALL_SECONDS           positive number
 *   DELEGATION_OBSERVER_STALE_GRACE_SECONDS     positive number (history window)
 *   DELEGATION_OBSERVER_HEALTH_FILE             path
 *   DELEGATION_OBSERVER_STATUS_FILE             path
 *
 * Precedence is per key: a value the host forwarded in `options` wins; the env
 * fills only what the host dropped. Numeric/boolean parsing is total (invalid
 * values are ignored).
 */
export function tuiConfig(ctx: any, env: Record<string, string | undefined> = process.env) {
  const options = ctx?.options?.delegationObserver ?? {};
  const merged: any = { ...options };
  const take = (key: string, raw: unknown, parse: (value: string) => unknown) => {
    if (options[key] !== undefined) return; // forwarded option wins
    if (raw === undefined || raw === "") return;
    const value = parse(String(raw));
    if (value !== undefined) merged[key] = value;
  };
  const positive = (raw: string) => {
    const value = Number(raw);
    return Number.isFinite(value) && value > 0 ? value : undefined;
  };
  take("stallSeconds", env?.DELEGATION_OBSERVER_STALL_SECONDS, positive);
  take("staleGraceSeconds", env?.DELEGATION_OBSERVER_STALE_GRACE_SECONDS, positive);
  take("enabled", env?.DELEGATION_OBSERVER_ENABLED, (raw) => {
    const value = raw.trim().toLowerCase();
    if (["0", "false", "no", "off"].includes(value)) return false;
    if (["1", "true", "yes", "on"].includes(value)) return true;
    return undefined;
  });
  for (const [key, envKey] of [
    ["healthFile", "DELEGATION_OBSERVER_HEALTH_FILE"],
    ["statusFile", "DELEGATION_OBSERVER_STATUS_FILE"],
  ] as const) {
    take(key, env?.[envKey], (raw) => (raw.trim() ? raw.trim() : undefined));
  }
  return merged;
}

export function createState(overrides: Partial<ObserverConfig> = {},
  now: () => number = Date.now): ObserverState {
  return {
    config: { ...DEFAULTS, ...overrides },
    now,
    delegates: new Map<string, Delegate>(),
    active: new Map<string, boolean>(),
    connection: "connected",
    degradation: null,
    lastEventAt: null,
    pending: [],
  };
}

/** The store's terminal outcome, normalized; null when absent or unknown. */
function terminalOutcome(info: SessionInfoLike): "completed" | "failed" | null {
  return normalizeOutcome(info.outcome ?? info.idleOutcome ?? info.idle_outcome ?? null);
}

export function normalizeOutcome(raw: unknown): "completed" | "failed" | null {
  if (!raw) return null;
  const value = String(raw).trim().toLowerCase();
  if (!value) return null;
  if (["succeeded", "success", "completed", "complete", "done"].includes(value)) {
    return "completed";
  }
  if (["failed", "error", "interrupted", "cancelled", "canceled", "aborted"].includes(value)) {
    return "failed";
  }
  return null;
}

function isActive(state: ObserverState, sessionID: string): boolean {
  return state.active.get(sessionID) === true;
}

/**
 * Staleness is a property of *evidence*, never of discovery. Order matters:
 * - `archived` is final, for observed and live rows too (the store removed it
 *   from the working set);
 * - a session terminal in the store but never observed here is history;
 * - an observed session is live state, so the clock classifier owns it;
 * - a live active-map entry is real liveness;
 * - otherwise the session is stale once its real last event (or, failing
 *   that, its created time) is older than the grace window. No timestamp at
 *   all means no evidence at all: stale immediately.
 */
export function isStale(state: ObserverState, d: Delegate,
  now: number = state.now()): boolean {
  if (d.archived) return true;
  if (d.terminal) return d.provenance !== "observed";
  if (d.provenance === "observed") return false;
  if (isActive(state, d.sessionID)) return false;
  const at = d.lastActivityAt ?? d.startedAt;
  if (at === null) return true;
  return now - at >= state.config.staleGraceSeconds * 1000;
}

/** Apply a store outcome as terminal, once. Never emits a milestone. */
function applyStoreOutcome(d: Delegate, outcome: "completed" | "failed",
  at: number | null) {
  if (d.terminal) return;
  d.terminal = { outcome, detail: "store outcome", at: at ?? 0 };
  d.status = outcome;
  d.phase = outcome;
  d.needsInput = null;
  d.toolInFlight = false;
  d.busy = false;
  // History must never emit a synthetic start or terminal milestone: the
  // orchestrator already saw this session end.
  d.emitted.add("start");
  d.emitted.add("terminal");
}

/**
 * Reconcile the live active map with a fresh snapshot.
 *
 * `null` means the host could not answer: nothing is live. Every id the
 * observer has ever recorded is then denied, so a discovered row cannot keep
 * claiming `running` from a last-known value after the liveness source is
 * gone. On an available snapshot, ids absent from it are denied too (a session
 * that left the map is no longer live), which is what makes a row demote
 * without waiting for a full list refresh. Observed rows are untouched: their
 * own event clock owns them.
 *
 * Returns true when the map membership changed (the caller re-renders).
 */
export function reconcileActive(
  state: ObserverState,
  snapshot: Iterable<string> | null,
): boolean {
  const live = snapshot === null ? new Set<string>() : new Set(snapshot);
  // Every id the observer knows about: the active-map keys, the new snapshot,
  // and every discovered delegate — a row can be promoted from
  // `associateSessionInfo({ active: true })` without an active-map entry, and
  // it must still be denied when the map drops it (review F21).
  const known = new Set<string>([...state.active.keys(), ...live]);
  for (const d of state.delegates.values()) {
    if (d.provenance === "discovered") known.add(d.sessionID);
  }
  let changed = false;
  for (const sessionID of known) {
    const next = live.has(sessionID);
    const before = state.active.get(sessionID);
    const delegate = state.delegates.get(sessionID);
    const wasRunning = delegate?.status === "running";
    markActive(state, sessionID, next);
    const demoted = wasRunning && delegate?.status !== "running";
    if (before !== next || demoted) changed = true;
  }
  return changed;
}

/**
 * Record the host's live active-map answer for a session. A discovered row
 * only becomes `running` here; an observed row keeps its event-driven state.
 * Archived and store-terminal rows are final: neither a map entry nor a
 * demotion may revive them.
 */
export function markActive(state: ObserverState, sessionID: string, active: boolean) {
  if (!sessionID) return null;
  const live = Boolean(active);
  state.active.set(sessionID, live);
  const d = state.delegates.get(sessionID);
  if (!d || d.archived || d.terminal || d.provenance === "observed") return d ?? null;
  if (live) {
    d.status = "running";
    d.phase = "active";
    d.stale = false;
  } else if (d.status === "running") {
    d.status = "unknown";
    d.phase = "no events observed";
    d.stale = isStale(state, d);
  }
  return d;
}

function associate(state: ObserverState, sessionID: string, info: SessionInfoLike,
  source: Provenance) {
  if (!sessionID) return null;
  const created = info.time?.created ?? null;
  const updated = info.time?.updated ?? null;
  const archived = (info.time?.archived ?? null) !== null;
  const outcome = terminalOutcome(info);
  const now = state.now();
  let delegate = state.delegates.get(sessionID);
  if (delegate) {
    // A later list refresh may carry evidence the first sight did not: absorb
    // it without ever reviving anything.
    if (!delegate.agent && info.agent) delegate.agent = info.agent;
    if (archived) delegate.archived = true;
    if (outcome) applyStoreOutcome(delegate, outcome, updated ?? created);
    delegate.stale = isStale(state, delegate, now);
    return delegate;
  }
  const parentID = info.parentID ?? info.parent_id ?? null;
  const marker = parseDelegationTitle(info.title ?? "");
  if (!parentID && !marker) return null;
  const knownActive = state.active.get(sessionID);
  const live = knownActive ?? Boolean(info.active);
  // Record the promotion so the map and the row agree: reconciliation denies
  // exactly the ids the map holds, so an `info.active` promotion must leave a
  // trace (review F21).
  if (knownActive === undefined && info.active !== undefined) {
    state.active.set(sessionID, Boolean(info.active));
  }
  delegate = {
    sessionID,
    orchestratorID: parentID || marker?.orchestratorID || "",
    via: parentID ? "parent" : "title",
    agent: info.agent || marker?.agent || "?",
    task: marker?.task || (info.title ?? "").trim() || "delegated task",
    status: "running",
    phase: "starting",
    startedAt: source === "observed" ? (created ?? now) : created,
    lastActivityAt: source === "observed" ? now : updated,
    provenance: source,
    stale: false,
    archived,
    busy: false,
    openStep: false,
    toolInFlight: false,
    tool: null,
    calls: new Map(),
    loop: null,
    needsInput: null,
    warning: null,
    tokens: { input: 0, output: 0 },
    cost: 0,
    terminal: null,
    lastRoutineMilestoneAt: null,
    emitted: new Set(),
  };
  if (source === "discovered") {
    // Discovery is not liveness. Rank the evidence we actually have: the
    // store's terminal outcome is final and outranks the live map (a finished
    // session is not running again just because the map says busy), and an
    // archived session is never live at all.
    if (outcome) {
      applyStoreOutcome(delegate, outcome, updated ?? created);
    } else if (archived) {
      delegate.status = "unknown";
      delegate.phase = "archived";
      delegate.emitted.add("start");
    } else if (live) {
      delegate.status = "running";
      delegate.phase = "active";
    } else {
      delegate.status = "unknown";
      delegate.phase = "no events observed";
      // Bootstrap never emits a start milestone, so no synthetic claim either.
      delegate.emitted.add("start");
    }
  }
  state.delegates.set(sessionID, delegate);
  delegate.stale = isStale(state, delegate, now);
  return delegate;
}

/**
 * Bootstrap association from `ctx.session.list()` / `data.session.list()`.
 *
 * Everything here is *discovery*: `session.list()` returns every child the
 * store has ever seen, so the row starts as `unknown` unless the live active
 * map or a store outcome says otherwise.
 */
export function associateSessionInfo(state: ObserverState, info: SessionInfoLike | null | undefined) {
  const sessionID = info?.id ?? info?.sessionID;
  if (!sessionID || !info) return null;
  return associate(state, sessionID, info, "discovered");
}

// --- milestone helpers -----------------------------------------------------

function label(d: Delegate) {
  return `${d.agent} ${d.sessionID}`;
}

function milestone(
  state: ObserverState,
  d: Delegate,
  kind: Milestone["kind"],
  key: string,
  text: string,
  { attention = false, terminal = false }: { attention?: boolean; terminal?: boolean } = {},
) {
  if (d.emitted.has(key)) return null;
  const now = state.now();
  if (!attention && !terminal) {
    if (d.lastRoutineMilestoneAt !== null
      && now - d.lastRoutineMilestoneAt < state.config.milestoneMinIntervalSeconds * 1000) {
      d.emitted.add(key); // coalesced away, never queued: no later chatter
      return null;
    }
    d.lastRoutineMilestoneAt = now;
  }
  d.emitted.add(key);
  return {
    sessionID: d.sessionID,
    parentID: d.orchestratorID,
    kind,
    text,
    description: state.config.milestoneDescription,
    attention,
  };
}

function alert(m: Milestone): Alert {
  const severity = m.kind === "terminal"
    ? "info"
    : (m.kind === "needs-input" || m.kind === "thrash" || m.kind === "stall")
      ? "warning"
      : "info";
  return {
    sessionID: m.sessionID,
    kind: m.kind,
    severity,
    title: `delegate ${m.kind}`,
    message: m.text,
  };
}

function touch(d: Delegate, now: number) {
  d.lastActivityAt = now;
  d.stale = false;
  // A clock-classified warning/failed row that shows real activity is alive
  // again; only a terminal outcome or an archive is sticky.
  if (d.status === "warning" || d.status === "failed" || d.status === "unknown") {
    d.status = "running";
  }
  d.warning = null;
  for (const key of [...d.emitted]) {
    if (key.startsWith("stall:")) d.emitted.delete(key);
  }
}

// --- tool application ------------------------------------------------------

function toolTarget(name: string, input: unknown) {
  const inp = (input && typeof input === "object" ? input : {}) as Record<string, any>;
  const value = inp.command ?? inp.path ?? inp.filePath ?? inp.pattern
    ?? inp.agent ?? inp.description ?? "";
  return String(value).split("\n")[0].slice(0, 80);
}

function applyTool(state: ObserverState, d: Delegate, name: string, target: string,
  id: string, status: string) {
  const now = state.now();
  touch(d, now);
  const running = status === "running" || status === "pending"
    || status === "streaming" || status === "called";
  // `session.tool.called` carries no tool name on 2.1.4; the name arrives with
  // `session.message.content.updated`. Until it does, show the target only and
  // do not label/count the call (avoids a "tool:" label and double counting).
  const named = Boolean(name) && name !== "tool" && name !== "?";
  d.phase = running
    ? `${named ? name : "tool"}${target ? `: ${target}` : ""}`
    : "thinking";
  d.toolInFlight = running;
  d.tool = running ? { name, target, id } : null;
  if (running) {
    // One call, one count. `session.message.content.updated` re-delivers the
    // same tool block (same id, same target) on every delta; counting those
    // would flag thrash for a single long-running call. The loop key is the
    // target (tool:target's discriminating half) so a late tool name cannot
    // re-key an already-counted call.
    const counted = Boolean(id) && d.calls.has(id);
    if (target && !counted && named) {
      if (id) {
        d.calls.set(id, true);
        if (d.calls.size > 64) {
          const oldest = d.calls.keys().next().value;
          if (oldest !== undefined) d.calls.delete(oldest);
        }
      }
      if (!d.loop || d.loop.key !== target) d.loop = { key: target, count: 0 };
      d.loop.count += 1;
      const label = `${name}: ${target}`;
      const first = milestone(state, d, "first-tool", "first-tool",
        `first tool: ${label}`);
      if (first) state.pending.push(first);
      if (d.loop.count >= state.config.loopRepeats) {
        const thrash = milestone(state, d, "thrash", `thrash:${target}`,
          `thrash: ${label} x${d.loop.count}`, { attention: true });
        if (thrash) {
          d.warning = `thrash: ${name}: ${target} x${d.loop.count}`;
          if (d.status === "running") d.status = "warning";
          state.pending.push(thrash);
        }
      }
    }
  }
  return now;
}

// --- reducer ---------------------------------------------------------------

export function observe(state: ObserverState, event: any): ObserveResult {
  state.pending = state.pending ?? [];
  const out: ObserveResult = { milestones: [], alerts: [] };
  const type = event?.type ?? "";
  const data = event?.data ?? event?.properties ?? {};
  // FormInfo1 nests the session id (`data.form.sessionID`); every other
  // event used here carries it top-level (client types FormCreated/FormInfo1).
  const sessionID = data?.sessionID ?? data?.session?.id
    ?? data?.info?.sessionID ?? data?.form?.sessionID;
  const now = state.now();
  state.lastEventAt = now;

  // Archive lifecycle is resolved BEFORE any association or milestone: an
  // archived row never emits, and a replayed `session.created` for it must not
  // produce a synthetic start (review F11).
  let d = sessionID ? state.delegates.get(sessionID) ?? null : null;
  if (d && type === "session.archived") {
    // Archive is final for every row, observed, live or terminal: the store
    // removed the session from the working set, so it is history from here on.
    d.archived = true;
    d.needsInput = null;
    d.toolInFlight = false;
    d.busy = false;
    d.stale = true;
    state.pending.length = 0;
    return out;
  }
  if (d && type === "session.unarchived") {
    d.archived = false;
    d.stale = isStale(state, d, now);
    state.pending.length = 0;
    return out;
  }
  if (d?.archived) {
    // An archived session never becomes live again and never emits.
    state.pending.length = 0;
    return out;
  }

  if (type === "session.created") {
    const created = associate(state, sessionID, {
      parentID: data.parentID,
      title: data.title,
      agent: data.agent,
    }, "observed");
    if (created && !created.archived) {
      const m = milestone(state, created, "start", "start",
        `${label(created)} started: ${created.task}`);
      if (m) out.milestones.push(m);
    }
  } else if (type === "session.renamed") {
    const renamed = associate(state, sessionID, {
      parentID: null, title: data.title, agent: data.agent,
    }, "observed");
    if (renamed && !renamed.archived && renamed.via === "title" && data.title) {
      const marker = parseDelegationTitle(data.title);
      if (marker?.task) renamed.task = marker.task;
    }
  }

  d = sessionID ? state.delegates.get(sessionID) ?? null : null;
  if (!d || d.terminal) {
    state.pending.length = 0;
    return out;
  }
  if (d.archived) {
    state.pending.length = 0;
    return out;
  }

  // Any event is the strongest evidence there is: a discovered row is live
  // from here on and the clock classifier (stall/thrash/needs-input) owns it.
  // `touch` is what makes that true: it refreshes the observation clock to
  // NOW, so a 19 h-old store timestamp can never be read as quiet time and
  // the next tick cannot emit a false stall/dead milestone (fix F2).
  if (d.provenance === "discovered") {
    d.provenance = "observed";
    touch(d, now);
    if (d.status === "unknown") {
      d.status = "running";
      d.phase = "active";
    }
  }

  switch (type) {
    case "permission.asked": {
      const detail = `${data.action ?? "permission"} ${(data.resources ?? []).join(", ")}`.trim();
      d.needsInput = { kind: "permission", detail, since: now };
      d.status = "waiting";
      d.phase = "waiting for permission";
      const m = milestone(state, d, "needs-input", `needs:permission:${detail}`,
        `${label(d)} needs input: ${detail}`, { attention: true });
      if (m) out.milestones.push(m);
      break;
    }
    case "form.created": {
      const detail = data.form?.title ?? data.title ?? "form";
      d.needsInput = { kind: "form", detail, since: now };
      d.status = "waiting";
      d.phase = "waiting for form";
      const m = milestone(state, d, "needs-input", `needs:form:${detail}`,
        `${label(d)} needs input: form ${detail}`, { attention: true });
      if (m) out.milestones.push(m);
      break;
    }
    case "permission.replied":
    case "form.replied":
    case "form.cancelled": {
      if (!d.needsInput) break;
      const pending = d.needsInput;
      d.needsInput = null;
      if (type === "permission.replied" && data.reply === "reject") {
        // A denial is an intervention, not progress (AC8): warn, never
        // claim the child resumed. The next real activity clears it.
        touch(d, now);
        d.warning = `permission denied: ${pending.detail}`;
        d.status = "warning";
        d.phase = "permission denied";
        const m = milestone(state, d, "denied", `denied:${pending.detail}`,
          `${label(d)} permission DENIED: ${pending.detail}`, { attention: true });
        if (m) out.milestones.push(m);
        break;
      }
      d.status = "running";
      d.phase = "resumed";
      touch(d, now);
      const m = milestone(state, d, "resume", `resume:${now}`,
        `${label(d)} resumed after input`);
      if (m) out.milestones.push(m);
      break;
    }
    case "session.status": {
      const status = data.status && typeof data.status === "object"
        ? data.status : data;
      const kind = status.type ?? data.type;
      d.busy = kind === "busy";
      if (kind === "retry") {
        d.warning = `retry${status.attempt ? ` attempt ${status.attempt}` : ""}`;
        d.status = "warning";
        d.phase = d.warning;
        const key = `retry:${status.attempt ?? "?"}`;
        const m = milestone(state, d, "retry", key,
          `${label(d)} ${d.warning}`, { attention: true });
        if (m) out.milestones.push(m);
      } else if (kind === "busy") {
        d.status = d.needsInput ? "waiting" : "running";
        if (!d.needsInput) d.phase = "generating";
        touch(d, now);
      } else {
        // idle/unknown is still an observed transition: refresh the clock so
        // a completed turn is not classified dead by the next tick.
        touch(d, now);
        if (d.status !== "waiting") d.status = "running";
        d.phase = "idle";
      }
      break;
    }
    case "session.step.started":
      d.openStep = true;
      d.phase = "generating";
      touch(d, now);
      break;
    case "session.step.ended": {
      // A long generation ending normally is progress: refresh the clock,
      // close the step, and take the vendor's totals. Without the refresh the
      // next tick would classify the completed turn dead (AC8).
      touch(d, now);
      d.openStep = false;
      d.phase = "thinking";
      if (typeof data.cost === "number") d.cost = data.cost;
      const t = data.tokens ?? {};
      if (typeof t.input === "number") d.tokens.input = t.input;
      if (typeof t.output === "number") d.tokens.output = t.output;
      break;
    }
    case "session.step.failed": {
      touch(d, now);
      d.openStep = false;
      d.phase = "step failed";
      d.warning = `step failed: ${data.error?.message ?? "unknown"}`;
      d.status = "warning";
      break;
    }
    case "session.tool.called": {
      const name = data.name ?? data.tool ?? data.metadata?.tool ?? "tool";
      applyTool(state, d, name, toolTarget(name, data.input), String(data.id ?? ""),
        "running");
      break;
    }
    case "session.tool.success":
    case "session.tool.failed": {
      const name = data.name ?? data.tool ?? d.tool?.name ?? "tool";
      applyTool(state, d, name, d.tool?.target ?? "", String(data.id ?? ""),
        type.endsWith("success") ? "completed" : "error");
      break;
    }
    case "session.message.content.updated": {
      for (const block of data.content ?? []) {
        if (!block || block.type !== "tool") continue;
        const st = block.state ?? {};
        applyTool(state, d, block.name ?? "tool", toolTarget(block.name, st.input),
          String(block.id ?? ""), st.status ?? "unknown");
      }
      break;
    }
    case "session.usage.updated": {
      if (typeof data.cost === "number") d.cost = data.cost;
      const t = data.tokens ?? {};
      if (typeof t.input === "number") d.tokens.input = t.input;
      if (typeof t.output === "number") d.tokens.output = t.output;
      break;
    }
    case "session.execution.succeeded":
    case "session.execution.failed":
    case "session.execution.interrupted": {
      const outcome = type.endsWith("succeeded") ? "completed" : "failed";
      const detail = type.endsWith("succeeded") ? null
        : (type.endsWith("interrupted") ? "interrupted" : (data.error?.message ?? "failed"));
      d.terminal = { outcome, detail, at: now };
      d.status = outcome;
      d.phase = outcome;
      d.needsInput = null;
      d.toolInFlight = false;
      const m = milestone(state, d, "terminal", "terminal",
        `${label(d)} ${outcome}${detail ? `: ${detail}` : ""}`, { terminal: true });
      if (m) out.milestones.push(m);
      break;
    }
    default:
      break;
  }

  out.milestones.push(...state.pending);
  state.pending.length = 0;
  out.alerts.push(...out.milestones.map(alert));
  return out;
}

// --- clock-driven classification (no polling of any file) ------------------

export function tick(state: ObserverState, now: number = state.now()): ObserveResult {
  const out: ObserveResult = { milestones: [], alerts: [] };
  for (const d of state.delegates.values()) {
    // Staleness is re-evaluated on the clock: a row discovered five minutes
    // ago is not stale yet, and crosses the grace window without any event.
    d.stale = isStale(state, d, now);
    if (d.terminal || d.stale) continue;
    // Discovery is not liveness (live defect, 2026-10-30): a bootstrapped row
    // has no observation clock of its own, so it is never classified and never
    // emits a synthetic stall. The first real event promotes it.
    if (d.provenance === "discovered") continue;
    if (d.lastActivityAt === null) continue;
    if (d.needsInput) {
      if (d.status !== "waiting") d.status = "waiting";
      continue;
    }
    if (d.busy) continue;
    const threshold = d.openStep
      ? state.config.generationSeconds
      : d.toolInFlight ? state.config.callSeconds : state.config.stallSeconds;
    const quiet = (now - d.lastActivityAt) / 1000;
    if (quiet <= threshold) continue;
    const dead = quiet > threshold * 2;
    const what = d.openStep ? "open generation"
      : d.toolInFlight ? `call ${d.tool?.name ?? "tool"} in flight` : "no activity";
    d.warning = `${dead ? "dead" : "quiet"} ${Math.round(quiet)}s (${what})`;
    d.status = dead ? "failed" : "warning";
    const m = milestone(state, d, "stall", `stall:${d.tool?.id ?? d.phase}`,
      `${label(d)} ${dead ? "dead" : "stalled"}: ${d.warning}`, { attention: true });
    if (m) out.milestones.push(m);
  }
  out.alerts.push(...out.milestones.map(alert));
  return out;
}

function setDegradation(state: ObserverState, reason: string) {
  const text = String(reason ?? "degraded");
  state.degradation = state.degradation ? `${state.degradation}; ${text}` : text;
}

export function degrade(state: ObserverState, reason: string) {
  state.connection = "unavailable";
  setDegradation(state, reason);
}

export function disconnect(state: ObserverState, reason = "event stream disconnected") {
  state.connection = "disconnected";
  setDegradation(state, reason);
}

export function reconnect(state: ObserverState) {
  state.connection = "connected";
  state.degradation = null;
}

// --- shared health record (server -> TUI degradation channel) --------------

/**
 * The server part cannot push to the TUI: they are separate processes. It
 * writes this small health record instead, and the TUI reads it only when it
 * needs the degradation channel — never as the progress source (AC3).
 */
export function healthPath(directory: string | null | undefined): string | null {
  if (!directory) return null;
  const base = String(directory).replace(/\/+$/, "");
  return `${base}/.scratch/delegation-observer/health.json`;
}

export function parseHealthRecord(text: string | null | undefined) {
  if (!text || !String(text).trim()) return null;
  try {
    const data = JSON.parse(String(text));
    if (!data || typeof data !== "object") return null;
    return {
      connection: typeof data.connection === "string" ? data.connection : "unavailable",
      degradation: typeof data.degradation === "string" && data.degradation
        ? data.degradation : null,
      updated: typeof data.updated === "number" ? data.updated : null,
    };
  } catch {
    return null;
  }
}
