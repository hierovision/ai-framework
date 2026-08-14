#!/usr/bin/env node
// validating-ui smoke harness — deterministic runtime UI validation.
//
// Drives a *journey module* (writing-e2e-tests doctrine: role /
// accessible-name / testid selectors, condition waits, never
// waitForTimeout, auth via fixture) through a real browser, captures
// console errors/warnings + pageerrors, screenshots (full-page +
// element clip), and the page's ariaSnapshot, and writes evidence.json.
//
// Net discipline (R1): console errors AND warnings AND pageerrors block
// the run (exit non-zero) unless the message matches an allowlist entry.
// Allowlist entries must be dated + justified (no blanket suppression).
// The allowlist is a PROJECT-OWNED override point: --allowlist <path>,
// else auto-discovered .opencode/smoke-allowlist.json in the cwd, else
// no allowlist (strictest mode).
//
// CLI (stack-agnostic surface — local overrides wire the rest):
//   node smoke.mjs --target <baseURL> --journey <path> --out <dir>
//     [--allowlist <path>] [--auth-fixture <path>] [--clip-role <role>
//     --clip-name <name> | --clip-testid <id>] [--viewport WxH]
//     [--chromium <executable>] [--no-screenshot]
// Env: VALIDATING_UI_VISION=1 (optional advisory vision pass — see
// SKILL.md; the harness itself only archives the screenshot).
import { mkdirSync, writeFileSync, readFileSync, existsSync } from "node:fs";
import { join, resolve, dirname, basename } from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";

const SCHEMA_VERSION = "1.0";

export function parseArgs(argv) {
  const args = { viewport: "1280x720" };
  for (let i = 0; i < argv.length; i += 2) {
    const k = argv[i];
    const v = argv[i + 1];
    if (k === "--target") args.target = v;
    else if (k === "--journey") args.journey = v;
    else if (k === "--out") args.out = v;
    else if (k === "--allowlist") args.allowlist = v;
    else if (k === "--auth-fixture") args.authFixture = v;
    else if (k === "--clip-role") args.clipRole = v;
    else if (k === "--clip-name") args.clipName = v;
    else if (k === "--clip-testid") args.clipTestid = v;
    else if (k === "--viewport") args.viewport = v;
    else if (k === "--chromium") args.chromium = v;
    else if (k === "--no-screenshot") args.noScreenshot = true;
    else if (k === "--help") args.help = true;
  }
  return args;
}

function usage() {
  return `usage: node smoke.mjs --target <baseURL> --journey <path> --out <dir>
  [--allowlist <path>] [--auth-fixture <path>]
  [--clip-role <role> --clip-name <name> | --clip-testid <id>]
  [--viewport WxH] [--chromium <executable>] [--no-screenshot]`;
}

function loadAllowlist(pathArg) {
  let candidates = [];
  if (pathArg) candidates.push(resolve(pathArg));
  else {
    const auto = join(process.cwd(), ".opencode", "smoke-allowlist.json");
    if (existsSync(auto)) candidates.push(auto);
  }
  for (const p of candidates) {
    if (!existsSync(p)) continue;
    const data = JSON.parse(readFileSync(p, "utf-8"));
    const entries = Array.isArray(data) ? data : data.entries || [];
    return { path: p, entries };
  }
  return { path: null, entries: [] };
}

function isAllowlisted(message, allowlist) {
  for (const e of allowlist.entries) {
    if (typeof e?.pattern === "string" && message.includes(e.pattern)) return e;
  }
  return null;
}

function validateEvidence(a) {
  const bad = [];
  if (a?.schema_version !== SCHEMA_VERSION) bad.push("schema_version");
  if (typeof a?.target !== "string" || !a.target) bad.push("target");
  if (typeof a?.journey !== "string" || !a.journey) bad.push("journey");
  if (!Array.isArray(a?.console_errors)) bad.push("console_errors[]");
  if (!Array.isArray(a?.console_warnings)) bad.push("console_warnings[]");
  if (!Array.isArray(a?.page_errors)) bad.push("page_errors[]");
  if (typeof a?.screenshots?.full !== "string" || !a.screenshots.full) bad.push("screenshots.full");
  if (typeof a?.aria_snapshot !== "string") bad.push("aria_snapshot");
  if (typeof a?.net_clean !== "boolean") bad.push("net_clean");
  return bad;
}

export { validateEvidence };

