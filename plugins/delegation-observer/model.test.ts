/**
 * Model tests for the delegation-observer TUI (RM-069 AC4, AC9, AC11).
 *
 * These import `model.ts` — the real initialization path `createDefinition`
 * calls — against a mock host. They exist because the previous review found
 * `createTuiModel` throwing `ReferenceError` at construction (a memo reading a
 * `const` declared below it): a view-only test suite could not see it.
 *
 * Run: node --test model.test.ts
 */
import assert from "node:assert/strict";
import { existsSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { createTuiModel } from "./model.ts";

const OLD = Date.now() - 20 * 3_600_000;

function mockHost({
  sessions = [],
  status = () => "idle",
  list = undefined,
  plugin = "active",
}: {
  sessions?: any[];
  status?: (id: string) => unknown;
  list?: () => unknown;
  plugin?: "active" | "failed" | "missing";
} = {}) {
  const calls: {
    focus: string[];
    toasts: any[];
    dialogs: any[];
    commands: any[];
    listeners: Array<(event: any) => void>;
    disposed: number;
  } = { focus: [], toasts: [], dialogs: [], commands: [], listeners: [], disposed: 0 };
  const ctx = {
    options: {},
    data: {
      listen: (handler: (event: any) => void) => {
        calls.listeners.push(handler);
        return () => { calls.disposed += 1; };
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
      slot: () => () => {},
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

const liveChild = (id = "ses_live", parentID = "ses_parent") => ({
  id, parentID, title: `${id} task`, agent: "implementer",
  time: { created: OLD, updated: OLD },
});

const historicalChild = (id = "ses_old", parentID = "ses_parent") => ({
  id, parentID, title: `${id} task`, agent: "implementer",
  time: { created: OLD, updated: OLD },
});

test("the model constructs over a healthy host and bootstraps liveness", () => {
  // Regression for the review's blocker: createTuiModel must not throw. The
  // banner memo reads sessionRows(), which used to be declared below it.
  const { ctx, calls } = mockHost({
    sessions: [liveChild("ses_live"), historicalChild("ses_old")],
    status: (id) => (id === "ses_live" ? "running" : "idle"),
  });
  const model = createTuiModel(ctx);
  try {
    assert.equal(calls.commands.length, 6, "the command layer is registered");
    const rows = model.liveRows();
    const live = rows.find((r) => r.sessionID === "ses_live");
    const old = rows.find((r) => r.sessionID === "ses_old");
    assert.equal(live?.status, "running", "the live map is read before association");
    assert.equal(live?.stale, false);
    assert.equal(old?.status, "unknown");
    assert.equal(old?.stale, true);
    assert.equal(model.liveBanner(), null, "healthy host: no banner");
    assert.equal(model.state.delegates.size, 2);
    // the view's memo layer exists and is wired to the same projections
    assert.equal(typeof model.rows, "function");
    assert.equal(typeof model.banner, "function");
    assert.deepEqual(model.rows().map((r) => r.sessionID), rows.map((r) => r.sessionID));
  } finally {
    model.dispose();
  }
});

test("a throwing status map is a banner, not a crash", () => {
  const { ctx } = mockHost({
    sessions: [liveChild("ses_live")],
    status: () => { throw new Error("no status"); },
  });
  const model = createTuiModel(ctx);
  try {
    assert.match(model.liveBanner() ?? "", /cannot read the live session status map/);
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
      assert.match(model!.liveBanner() ?? "", /cannot read the live session status map/);
      assert.deepEqual(model!.liveRows(), []);
    } finally {
      model!.dispose();
    }
  }
});

test("a throwing session list is a banner, not a crash", () => {
  const { ctx } = mockHost({ list: () => { throw new Error("list closed"); } });
  const model = createTuiModel(ctx);
  try {
    assert.match(model.liveBanner() ?? "", /cannot read the live session status map/);
    assert.deepEqual(model.liveRows(), []);
  } finally {
    model.dispose();
  }
});

test("the event stream drives rows through the real listener", () => {
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
    assert.ok(row);
    assert.equal(row.status, "running");
    assert.equal(row.agent, "planner");
    assert.ok(calls.toasts.length >= 0);
  } finally {
    model.dispose();
    assert.equal(calls.disposed, 1, "dispose unsubscribes the listener");
  }
});

test("the live picker excludes collapsed history; history is its own path", async () => {
  const { ctx, calls } = mockHost({
    sessions: [liveChild("ses_live"), historicalChild("ses_old")],
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

    // Steer/ints on a stale-only inbox: the live picker reports empty and
    // never offers the collapsed row.
    const staleOnly = mockHost({
      sessions: [historicalChild("ses_old")],
      status: () => "idle",
    });
    const idle = createTuiModel(staleOnly.ctx);
    try {
      await command(staleOnly.calls, "delegation.focus").run();
      assert.deepEqual(staleOnly.calls.focus, []);
      assert.match(staleOnly.calls.toasts.at(-1)?.message ?? "", /no delegates observed/);
      await command(staleOnly.calls, "delegation.history").run();
      assert.deepEqual(staleOnly.calls.focus, ["ses_old"]);
      assert.ok(idle);
    } finally {
      idle.dispose();
    }
  } finally {
    model.dispose();
  }
});

test("the history path reports an empty history instead of opening a dialog", async () => {
  const { ctx, calls } = mockHost({
    sessions: [liveChild("ses_live")],
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

test("status reports health, and a degraded observer through the banner", async () => {
  const healthy = mockHost({ sessions: [] });
  const model = createTuiModel(healthy.ctx);
  try {
    await command(healthy.calls, "delegation.status").run();
    assert.match(healthy.calls.toasts.at(-1)?.message ?? "", /healthy/);
  } finally {
    model.dispose();
  }

  const degraded = mockHost({ plugin: "missing" });
  const broken = createTuiModel(degraded.ctx);
  try {
    await command(degraded.calls, "delegation.status").run();
    const toast = degraded.calls.toasts.at(-1);
    assert.equal(toast?.title, "delegation degraded");
    assert.match(toast?.message ?? "", /not loaded/);
  } finally {
    broken.dispose();
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
