/**
 * Model tests for the delegation-observer TUI (RM-069 AC4, AC9, AC11).
 *
 * These import `model.ts` — the real initialization path `createDefinition`
 * calls — against a mock host. They exist because an earlier review found
 * `createTuiModel` throwing `ReferenceError` at construction (a memo reading a
 * `const` declared below it): a view-only test suite could not see it.
 *
 * Every assertion here is load-bearing: no `assert.ok(x)` on an object or an
 * array length, which is true for any value (review F14).
 *
 * Run: node --test model.test.ts
 */
import assert from "node:assert/strict";
import { existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { createDefinition, createTuiModel } from "./model.ts";

const OLD = Date.now() - 20 * 3_600_000;

function mockHost({
  sessions = [],
  status = () => "idle",
  list = undefined,
  plugin = "active",
  options = {},
}: {
  sessions?: any[];
  status?: (id: string) => unknown;
  list?: () => unknown;
  plugin?: "active" | "failed" | "missing";
  options?: Record<string, any>;
} = {}) {
  const calls: {
    focus: string[];
    toasts: any[];
    dialogs: any[];
    commands: any[];
    slots: any[];
    listeners: Array<(event: any) => void>;
    listenersDisposed: number;
    slotsDisposed: number;
  } = {
    focus: [], toasts: [], dialogs: [], commands: [], slots: [],
    listeners: [], listenersDisposed: 0, slotsDisposed: 0,
  };
  const ctx = {
    options,
    data: {
      listen: (handler: (event: any) => void) => {
        calls.listeners.push(handler);
        return () => { calls.listenersDisposed += 1; };
      },
      session: {
        list: list ?? (() => sessions),
        status,
      },
    },
    ui: {
      toast: { show: (input: any) => calls.toasts.push(input) },
      dialog: {
        select: async (input: any) => {
          calls.dialogs.push(input);
          return input.options?.[0]?.value;
        },
        prompt: async () => undefined,
      },
      tabs: { focus: (id: string) => { calls.focus.push(id); return true; } },
      panel: { open: () => {} },
      slot: (input: any) => {
        calls.slots.push(input);
        return () => { calls.slotsDisposed += 1; };
      },
    },
    attention: { notify: async () => {} },
    keymap: {
      layer: (fn: () => any) => {
        calls.commands.push(...(fn().commands ?? []));
        return () => {};
      },
    },
    client: {
      plugin: {
        list: async () => plugin === "missing"
          ? []
          : [{ id: "delegation-observer", state: { status: plugin }, features: { tui: true } }],
      },
      session: { prompt: async () => ({}), interrupt: async () => ({ interrupted: true }) },
    },
  };
  return { ctx, calls };
}

/** Run a command from the registered layer by id. */
function command(calls: { commands: any[] }, id: string) {
  const entry = calls.commands.find((c) => c.id === id);
  assert.ok(entry, `command ${id} is registered`);
  return entry;
}

const child = (id = "ses_live", parentID = "ses_parent") => ({
  id, parentID, title: `${id} task`, agent: "implementer",
  time: { created: OLD, updated: OLD },
});

test("the model constructs over a healthy host and bootstraps liveness", () => {
  // Regression for the F9 blocker: createTuiModel must not throw. The banner
  // memo reads liveSessionRows(), which used to be declared below it.
  const { ctx, calls } = mockHost({
    sessions: [child("ses_live"), child("ses_old")],
    status: (id) => (id === "ses_live" ? "running" : "idle"),
  });
  const model = createTuiModel(ctx);
  try {
    assert.deepEqual(
      calls.commands.map((c) => c.id),
      ["delegation.focus", "delegation.steer", "delegation.interrupt",
        "delegation.history", "delegation.panel", "delegation.status"],
      "the documented command layer is registered",
    );
    const rows = model.liveRows();
    const live = rows.find((r) => r.sessionID === "ses_live");
    const old = rows.find((r) => r.sessionID === "ses_old");
    assert.equal(live?.status, "running", "the live map is read before association");
    assert.equal(live?.stale, false);
    assert.equal(old?.status, "unknown");
    assert.equal(old?.stale, true);
    // the view's memo layer is evaluated here (solid memos are eager)
    assert.equal(model.banner(), null, "healthy host: the rendered banner is empty");
    assert.equal(model.state.delegates.size, 2);
    assert.equal(typeof model.rows, "function");
    assert.equal(typeof model.banner, "function");
  } finally {
    model.dispose();
  }
});

test("a throwing status map is a banner, not a crash", () => {
  const { ctx } = mockHost({
    sessions: [child("ses_live")],
    status: () => { throw new Error("no status"); },
  });
  const model = createTuiModel(ctx);
  try {
    assert.match(model.banner() ?? "", /cannot read the live session status map/);
    assert.equal(model.liveRows()[0]?.status, "unknown", "no liveness claim without the map");
  } finally {
    model.dispose();
  }
});

test("a null, undefined or non-array session list is normalized", () => {
  for (const listed of [null, undefined, {}, 42, "nope"]) {
    const { ctx } = mockHost({ list: () => listed });
    let model: ReturnType<typeof createTuiModel> | null = null;
    assert.doesNotThrow(() => { model = createTuiModel(ctx); }, `list=${String(listed)}`);
    try {
      assert.match(model!.banner() ?? "", /cannot read the live session status map/);
      assert.deepEqual(model!.liveRows(), []);
    } finally {
      model!.dispose();
    }
  }
});

test("malformed array elements are dropped, not dereferenced", () => {
  // [null] used to reach liveSessionRows and throw
  // "Cannot read properties of null (reading 'id')" at construction (F15).
  for (const listed of [
    [null],
    [undefined],
    [null, child("ses_live"), undefined],
    [child("ses_live"), null, 7, "junk", {}],
  ]) {
    const hasChild = listed.some(
      (element: any) => element && typeof element === "object" && element.id === "ses_live",
    );
    const { ctx } = mockHost({
      list: () => listed,
      status: (id) => (id === "ses_live" ? "running" : "idle"),
    });
    let model: ReturnType<typeof createTuiModel> | null = null;
    assert.doesNotThrow(
      () => { model = createTuiModel(ctx); },
      `elements=${JSON.stringify(listed)}`,
    );
    try {
      // the container is an array, so the map is available: the valid child
      // is discovered from the live map, the junk is ignored.
      assert.equal(model!.banner(), null, "a partial array is not a degradation");
      const rows = model!.liveRows();
      assert.deepEqual(rows.map((r) => r.sessionID), hasChild ? ["ses_live"] : []);
      if (hasChild) assert.equal(rows[0].status, "running");
    } finally {
      model!.dispose();
    }
  }
});

test("a throwing session list is a banner, not a crash", () => {
  const { ctx } = mockHost({ list: () => { throw new Error("list closed"); } });
  const model = createTuiModel(ctx);
  try {
    assert.match(model.banner() ?? "", /cannot read the live session status map/);
    assert.deepEqual(model.liveRows(), []);
  } finally {
    model.dispose();
  }
});

test("the event stream drives rows and attention toasts through the listener", () => {
  const { ctx, calls } = mockHost({ sessions: [] });
  const model = createTuiModel(ctx);
  try {
    assert.equal(calls.listeners.length, 1, "ctx.data.listen is wired");
    calls.listeners[0]({
      details: {
        type: "session.created",
        data: { sessionID: "ses_new", parentID: "ses_parent", title: "new work", agent: "planner" },
      },
    });
    const row = model.liveRows().find((r) => r.sessionID === "ses_new");
    assert.equal(row?.status, "running");
    assert.equal(row?.agent, "planner");
    assert.equal(calls.toasts.length, 0, "a routine start is a row, not a toast");

    // attention: needs-input is surfaced immediately, not just a row state
    calls.listeners[0]({
      details: {
        type: "permission.asked",
        data: { sessionID: "ses_new", action: "external_directory", resources: ["/etc/**"] },
      },
    });
    const waiting = model.liveRows().find((r) => r.sessionID === "ses_new");
    assert.equal(waiting?.status, "waiting");
    assert.match(waiting?.needsInput ?? "", /external_directory/);
    assert.equal(calls.toasts.at(-1)?.title, "delegate needs-input");
    assert.match(calls.toasts.at(-1)?.message ?? "", /ses_new/);
    assert.match(calls.toasts.at(-1)?.message ?? "", /external_directory/);
  } finally {
    model.dispose();
    assert.equal(calls.listenersDisposed, 1, "dispose unsubscribes the listener");
  }
});

test("the live picker excludes collapsed history; history is its own path", async () => {
  const { ctx, calls } = mockHost({
    sessions: [child("ses_live"), child("ses_old")],
    status: (id) => (id === "ses_live" ? "running" : "idle"),
  });
  const model = createTuiModel(ctx);
  try {
    // The only live row: focus goes straight to it, no dialog.
    await command(calls, "delegation.focus").run();
    assert.deepEqual(calls.focus, ["ses_live"]);

    // Collapsed history is reachable, but only through the history command.
    await command(calls, "delegation.history").run();
    assert.deepEqual(calls.focus, ["ses_live", "ses_old"]);
    assert.equal(calls.dialogs.length, 0);

    // Steer on a stale-only inbox: the live picker reports empty and never
    // offers the collapsed row.
    const staleOnly = mockHost({
      sessions: [child("ses_old")],
      status: () => "idle",
    });
    const idle = createTuiModel(staleOnly.ctx);
    try {
      assert.equal(idle.liveRows()[0]?.stale, true, "the only row is history");
      assert.equal(idle.liveRows()[0]?.status, "unknown");
      await command(staleOnly.calls, "delegation.focus").run();
      assert.deepEqual(staleOnly.calls.focus, []);
      assert.match(staleOnly.calls.toasts.at(-1)?.message ?? "", /no delegates observed/);
      await command(staleOnly.calls, "delegation.history").run();
      assert.deepEqual(staleOnly.calls.focus, ["ses_old"]);
      assert.equal(staleOnly.calls.dialogs.length, 0);
    } finally {
      idle.dispose();
    }
  } finally {
    model.dispose();
  }
});

test("the history path reports an empty history instead of opening a dialog", async () => {
  const { ctx, calls } = mockHost({
    sessions: [child("ses_live")],
    status: () => "running",
  });
  const model = createTuiModel(ctx);
  try {
    await command(calls, "delegation.history").run();
    assert.deepEqual(calls.focus, []);
    assert.equal(calls.dialogs.length, 0);
    assert.match(calls.toasts.at(-1)?.message ?? "", /no delegate history/);
  } finally {
    model.dispose();
  }
});

test("the shared health record reaches the banner and the status command", async (t) => {
  const dir = mkdtempSync(join(tmpdir(), "rm069-health-"));
  const file = join(dir, "health.json");
  try {
    // healthy record: no banner
    writeFileSync(file, JSON.stringify({ connection: "connected", degradation: null, updated: 1 }));
    const healthy = mockHost({ sessions: [], options: { delegationObserver: { healthFile: file } } });
    const ok = createTuiModel(healthy.ctx);
    try {
      assert.equal(ok.banner(), null, "a healthy record leaves the banner empty");
    } finally {
      ok.dispose();
    }

    // degraded record, read at construction: the banner carries the reason
    writeFileSync(file, JSON.stringify({
      connection: "unavailable",
      degradation: "synthetic failed: nope",
      updated: 2,
    }));
    const degraded = mockHost({ sessions: [], options: { delegationObserver: { healthFile: file } } });
    const bad = createTuiModel(degraded.ctx);
    try {
      assert.match(bad.banner() ?? "", /server degraded: synthetic failed: nope/);
      await command(degraded.calls, "delegation.status").run();
      const toast = degraded.calls.toasts.at(-1);
      assert.equal(toast?.title, "delegation degraded");
      assert.match(toast?.message ?? "", /synthetic failed: nope/);
    } finally {
      bad.dispose();
    }

    // the read is throttled to 1 s: a record rewritten after construction is
    // picked up once the throttle window passes (fake clock)
    t.mock.timers.enable({ apis: ["Date", "setInterval"], now: OLD });
    writeFileSync(file, JSON.stringify({ connection: "connected", degradation: null, updated: 3 }));
    const live = mockHost({ sessions: [], options: { delegationObserver: { healthFile: file } } });
    const model = createTuiModel(live.ctx);
    try {
      assert.equal(model.banner(), null);
      writeFileSync(file, JSON.stringify({
        connection: "disconnected", degradation: "event stream ended", updated: 4,
      }));
      t.mock.timers.tick(1_100); // past the 1 s throttle
      await command(live.calls, "delegation.status").run();
      assert.match(live.calls.toasts.at(-1)?.message ?? "", /event stream ended/);
    } finally {
      model.dispose();
      t.mock.timers.reset();
    }
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("one interval tick refreshes the live map and the rows", (t) => {
  t.mock.timers.enable({ apis: ["Date", "setInterval"], now: OLD + 20 * 3_600_000 });
  let live = false;
  const { ctx } = mockHost({
    sessions: [child("ses_live")],
    status: () => (live ? "running" : "idle"),
  });
  const model = createTuiModel(ctx);
  try {
    assert.equal(model.liveRows()[0]?.status, "unknown", "idle map: no liveness claim");
    assert.equal(model.liveRows()[0]?.stale, true, "19 h old and unproven: history");

    live = true;
    t.mock.timers.tick(5_000); // TICK_MS: refreshActive + tick + bump

    const row = model.liveRows()[0];
    assert.equal(row.status, "running", "the timer refreshed the live map");
    assert.equal(row.stale, false);
    assert.equal(row.phase, "active");
  } finally {
    model.dispose();
    t.mock.timers.reset();
  }
});

test("createDefinition registers the documented slots and disposes them", async () => {
  const { ctx, calls } = mockHost({ sessions: [child("ses_live")], status: () => "running" });
  const views = {
    strip: () => "strip-view",
    footer: () => "footer-view",
    panel: (_model: any, input: any) => `panel:${input?.name ?? "-"}`,
  };
  const definition = createDefinition({ define: (d: any) => d }, views);
  assert.equal(definition.id, "delegation-observer");

  const dispose = await definition.setup(ctx);
  assert.deepEqual(calls.slots.map((s) => s.append),
    ["sidebar.content", "home.footer.status", "session.panel"],
    "the three documented slots are registered");
  assert.equal(calls.slots[0].render(), "strip-view");
  assert.equal(calls.slots[1].render(), "footer-view");
  assert.equal(calls.slots[2].render({ name: "delegates" }), "panel:delegates");
  assert.equal(calls.slots[2].render({ name: "other" }), "panel:other");

  dispose();
  assert.equal(calls.listenersDisposed, 1, "the event listener is released");
  assert.equal(calls.slotsDisposed, 3, "every slot disposer ran");
});

test("a disabled observer still registers and says so once", async () => {
  const { ctx, calls } = mockHost({
    sessions: [],
    options: { delegationObserver: { enabled: false } },
  });
  const definition = createDefinition({ define: (d: any) => d }, {
    strip: () => "s", footer: () => "f", panel: () => "p",
  });
  const dispose = await definition.setup(ctx);
  try {
    assert.equal(calls.slots.length, 3, "the strip still renders the disabled banner");
    assert.match(calls.toasts.at(-1)?.message ?? "", /disabled/);
    assert.equal(calls.toasts.at(-1)?.variant, "warning");
  } finally {
    dispose();
  }
});

test("presence is written at construction and removed on dispose", () => {
  const dir = mkdtempSync(join(tmpdir(), "rm069-model-"));
  try {
    const { ctx } = mockHost({ sessions: [] });
    ctx.location = { directory: dir } as any;
    const model = createTuiModel(ctx);
    const marker = join(dir, ".scratch", "delegation-observer", "tui.json");
    assert.equal(existsSync(marker), true, "the sentinel's presence marker exists");
    model.dispose();
    assert.equal(existsSync(marker), false, "dispose removes it");
    assert.equal(model.state.connection, "disconnected");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