// Core, browser-injectable: browserFactory() -> { createBrowserContext(), close() }
// returns { exitCode, report, evidence }
export async function runSmoke(opts) {
  const {
    target,
    journey,
    out,
    allowlist = null,
    authFixture = null,
    clipRole = null,
    clipName = null,
    clipTestid = null,
    viewport = "1280x720",
    noScreenshot = false,
    browserFactory = null,
  } = opts;

  mkdirSync(out, { recursive: true });
  const allowlistData = loadAllowlist(allowlist);
  const [vw, vh] = viewport.split("x").map(Number);
  const report = [];
  const evidence = {
    schema_version: SCHEMA_VERSION,
    generated_at: new Date().toISOString(),
    target,
    journey: basename(journey),
    allowlist_path: allowlistData.path,
    console_errors: [],
    console_warnings: [],
    page_errors: [],
    screenshots: { full: null, clip: null },
    aria_snapshot: null,
    journey_error: null,
    net_clean: false,
    allowlisted: [],
  };

  let browser;
  try {
    browser = browserFactory
      ? await browserFactory()
      : await (await import("playwright")).chromium.launch({
          executablePath: process.env.CAPTURE_CHROMIUM_EXECUTABLE || undefined,
          headless: true,
        });
    const ctxOpts = { viewport: { width: vw, height: vh } };
    if (authFixture) ctxOpts.storageState = authFixture;
    const context = await browser.createBrowserContext(ctxOpts);
    const page = await context.newPage();

    page.on("console", (msg) => {
      if (msg.type() === "error") evidence.console_errors.push(msg.text());
      else if (msg.type() === "warning") evidence.console_warnings.push(msg.text());
    });
    page.on("pageerror", (err) => {
      evidence.page_errors.push({ message: String(err?.message || err), stack: String(err?.stack || "").split("\n").slice(0, 4).join("\n") });
    });

    let journeyResult = {};
    try {
      const mod = await import(pathToFileURL(resolve(journey)).href);
      journeyResult = (await mod.run(page)) || {};
    } catch (e) {
      evidence.journey_error = String(e?.message || e);
    }

    // Flush bridge for the fake browser (deterministic emission at end of
    // journey; a real browser fires these live during the journey).
    if (typeof page._flush === "function") page._flush();

    if (!evidence.journey_error && !noScreenshot) {
      try {
        const full = join(out, "full.png");
        writeFileSync(full, await page.screenshot({ fullPage: true }));
        evidence.screenshots.full = basename(full);
      } catch (e) {
        report.push(`note: full-page screenshot failed: ${e.message}`);
      }
      try {
        let shot = null;
        if (clipTestid) shot = await page.getByTestId(clipTestid).screenshot();
        else if (clipRole) shot = await page.getByRole(clipRole, clipName ? { name: clipName } : {}).screenshot();
        if (shot) {
          const clip = join(out, "clip.png");
          writeFileSync(clip, shot);
          evidence.screenshots.clip = basename(clip);
        }
      } catch (e) {
        report.push(`note: element clip failed (selector unresolved): ${e.message}`);
      }
    }

    try {
      evidence.aria_snapshot = await page.locator("body").ariaSnapshot();
    } catch (e) {
      report.push(`note: ariaSnapshot unavailable: ${e.message}`);
    }

    // Net: errors AND warnings AND pageerrors block unless allowlisted.
    const violations = [];
    const check = (list, kind) => {
      for (const item of list) {
        const text = typeof item === "string" ? item : item.message;
        const entry = isAllowlisted(text, allowlistData);
        if (entry) evidence.allowlisted.push({ message: text, pattern: entry.pattern, date: entry.date, reason: entry.reason });
        else violations.push({ kind, text });
      }
    };
    check(evidence.console_errors, "console.error");
    check(evidence.console_warnings, "console.warning");
    check(evidence.page_errors, "pageerror");

    evidence.net_clean = violations.length === 0 && !evidence.journey_error;

    if (evidence.journey_error) {
      report.push(`journey failed: ${evidence.journey_error}`);
    }
    for (const v of violations) {
      report.push(`blocking ${v.kind}: ${v.text}`);
    }
    if (violations.length === 0 && !evidence.journey_error) {
      report.push("net clean: no console errors, warnings, or pageerrors");
    }
  } finally {
    if (browser) await browser.close();
  }

  writeFileSync(join(out, "evidence.json"), JSON.stringify(evidence, null, 2));

  const exitCode = evidence.net_clean ? 0 : 1;
  return { exitCode, report: report.join("\n"), evidence };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    console.log(usage());
    process.exit(0);
  }
  const missing = [];
  if (!args.target) missing.push("--target");
  if (!args.journey) missing.push("--journey");
  if (!args.out) missing.push("--out");
  if (missing.length) {
    console.error(`missing required: ${missing.join(", ")}\n${usage()}`);
    process.exit(2);
  }
  const { exitCode, report } = await runSmoke({
    target: args.target,
    journey: args.journey,
    out: args.out,
    allowlist: args.allowlist,
    authFixture: args.authFixture,
    clipRole: args.clipRole,
    clipName: args.clipName,
    clipTestid: args.clipTestid,
    viewport: args.viewport,
    noScreenshot: args.noScreenshot,
  });
  console.log(report);
  process.exit(exitCode);
}

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1]);
if (isMain) await main();
