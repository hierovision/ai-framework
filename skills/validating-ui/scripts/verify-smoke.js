#!/usr/bin/env node
// Objective self-check for the validating-ui skill (failable verifier,
// per the capturing-ui-evidence precedent). Drives smoke.mjs's runSmoke
// against the bundled fake chromium, per state:
//   green       -> exit 0 (net clean, artifact valid)
//   allowlisted -> exit 0 (warning covered by the fixture allowlist)
//   error       -> exit non-zero (console error blocks)
//   warning     -> exit non-zero (console warning blocks)
//   pageerror   -> exit non-zero (pageerror blocks)
//   bad-evidence-> the schema validator rejects the bundled malformed
//                  artifact (exit non-zero)
//   usage       -> the CLI contract holds: --help exits 0 with usage
//                  text; missing required args exit 2; parseArgs maps
//                  every flag (guards the CLI surface that runSmoke
//                  driving never reaches)
// Usage:
//   node verify-smoke.js <state>       # one state
//   node verify-smoke.js --all         # every state; exit 0 iff all pass
import { mkdtempSync, writeFileSync, readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const SKILL_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const SMOKE = join(SKILL_ROOT, "scripts", "smoke.mjs");
const FAKE = join(SKILL_ROOT, "scripts", "fake-chromium.mjs");
const FIXTURE = join(SKILL_ROOT, "evals", "fixtures", "smoke-basic");
const JOURNEY = join(FIXTURE, "journey.mjs");
const ALLOWLIST = join(FIXTURE, "allowlist.json");
const BAD_EVIDENCE = join(FIXTURE, "bad-evidence.json");

function validateEvidence(a) {
  const bad = [];
  if (a?.schema_version !== "1.0") bad.push("schema_version");
  if (typeof a?.target !== "string" || !a.target) bad.push("target");
  if (typeof a?.journey !== "string" || !a.journey) bad.push("journey");
  if (!Array.isArray(a?.console_errors)) bad.push("console_errors[]");
  if (!Array.isArray(a?.console_warnings)) bad.push("console_warnings[]");
  if (!Array.isArray(a?.page_errors)) bad.push("page_errors[]");
  if (typeof a?.screenshots?.full !== "string" || !a.screenshots.full) bad.push("screenshots.full");
  if (typeof a?.aria_snapshot !== "string") bad.push("aria_snapshot");
  if (typeof a?.net_clean !== "boolean") bad.push("net_clean");
  if (bad.length) return { ok: false, missing: bad };
  return { ok: true };
}

async function runState(state, log = () => {}) {
  const { runSmoke } = await import(SMOKE);
  const { createFakeBrowser } = await import(FAKE);
  const outDir = mkdtempSync(join(tmpdir(), "validating-ui-"));
  const browserFactory = () => createFakeBrowser(state);
  const result = await runSmoke({
    target: "http://localhost:9999",
    journey: JOURNEY,
    out: outDir,
    allowlist: ALLOWLIST,
    browserFactory,
  });
  const evidence = JSON.parse(readFileSync(join(outDir, "evidence.json"), "utf-8"));
  return { result, evidence, outDir };
}

const CHECKS = {
  green: async (log) => {
    const { result, evidence } = await runState("green", log);
    const v = validateEvidence(evidence);
    const ok = result.exitCode === 0 && v.ok && evidence.net_clean === true && evidence.console_errors.length === 0;
    if (!ok) log(`green: exit=${result.exitCode} net_clean=${evidence.net_clean} validator=${v.ok ? "ok" : v.missing}`);
    return ok;
  },
  allowlisted: async (log) => {
    const { result, evidence } = await runState("allowlisted", log);
    const ok = result.exitCode === 0 && evidence.allowlisted.length === 1 && evidence.console_warnings.length === 1;
    if (!ok) log(`allowlisted: exit=${result.exitCode} allowlisted=${evidence.allowlisted.length} warnings=${evidence.console_warnings.length}`);
    return ok;
  },
  error: async (log) => {
    const { result, evidence } = await runState("error", log);
    const ok = result.exitCode !== 0 && result.report.includes("Failed to fetch dynamically imported module");
    if (!ok) log(`error negative: exit=${result.exitCode} report=${JSON.stringify(result.report.slice(0, 120))}`);
    return ok;
  },
  warning: async (log) => {
    const { result } = await runState("warning", log);
    const ok = result.exitCode !== 0 && result.report.includes("Unhandled error during execution");
    if (!ok) log(`warning negative: exit=${result.exitCode} report=${JSON.stringify(result.report.slice(0, 120))}`);
    return ok;
  },
  pageerror: async (log) => {
    const { result } = await runState("pageerror", log);
    const ok = result.exitCode !== 0 && result.report.includes("stopPreview");
    if (!ok) log(`pageerror negative: exit=${result.exitCode} report=${JSON.stringify(result.report.slice(0, 120))}`);
    return ok;
  },
  "bad-evidence": async () => {
    const artifact = JSON.parse(readFileSync(BAD_EVIDENCE, "utf-8"));
    return validateEvidence(artifact).ok === false;
  },
  usage: async (log) => {
    // Coverage-gate expansion: the CLI surface (parseArgs / usage /
    // missing-required exit 2) is never reached by runSmoke driving.
    // Both CLI paths exit before runSmoke, so the lazy playwright
    // import is never touched.
    const { parseArgs } = await import(SMOKE);
    const helpOk = (() => {
      try {
        const out = execFileSync(process.execPath, [SMOKE, "--help"], { stdio: ["ignore", "pipe", "pipe"], encoding: "utf-8" });
        return out.includes("usage: node smoke.mjs");
      } catch {
        return false;
      }
    })();
    const missingOk = (() => {
      try {
        execFileSync(process.execPath, [SMOKE], { stdio: ["ignore", "pipe", "pipe"], encoding: "utf-8" });
        return false; // no exit 2 => the harness ran instead of refusing: broken
      } catch (e) {
        return e.status === 2 && String(e.stderr).includes("missing required: --target");
      }
    })();
    const parsed = parseArgs([
      "--target", "http://x", "--journey", "j.mjs", "--out", "d",
      "--allowlist", "w.json", "--no-screenshot",
    ]);
    const parseOk =
      parsed.target === "http://x" && parsed.journey === "j.mjs" &&
      parsed.out === "d" && parsed.allowlist === "w.json" &&
      parsed.noScreenshot === true && parsed.viewport === "1280x720";
    if (!helpOk) log("usage: --help did not print usage / exit 0");
    if (!missingOk) log("usage: missing required args did not exit 2 with a missing list");
    if (!parseOk) log(`usage: parseArgs mis-mapped: ${JSON.stringify(parsed)}`);
    return helpOk && missingOk && parseOk;
  },
};

const stateArg = process.argv[2];
const all = stateArg === "--all";

if (all) {
  let failed = 0;
  for (const [state, check] of Object.entries(CHECKS)) {
    try {
      const ok = await check((m) => console.log(`  ${m}`));
      console.log(`${ok ? "PASS" : "FAIL"}  ${state}`);
      if (!ok) failed++;
    } catch (e) {
      failed++;
      console.log(`FAIL  ${state} (threw: ${e.message})`);
    }
  }
  process.exit(failed ? 1 : 0);
}

if (!CHECKS[stateArg]) {
  console.error(`usage: node verify-smoke.js <${Object.keys(CHECKS).join("|")}|--all>`);
  process.exit(2);
}
try {
  const ok = await CHECKS[stateArg]((m) => console.log(`  ${m}`));
  const verdicts = {
    green: "exit 0, net clean, evidence schema-valid",
    allowlisted: "exit 0, warning covered by the allowlist",
    error: "harness blocked (exit non-zero), message text in report",
    warning: "harness blocked (exit non-zero), message text in report",
    pageerror: "harness blocked (exit non-zero), message text in report",
    "bad-evidence": "malformed artifact rejected by the validator",
    usage: "CLI contract holds (--help exit 0, missing-required exit 2, parseArgs mapping)",
  };
  console.log(`${ok ? "PASS" : "FAIL"}  ${stateArg} — ${verdicts[stateArg]}`);
  process.exit(ok ? 0 : 1);
} catch (e) {
  console.error(`FAIL ${stateArg}: threw ${e.message}`);
  process.exit(1);
}
