/**
 * Sentinel banner tests (RM-069 AC11 fallback). The sentinel must be honest:
 * no delegate detail, a visible line for every unavailable condition, and
 * nothing when the observer is healthy.
 */
import assert from "node:assert/strict";
import test from "node:test";

import {
  healthRecordPath,
  observerStatePath,
  parsePresence,
  sentinelBanner,
  sentinelEnabled,
} from "./sentinel.ts";

test("a healthy observer renders no sentinel line", () => {
  assert.equal(sentinelBanner({ presenceAgeMs: 1_000 }), null);
});

test("every unavailable condition renders a fallback naming the watchdog", () => {
  const cases = [
    [{ observerPresent: false }, /not loaded.*watchdog/],
    [{ observerState: "failed: boom" }, /failed.*boom.*watchdog/],
    [{ observerDisabled: true }, /disabled.*watchdog/],
    [{ connection: "disconnected" }, /disconnected.*watchdog/],
    [{ connection: "unavailable" }, /unavailable.*watchdog/],
    [{ degradation: "synthetic failed" }, /degraded.*synthetic failed.*watchdog/],
    [{ presenceAgeMs: null }, /TUI is not running.*watchdog/],
    [{ presenceAgeMs: 120_000 }, /TUI is not running.*watchdog/],
  ];
  for (const [input, pattern] of cases) {
    assert.match(sentinelBanner(input), pattern);
  }
});

test("the sentinel never claims delegate detail", () => {
  const line = sentinelBanner({ observerPresent: false });
  assert.doesNotMatch(line ?? "", /running|completed|delegate row|token/i);
});

test("paths and presence parsing are total", () => {
  assert.equal(observerStatePath("/repo/"),
    "/repo/.scratch/delegation-observer/tui.json");
  assert.equal(healthRecordPath("/repo/", {}),
    "/repo/.scratch/delegation-observer/health.json");
  assert.equal(healthRecordPath("/repo/", { DELEGATION_OBSERVER_HEALTH_FILE: "/tmp/h" }),
    "/tmp/h");
  assert.equal(observerStatePath(null), null);
  assert.deepEqual(parsePresence('{"pid":7,"ts":123}'), { pid: 7, ts: 123 });
  assert.equal(parsePresence("junk"), null);
  assert.equal(parsePresence(""), null);
});

test("the sentinel can be disabled explicitly", () => {
  assert.equal(sentinelEnabled({}), true);
  assert.equal(sentinelEnabled({ DELEGATION_SENTINEL_ENABLED: "0" }), false);
  assert.equal(sentinelEnabled({ DELEGATION_SENTINEL_ENABLED: "false" }), false);
  assert.equal(sentinelEnabled({ DELEGATION_SENTINEL_ENABLED: "1" }), true);
});
