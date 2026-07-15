#!/usr/bin/env node
// verify.mjs — offline, self-contained evaluator for refining-issue-acceptance.
//
// Runs the bundled refine-issue.mjs in --dry-run against two fixtures:
//   1. a GOOD refined body (behavioral ACs, tagged)  -> must exit 0, VALIDATION: PASS
//   2. a BAD  refined body (file/function leaks)      -> must exit non-zero, VALIDATION: FAIL
// A test-type tag set must appear, and every tagged AC must use an observable
// verb (behavioral, not vague). Exits 0 only when both assertions hold.

import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SCRIPT = resolve(__dirname, "..", "..", "scripts", "refine-issue.mjs");
const GOOD = resolve(__dirname, "refined-body.md");
const BAD = resolve(__dirname, "bad-refined-body.md");
const CURRENT = resolve(__dirname, "sample-issue.md");
const CURRENT_TITLE = "Add guest checkout to the cart";

// Observable-behavior stems: a tagged AC line is "behavioral" if it contains
// any word derived from one of these stems (tense-agnostic). Implementation
// leaks (function/migration/refactor) do not match these stems.
const BEHAVIORAL_STEMS = [
  "reach", "place", "see", "display", "return", "creat", "persist", "emit",
  "reject", "prevent", "redirect", "appear", "receiv", "empti", "surviv",
  "report", "show", "assert", "arriv", "send", "submit", "confirm", "navigat",
  "link", "flag", "valid",
];

function isBehavioral(line) {
  const low = line.toLowerCase();
  return BEHAVIORAL_STEMS.some((s) => new RegExp(`\\b${s}\\w*\\b`).test(low));
}

function runDryRun(bodyFile) {
  try {
    const out = execFileSync("node", [
      SCRIPT,
      "--current-title", CURRENT_TITLE,
      "--current-body", CURRENT,
      "--refined-body", bodyFile,
      "--dry-run",
    ], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
    return { code: 0, out };
  } catch (e) {
    return { code: e.status ?? 1, out: e.stdout || "" };
  }
}

let failures = 0;
function check(cond, msg) {
  if (cond) { console.log("  ok   - " + msg); }
  else { console.log("  FAIL - " + msg); failures++; }
}

// ---- 1. GOOD body ----
console.log("[1] GOOD refined body should PASS and be behavioral/verifiable");
const good = runDryRun(GOOD);
check(good.code === 0, `script exited 0 (got ${good.code})`);
check(/VALIDATION:\s*PASS/i.test(good.out), "validation reports PASS");
for (const tag of ["[unit]", "[integration]", "[e2e]"]) {
  check(good.out.includes(tag), `proposed AC set includes tag ${tag}`);
}
const goodAllLines = good.out.split("\n");
const goodBlocks = [];
let cur = null;
for (const l of goodAllLines) {
  if (/\[(unit|integration|e2e)\]/i.test(l)) { if (cur) goodBlocks.push(cur); cur = l; }
  else if (cur !== null) cur += " " + l;
}
if (cur) goodBlocks.push(cur);
check(goodBlocks.length >= 3, `found ${goodBlocks.length} tagged AC blocks (>=3)`);
const behavioral = goodBlocks.filter((b) => isBehavioral(b));
check(behavioral.length === goodBlocks.length,
  `every tagged AC uses an observable verb (${behavioral.length}/${goodBlocks.length})`);

// ---- 2. BAD body ----
console.log("[2] BAD refined body (file/function leak) should FAIL");
const bad = runDryRun(BAD);
check(bad.code !== 0, `script exited non-zero (got ${bad.code})`);
check(/VALIDATION:\s*FAIL/i.test(bad.out), "validation reports FAIL");
check(/implementation leak/i.test(bad.out), "reports an implementation-leak violation");

console.log("");
if (failures) {
  console.log(`EVAL FAILED: ${failures} assertion(s) failed.`);
  process.exit(1);
}
console.log("EVAL PASSED: refined-issue-acceptance verifier green.");
process.exit(0);
