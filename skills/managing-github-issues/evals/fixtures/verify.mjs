#!/usr/bin/env node
// verify.mjs — self-checking eval for managing-github-issues.
// Runs the sync script in offline dry-run mode against the sample roadmap and
// asserts the planned-create count is exactly the open items (6), and that
// every planned create carries the roadmap-id:<id> dedup label.
//
// Exit 0 = pass (count correct, labels present). Exit 1 = assertion failed.

import { execFileSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const script = resolve(__dirname, "..", "..", "scripts", "sync-issues.mjs");
const roadmap = resolve(__dirname, "sample-roadmap.md");

const EXPECTED = 6;
const EXPECTED_IDS = ["feat-a", "feat-b", "bug-a", "debt-a", "chore-a", "chore-b"];

let out;
try {
  out = execFileSync("node", [script, "--dry-run", "--offline", "--repo", "test/test", "--roadmap", roadmap], {
    encoding: "utf8", stdio: ["ignore", "pipe", "pipe"],
  });
} catch (e) {
  console.error("FAILED: script errored\n", e.stdout, e.stderr);
  process.exit(1);
}

const summaryMatch = out.match(/(\d+) to create/);
if (!summaryMatch) {
  console.error("FAILED: no 'to create' summary line found in output:\n", out);
  process.exit(1);
}
const count = Number(summaryMatch[1]);
if (count !== EXPECTED) {
  console.error(`FAILED: expected ${EXPECTED} to create, got ${count}`);
  process.exit(1);
}

const missing = EXPECTED_IDS.filter((id) => !out.includes(`roadmap-id:${id}`));
if (missing.length) {
  console.error(`FAILED: missing roadmap-id label for: ${missing.join(", ")}`);
  process.exit(1);
}

// Done/Skipped rows must NOT appear.
if (out.includes("done-old") || out.includes("skip-x")) {
  console.error("FAILED: a Done/Skipped row was enumerated as a planned create.");
  process.exit(1);
}

console.log(`PASS: ${count} planned creates, all carry roadmap-id:<id>, Done/Skipped excluded.`);
process.exit(0);
