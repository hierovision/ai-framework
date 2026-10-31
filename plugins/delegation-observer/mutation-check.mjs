#!/usr/bin/env node
/**
 * Break/restore proofs for the delegation observer's liveness guards.
 *
 * Run: node plugins/delegation-observer/mutation-check.mjs
 *
 * Every entry names one guard of the 2026-10-30 stale-row fix, the exact
 * source text that implements it, and the test that must fail without it. The
 * script:
 *   1. runs the suite once (baseline must be green),
 *   2. for each mutation: backs the file up, applies the textual mutation,
 *      runs the file's suite, and requires a NON-ZERO exit whose output names
 *      the expected failing test,
 *   3. restores the file in `finally` and byte-compares it with the original,
 *   4. exits non-zero if any mutation survived, failed for the wrong reason,
 *      or the tree was not restored.
 *
 * A green run here is the checked-in evidence that each test fails for its
 * own reason — not a claim in a PR body.
 */
import { spawnSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const TESTS = ["state.test.ts", "tui.test.ts", "server.test.ts", "model.test.ts"]
  .map((f) => join(HERE, f));

const MUTATIONS = [
  {
    id: "fabricate-last-activity",
    why: "quiet must be the session's last event, not the observer boot clock",
    file: "state.ts",
    from: 'lastActivityAt: source === "observed" ? now : updated,',
    to: "lastActivityAt: now,",
    expect: "a discovered session with no events is never running",
  },
  {
    id: "drop-tick-guard",
    why: "a discovered row has no observation clock and must not be classified",
    file: "state.ts",
    from: '    if (d.provenance === "discovered") continue;\n',
    to: "",
    expect: "an active-map row is never stall-classified without an observed event",
  },
  {
    id: "ignore-live-map",
    why: "only the host live map may make a discovered row running",
    file: "state.ts",
    from: '    } else if (live) {\n      delegate.status = "running";',
    to: '    } else if (false) {\n      delegate.status = "running";',
    expect: "only the live active map can make a discovered session running",
  },
  {
    id: "read-wrong-outcome-field",
    why: "SessionInfo.outcome is the real host field, not a DB-column alias",
    file: "state.ts",
    from: "return normalizeOutcome(info.outcome ?? info.idleOutcome ?? info.idle_outcome ?? null);",
    to: "return normalizeOutcome(info.idleOutcome ?? info.idle_outcome ?? null);",
    expect: "a store-terminal row is completed at bootstrap from the real outcome field",
  },
  {
    id: "drop-store-outcome",
    why: "a store-terminal row is history, never a revivable delegate",
    file: "state.ts",
    from: "    if (outcome) {\n      applyStoreOutcome(delegate, outcome, updated ?? created);\n    } else if (archived) {",
    to: "    if (false) {\n      applyStoreOutcome(delegate, outcome, updated ?? created);\n    } else if (archived) {",
    expect: "a recent completed child is never revived by later events",
  },
  {
    id: "promotion-without-touch",
    why: "the first observed event must reset the observation clock (F2)",
    file: "state.ts",
    from: "    touch(d, now);\n    if (d.status === \"unknown\") {",
    to: "    d.stale = false;\n    if (d.status === \"unknown\") {",
    expect: "the first real event refreshes the observation clock (F2)",
  },
  {
    id: "archived-after-live",
    why: "archived must outrank the live map",
    file: "state.ts",
    from:
      "  if (d.archived) return true;\n"
      + "  if (d.terminal) return d.provenance !== \"observed\";\n"
      + "  if (d.provenance === \"observed\") return false;\n"
      + "  if (isActive(state, d.sessionID)) return false;\n",
    to:
      "  if (d.terminal) return d.provenance !== \"observed\";\n"
      + "  if (d.provenance === \"observed\") return false;\n"
      + "  if (isActive(state, d.sessionID)) return false;\n"
      + "  if (d.archived) return true;\n",
    expect: "an archived session is stale even when the live map calls it running",
  },
  {
    id: "archived-after-observed",
    why: "archived must outrank observed provenance on the clock refresh",
    file: "state.ts",
    from:
      "  if (d.archived) return true;\n"
      + "  if (d.terminal) return d.provenance !== \"observed\";\n"
      + "  if (d.provenance === \"observed\") return false;\n",
    to:
      "  if (d.terminal) return d.provenance !== \"observed\";\n"
      + "  if (d.provenance === \"observed\") return false;\n"
      + "  if (d.archived) return true;\n",
    expect: "archive after start hides an observed row, unarchive restores it",
  },
  {
    id: "drop-stale-collapse",
    why: "history collapses to one line instead of a wall of rows",
    file: "view.ts",
    from: "  if (stale > 0) lines.push(`${stale} stale delegates hidden`);\n",
    to: "",
    expect: "historical rows collapse to one line and never claim to be running",
  },
  {
    id: "select-stale-rows",
    why: "stale rows must not be selectable targets",
    file: "view.ts",
    from: "  return (rows ?? []).filter((row) => !row.stale);",
    to: "  return rows ?? [];",
    expect: "stale rows are not selectable and not actionable",
  },
  {
    id: "silent-live-map-failure",
    why: "an unreadable live map must degrade visibly",
    file: "view.ts",
    from: '  if (liveMap === "unavailable") {\n',
    to: '  if (false) {\n',
    expect: "an unavailable live map degrades visibly instead of hiding rows",
  },
  {
    id: "live-map-revives-terminal",
    why: "a store-terminal row must not be revived by the live map",
    file: "state.ts",
    from: "  if (!d || d.archived || d.terminal || d.provenance === \"observed\") return d ?? null;\n",
    to: "  if (!d || d.archived || d.provenance === \"observed\") return d ?? null;\n",
    expect: "the store outcome outranks the live map and cannot be demoted",
  },
  {
    id: "archived-replay-emits-start",
    why: "archive handling must run before the create/rename milestones",
    file: "state.ts",
    from:
      "  let d = sessionID ? state.delegates.get(sessionID) ?? null : null;\n"
      + "  if (d && type === \"session.archived\") {",
    to:
      "  let d: any = null;\n"
      + "  if (d && type === \"session.archived\") {",
    expect: "an archived row never emits a start milestone on a replayed create",
  },
  {
    id: "non-array-list-crashes",
    why: "a null/non-array session list must degrade, never throw (F10)",
    file: "model.ts",
    from: "      const listed = rawSessionList();\n      return Array.isArray(listed) ? listed : [];",
    to: "      const listed = rawSessionList();\n      return listed as any[];",
    expect: "a null, undefined or non-array session list is normalized",
  },
  {
    id: "model-tdz-missing-binding",
    why: "the projections must only close over initialized bindings (F9)",
    file: "model.ts",
    from: "  const liveSessionRows = () => {",
    to: "  const liveSessionRowsLater = () => {",
    expect: "the model constructs over a healthy host and bootstraps liveness",
  },
  {
    id: "model-live-map-not-reported",
    why: "refreshActive must publish live-map availability to the banner",
    file: "model.ts",
    from:
      "    const availabilityChanged = availability !== liveMap();\n"
      + "    if (availabilityChanged) setLiveMap(availability);\n",
    to: "    const availabilityChanged = false;\n",
    expect: "a throwing status map is a banner, not a crash",
  },
  {
    id: "health-record-ignored",
    why: "the shared health record must reach the banner and the status command",
    file: "model.ts",
    from: "      const next = record?.degradation ?? null;\n",
    to: "      const next = null;\n",
    expect: "the shared health record reaches the banner and the status command",
  },
  {
    id: "timer-skips-refresh",
    why: "the interval must refresh the live map (the only liveness source)",
    file: "model.ts",
    from: "  const timer = setInterval(() => {\n    refreshActive();\n",
    to: "  const timer = setInterval(() => {\n",
    expect: "one interval tick refreshes the live map and the rows",
  },
  {
    id: "live-map-null-elements",
    why: "malformed array elements must be dropped, not dereferenced",
    file: "view.ts",
    from:
      "  const sessions = (listed as unknown[]).filter(\n"
      + "    (session): session is LiveMap[\"sessions\"][number] =>\n"
      + "      Boolean(session) && typeof session === \"object\",\n"
      + "  );\n",
    to: "  const sessions = listed as LiveMap[\"sessions\"];\n",
    // the element-filter contract is asserted by the model suite
    test: "model.test.ts",
    expect: "malformed array elements are dropped, not dereferenced",
  },
  {
    id: "plugin-status-missing",
    why: "an absent plugin record must degrade, never read as loaded",
    file: "model.ts",
    from: '    if (!entry) return { loaded: false, state: "missing", tui: false };\n',
    to: '    if (!entry) return { loaded: true, state: "active", tui: true };\n',
    expect: "a missing plugin degrades the status command with the banner reason",
  },
  {
    id: "plugin-status-failed",
    why: "a failed plugin record must surface its load error",
    file: "model.ts",
    from: '    const state = entry.state?.status === "failed"\n',
    to: '    const state = entry.state?.status === "never"\n',
    expect: "a failed plugin degrades the status command with the load error",
  },
  {
    id: "status-ignores-healthy-branch",
    why: "a healthy observer must report healthy, not degraded",
    file: "model.ts",
    from: "    const warning = liveBanner();\n    if (!warning) {\n",
    to: "    const warning = liveBanner();\n    if (false) {\n",
    expect: "a healthy observer reports healthy from the status command",
  },
  {
    id: "map-loss-keeps-running",
    why: "an unavailable live map must demote discovered rows, not keep them running",
    file: "model.ts",
    from: "    const membershipChanged = reconcileActive(state, live);\n",
    to: "    const membershipChanged = false;\n",
    expect: "losing the live map demotes a running row, and recovery restores it (F18)",
  },
  {
    id: "absent-session-not-denied",
    why: "an id missing from an available map must be denied",
    file: "state.ts",
    from: "  for (const sessionID of known) {\n",
    to: "  for (const sessionID of live) {\n",
    // proven end-to-end at the model layer (the tick -> row demotion path)
    test: "model.test.ts",
    expect: "a session that leaves an available map stops being running (F18)",
  },
  {
    id: "reconcile-ignores-discovered",
    why: "every discovered row must be reconciled, not only active-map keys (F21)",
    file: "state.ts",
    from:
      "  const known = new Set<string>([...state.active.keys(), ...live]);\n"
      + "  for (const d of state.delegates.values()) {\n"
      + "    if (d.provenance === \"discovered\") known.add(d.sessionID);\n"
      + "  }\n",
    to: "  const known = new Set<string>(live);\n",
    expect: "reconcileActive denies a row promoted by info.active, however it was promoted",
  },
  {
    id: "associate-active-unrecorded",
    why: "an info.active promotion must leave a map entry to be denied later (F21)",
    file: "state.ts",
    from:
      "  if (knownActive === undefined && info.active !== undefined) {\n"
      + "    state.active.set(sessionID, Boolean(info.active));\n"
      + "  }\n",
    to: "",
    expect: "reconcileActive denies a row promoted by info.active, however it was promoted",
  },
  {
    id: "drop-version-read",
    why: "projections must read the version signal so a bump re-renders",
    file: "model.ts",
    from: "    version();\n    return compute();\n",
    to: "    return compute();\n",
    test: "model.test.ts",
    expect: "every projection reads the version signal so a bump re-renders",
  },
  {
    id: "definition-slot-missing",
    why: "the TUI registration must claim the documented slots",
    file: "model.ts",
    from: '          append: "home.footer.status",',
    to: '          append: "sidebar.content",',
    expect: "createDefinition registers the documented slots and disposes them",
  },
];

const TEST_FOR = {
  "state.ts": "state.test.ts",
  "view.ts": "tui.test.ts",
  "model.ts": "model.test.ts",
  "tui.tsx": "tui.test.ts",
  "server.ts": "server.test.ts",
};

function runSuite(files) {
  const result = spawnSync(process.execPath, ["--test", ...files], {
    cwd: HERE,
    encoding: "utf8",
    timeout: 120_000,
  });
  return {
    status: result.status ?? 1,
    output: `${result.stdout ?? ""}${result.stderr ?? ""}`,
  };
}

function failingNames(output) {
  const names = [];
  for (const line of output.split("\n")) {
    const match = /^\s*✖\s+(.+?)(?:\s+\(\d|$)/.exec(line);
    if (match) names.push(match[1].trim());
  }
  return [...new Set(names)];
}

function main() {
  const originals = new Map();
  for (const name of new Set(MUTATIONS.map((mutation) => mutation.file))) {
    const file = join(HERE, name);
    originals.set(file, readFileSync(file, "utf8"));
  }

  process.stdout.write("baseline: ");
  const baseline = runSuite(TESTS);
  if (baseline.status !== 0) {
    process.stdout.write("FAIL\n");
    process.stdout.write(baseline.output);
    return 1;
  }
  process.stdout.write("green\n");

  const failures = [];
  for (const mutation of MUTATIONS) {
    const file = join(HERE, mutation.file);
    const original = originals.get(file);
    if (original === undefined) {
      failures.push(`${mutation.id}: ${mutation.file} is not tracked by this script`);
      continue;
    }
    if (!original.includes(mutation.from)) {
      failures.push(`${mutation.id}: mutation anchor not found in ${mutation.file}`);
      continue;
    }
    writeFileSync(file, original.replace(mutation.from, mutation.to), "utf8");
    let result;
    try {
      const testFile = mutation.test ?? TEST_FOR[mutation.file];
      if (!testFile) {
        failures.push(`${mutation.id}: no test file mapped for ${mutation.file}`);
        continue;
      }
      result = runSuite([join(HERE, testFile)]);
    } finally {
      writeFileSync(file, original, "utf8");
    }
    const names = failingNames(result.output);
    if (result.status === 0) {
      failures.push(`${mutation.id}: SURVIVED — ${mutation.expect} stayed green (${mutation.why})`);
      continue;
    }
    if (!names.includes(mutation.expect)) {
      failures.push(
        `${mutation.id}: failed for the wrong reason — expected "${mutation.expect}", got [${names.join(", ")}]`,
      );
      continue;
    }
    process.stdout.write(`ok   ${mutation.id} -> red "${mutation.expect}"\n`);
  }

  for (const [file, original] of originals) {
    if (readFileSync(file, "utf8") !== original) {
      failures.push(`${file}: NOT RESTORED — restore it before committing`);
    }
  }

  process.stdout.write("baseline after restore: ");
  const after = runSuite(TESTS);
  process.stdout.write(after.status === 0 ? "green\n" : "FAIL\n");
  if (after.status !== 0) {
    process.stdout.write(after.output);
    failures.push("the suite is not green after restoring the mutations");
  }

  if (failures.length) {
    process.stdout.write(`\n${failures.length} failure(s):\n`);
    for (const failure of failures) process.stdout.write(`FAIL: ${failure}\n`);
    return 1;
  }
  process.stdout.write(`\n0 failure(s) — ${MUTATIONS.length} guards proven\n`);
  return 0;
}

process.exit(main());
