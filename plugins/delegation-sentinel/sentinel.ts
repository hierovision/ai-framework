/**
 * Delegation sentinel — pure logic (RM-069 AC11 fallback).
 *
 * The observer's own TUI part cannot draw a banner when it is absent or fails
 * to load. This companion is deliberately tiny and independent: it only checks
 * whether the observer is present/failed/disabled/disconnected (plugin record,
 * shared health record, TUI presence marker) and renders a visible fallback
 * line. It never claims live delegate detail.
 *
 * Run: node --test plugins/delegation-sentinel/sentinel.test.ts
 */

export const SENTINEL_ID = "delegation-sentinel";
export const OBSERVER_ID = "delegation-observer";
export const PRESENCE_STALE_MS = 45_000;

export interface SentinelInput {
  observerPresent?: boolean;
  observerState?: string;
  observerDisabled?: boolean;
  connection?: string | null;
  degradation?: string | null;
  presenceAgeMs?: number | null;
}

export function observerStatePath(directory?: string | null): string | null {
  if (!directory) return null;
  return `${String(directory).replace(/\/+$/, "")}/.scratch/delegation-observer/tui.json`;
}

export function healthRecordPath(
  directory?: string | null, env: Record<string, string | undefined> = process.env,
): string | null {
  const override = env?.DELEGATION_OBSERVER_HEALTH_FILE;
  if (override && override.trim()) return override.trim();
  if (!directory) return null;
  return `${String(directory).replace(/\/+$/, "")}/.scratch/delegation-observer/health.json`;
}

export function sentinelEnabled(env: Record<string, string | undefined> = process.env): boolean {
  const raw = env?.DELEGATION_SENTINEL_ENABLED;
  if (raw === undefined || raw === "") return true;
  return !["0", "false", "no", "off"].includes(String(raw).trim().toLowerCase());
}

export function sentinelBanner(input: SentinelInput = {}): string | null {
  const {
    observerPresent = true,
    observerState = "active",
    observerDisabled = false,
    connection = "connected",
    degradation = null,
    presenceAgeMs = 0,
  } = input;

  if (!observerPresent) {
    return "delegation-observer not loaded — no live delegate view; the watchdog/terminal wake remains authoritative.";
  }
  if (typeof observerState === "string" && observerState.startsWith("failed")) {
    return `delegation-observer failed: ${observerState.replace(/^failed:?\s*/, "")} — no live delegate view; the watchdog/terminal wake remains authoritative.`;
  }
  if (observerDisabled) {
    return "delegation-observer disabled by configuration — no live delegate view; the watchdog/terminal wake remains authoritative.";
  }
  if (connection === "disconnected" || connection === "unavailable") {
    return `delegation-observer ${connection} — live delegate view unavailable; the watchdog/terminal wake remains authoritative.`;
  }
  if (degradation) {
    return `delegation-observer degraded: ${degradation} — milestones may be missing; the watchdog/terminal wake remains authoritative.`;
  }
  if (presenceAgeMs === null || (typeof presenceAgeMs === "number" && presenceAgeMs > PRESENCE_STALE_MS)) {
    return "delegation-observer TUI is not running — status strip unavailable; the watchdog/terminal wake remains authoritative.";
  }
  return null;
}

/** Parse the observer TUI presence marker; null when absent/invalid. */
export function parsePresence(text: string | null | undefined): { pid: number; ts: number } | null {
  if (!text || !String(text).trim()) return null;
  try {
    const data = JSON.parse(String(text));
    if (!data || typeof data !== "object") return null;
    if (typeof data.ts !== "number") return null;
    return { pid: Number(data.pid) || 0, ts: data.ts };
  } catch {
    return null;
  }
}
