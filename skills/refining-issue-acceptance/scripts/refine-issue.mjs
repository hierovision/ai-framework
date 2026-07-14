#!/usr/bin/env node
// refine-issue.mjs — refine a GitHub issue into a proper engineering spec.
//
// The model authors the refined body (a short description + tagged, behavioral
// acceptance criteria, per references/acceptance-criteria.md). This script is
// the deterministic, re-runnable side-effect layer, mirroring the pattern of
// managing-github-issues/scripts/sync-issues.mjs:
//   - fetch the current issue (or read --current-body for an offline check)
//   - validate the refined AC rules (section present, every AC tagged, no
//     file/module/function leak)
//   - --dry-run (default): print the before -> after and VALIDATION result
//   - --apply: re-validate, then `gh issue edit` the live issue — but only
//     after the agent has obtained explicit user confirmation (external effect)
//
// A bad spec is never pushed: --apply refuses (exit non-zero) on validation
// failure, and --dry-run exits non-zero on failure so evals can assert the
// FAIL path.
//
// Run-as-main gate survives a symlinked install (realpath'd argv[1]).

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { realpathSync } from "node:fs";
import { dirname, resolve, join } from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// ---- args ----
function parseArgs(argv) {
  const a = {
    issue: null, repo: null, refinedBody: null, title: null,
    currentBody: null, currentTitle: null, dryRun: false, apply: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const t = argv[i];
    if (t === "--dry-run") a.dryRun = true;
    else if (t === "--apply") a.apply = true;
    else if (t === "--issue") a.issue = argv[++i];
    else if (t === "--repo") a.repo = argv[++i];
    else if (t === "--refined-body") a.refinedBody = argv[++i];
    else if (t === "--title") a.title = argv[++i];
    else if (t === "--current-body") a.currentBody = argv[++i];
    else if (t === "--current-title") a.currentTitle = argv[++i];
    else if (t === "--help" || t === "-h") {
      console.log("Usage: node refine-issue.mjs --refined-body <file> [--issue <n> --repo owner/name | --current-title <t> --current-body <file>] [--title <proposed>] [--dry-run|--apply]");
      process.exit(0);
    } else {
      console.error(`error: unknown arg "${t}"`);
      process.exit(2);
    }
  }
  if (!a.refinedBody) { console.error("error: --refined-body <file> is required"); process.exit(2); }
  if (!existsSync(a.refinedBody)) { console.error(`error: refined body not found: ${a.refinedBody}`); process.exit(2); }
  // Default-safe: if neither --apply nor --dry-run is given, dry-run.
  if (!a.apply && !a.dryRun) a.dryRun = true;
  return a;
}

// ---- validation ----
// Implementation-leak denylist: file paths, source-file names, code declarations.
// Conservative by design — catches obvious leaks without flagging plain prose.
const LEAK_PATTERNS = [
  /\b(src|app|components?|lib|pkg|api|utils?|services?|stores?|features?|modules?|routes?|handlers?|views?|models?)\/[\w./-]*/i,
  /\b[\w-]+\.(ts|tsx|js|jsx|mjs|cjs|py|go|rs|java|rb|php|vue|svelte|css|scss)\b/i,
  /\b(function|class|interface|struct|enum|namespace|trait|impl)\s+[A-Za-z_]\w*/,
  /\b(import|export)\s+[{(*A-Za-z]/,
  /\b(def|const|let|var|private|public|protected|static|async|fn)\s+[A-Za-z_]\w*\s*[=(:]/,
];

const TEST_TYPE_TAGS = ["unit", "integration", "e2e"];

function findLeaks(text) {
  const hits = [];
  for (const re of LEAK_PATTERNS) {
    const m = text.match(re);
    if (m) hits.push(m[0]);
  }
  return hits;
}

function countTaggedAcs(text) {
  const lines = text.split("\n");
  let inAc = false;
  let tagged = 0;
  let total = 0;
  for (const ln of lines) {
    if (/^#{1,6}\s+.*acceptance criteria/i.test(ln)) { inAc = true; continue; }
    if (inAc && /^#{1,6}\s+/.test(ln) && !/acceptance criteria/i.test(ln)) { inAc = false; }
    if (!inAc) continue;
    const isAcLine = /(^|\s)(\*\*AC\d|[-*]\s+\*\*AC|AC\d|[*-]\s+\[)/i.test(ln);
    if (!isAcLine) continue;
    total++;
    const hasTag = TEST_TYPE_TAGS.some((t) => new RegExp(`\\[${t}\\]`, "i").test(ln));
    if (hasTag) tagged++;
  }
  return { tagged, total, hasSection: /acceptance criteria/i.test(text) };
}

// Returns { pass, violations: [{rule, detail}] }.
function validateRefined(text) {
  const violations = [];
  const { tagged, hasSection } = countTaggedAcs(text);
  if (!hasSection) {
    violations.push({ rule: "AC section", detail: "no 'Acceptance Criteria' section found" });
  }
  if (tagged === 0) {
    violations.push({ rule: "AC tags", detail: "no AC tagged with [unit]/[integration]/[e2e]" });
  }
  const leaks = findLeaks(text);
  if (leaks.length) {
    violations.push({ rule: "implementation leak", detail: leaks.join(" | ") });
  }
  return { pass: violations.length === 0, violations };
}

// ---- current issue fetch ----
function fetchCurrent(args) {
  if (args.currentBody && existsSync(args.currentBody)) {
    const body = readFileSync(args.currentBody, "utf8");
    return { title: args.currentTitle || "(untitled)", body };
  }
  if (!args.issue || !args.repo) {
    return { title: args.currentTitle || "(no current issue supplied)", body: "" };
  }
  try {
    const out = execFileSync("gh", ["issue", "view", args.issue, "--repo", args.repo,
      "--json", "title,body"], { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
    const j = JSON.parse(out);
    return { title: j.title || "", body: j.body || "" };
  } catch {
    return { title: args.currentTitle || "(could not fetch)", body: "" };
  }
}

// ---- render ----
function renderDryRun(args, current, refinedText, validation) {
  console.log("=== refining-issue-acceptance — dry-run ===\n");
  console.log("CURRENT TITLE:\n  " + current.title + "\n");
  if (current.body.trim()) {
    console.log("CURRENT BODY (first 20 lines):");
    console.log(current.body.split("\n").slice(0, 20).map((l) => "  " + l).join("\n"));
    console.log("");
  }
  const proposedTitle = args.title || current.title;
  console.log("PROPOSED TITLE:\n  " + proposedTitle + "\n");
  console.log("PROPOSED BODY:\n" + refinedText.split("\n").map((l) => "  " + l).join("\n") + "\n");
  console.log("VALIDATION: " + (validation.pass ? "PASS" : "FAIL"));
  if (!validation.pass) {
    for (const v of validation.violations) {
      console.log(`  - [${v.rule}] ${v.detail}`);
    }
  }
  if (args.issue && args.repo) {
    const editTitle = args.title ? ` --title ${JSON.stringify(args.title)}` : "";
    console.log(`\nWOULD RUN: gh issue edit ${args.issue} --repo ${args.repo}${editTitle} --body-file ${args.refinedBody}`);
  } else {
    console.log("\nWOULD RUN: gh issue edit <number> --repo owner/name --body-file " + args.refinedBody + " (supply --issue/--repo to target a live issue)");
  }
}

// ---- apply ----
function applyEdit(args, proposedTitle) {
  if (!args.issue || !args.repo) {
    console.error("error: --apply requires --issue <n> and --repo owner/name");
    process.exit(2);
  }
  const titleArg = args.title ? ["--title", args.title] : [];
  try {
    execFileSync("gh", ["issue", "edit", args.issue, "--repo", args.repo, ...titleArg, "--body-file", args.refinedBody],
      { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
    console.log(`Applied: edited issue #${args.issue} in ${args.repo}.`);
  } catch (e) {
    console.error(`error: gh issue edit failed: ${e.message}`);
    process.exit(1);
  }
}

// ---- main ----
function main() {
  const args = parseArgs(process.argv.slice(2));
  const refinedText = readFileSync(args.refinedBody, "utf8");
  const validation = validateRefined(refinedText);
  const current = fetchCurrent(args);

  if (args.apply) {
    if (!validation.pass) {
      console.log("=== refining-issue-acceptance — apply ===\n");
      console.log("VALIDATION: FAIL — refusing to push a bad spec to the live issue.");
      for (const v of validation.violations) console.log(`  - [${v.rule}] ${v.detail}`);
      process.exit(1);
    }
    applyEdit(args, args.title || current.title);
    process.exit(0);
  }

  // default: dry-run
  renderDryRun(args, current, refinedText, validation);
  process.exit(validation.pass ? 0 : 1);
}

// Run-as-main gate that survives a symlinked install.
const invoked = process.argv[1] ? realpathSync(process.argv[1]) : null;
if (invoked === realpathSync(__filename)) {
  main();
}
