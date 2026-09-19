#!/usr/bin/env node
// verify.mjs — eval-manifest / fixture schema validator (Layer 1 pre-commit).
//
// Validates every skills/*/evals/evals.json against the eval-manifest schema
// and checks that each eval's files[] entry resolves on disk. This is the
// fixture half of the hermetic pre-commit gate (the skill-structure half is
// validate_skill.py); it is filesystem-only — no network, no model.
//
// Exit 0 = every manifest is schema-valid and all files[] resolve.
// Exit 1 = at least one error (printed).
//
// DO NOT add network or live-agent checks here: Layer 1 must stay hermetic
// and fast (~14s for the whole gate).

import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, "..");
const skillsRoot = join(repoRoot, "skills");

const TIERS = new Set(["free", "go", "zen"]);
// RM-003 pass 4: JS mirror of query_runs.py's CORE_SKILLS (the canonical
// source). Kept in step with the Python list; the six core skills must carry
// a `"core": true` marker on their default eval.
const CORE_SKILLS = new Set([
  "authoring-skills",
  "designing-architecture",
  "implementing-features",
  "reviewing-code",
  "triaging-requirements",
  "writing-unit-tests",
]);
const errors = [];
const warnings = [];

function isPlainObject(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

function validateManifest(skill, manifestPath, data) {
  const label = `skills/${skill}/evals/evals.json`;
  if (!isPlainObject(data)) {
    errors.push(`${label}: top level must be a JSON object`);
    return;
  }
  if (data.default_model_tier !== undefined) {
    if (typeof data.default_model_tier !== "string" || !TIERS.has(data.default_model_tier)) {
      errors.push(`${label}: default_model_tier must be one of free|go|zen`);
    }
  }
  if (!Array.isArray(data.evals)) {
    errors.push(`${label}: 'evals' must be an array`);
    return;
  }
  const defaultIdx = [];
  const coreIdx = [];
  data.evals.forEach((e, i) => {
    const where = `${label}: evals[${i}]`;
    if (!isPlainObject(e)) {
      errors.push(`${where} must be an object`);
      return;
    }
    if (e.id === undefined || (typeof e.id !== "number" && typeof e.id !== "string")) {
      errors.push(`${where}: 'id' must be a number or string`);
    }
    if (typeof e.prompt !== "string" || e.prompt.trim() === "") {
      errors.push(`${where}: 'prompt' must be a non-empty string`);
    }
    if (!Array.isArray(e.expected_behavior) || e.expected_behavior.length === 0 ||
        e.expected_behavior.some((b) => typeof b !== "string" || b.trim() === "")) {
      errors.push(`${where}: 'expected_behavior' must be a non-empty array of non-empty strings`);
    }
    if (e.deferred !== undefined && typeof e.deferred !== "boolean") {
      errors.push(`${where}: 'deferred' must be a boolean`);
    }
    if (e.default !== undefined) {
      if (typeof e.default !== "boolean") {
        errors.push(`${where}: 'default' must be a boolean`);
      } else if (e.default) {
        defaultIdx.push(i);
      }
    }
    if (e.core !== undefined) {
      if (typeof e.core !== "boolean") {
        errors.push(`${where}: 'core' must be a boolean`);
      } else if (e.core) {
        coreIdx.push(i);
      }
    }
    if (e.default_model_tier !== undefined &&
        (typeof e.default_model_tier !== "string" || !TIERS.has(e.default_model_tier))) {
      errors.push(`${where}: default_model_tier must be one of free|go|zen`);
    }
    if (e.files !== undefined) {
      if (!Array.isArray(e.files) || e.files.some((f) => typeof f !== "string")) {
        errors.push(`${where}: 'files' must be an array of strings`);
      } else {
        for (const rel of e.files) {
          const target = resolve(join(repoRoot, "skills", skill, "evals"), rel);
          if (!existsSync(target)) {
            errors.push(`${where}: files[] entry does not resolve: ${rel}`);
          }
        }
      }
    }
  });
  if (defaultIdx.length > 1) {
    errors.push(`${label}: ${defaultIdx.length} evals marked 'default': true (max one)`);
  }
  if (coreIdx.length > 1) {
    errors.push(`${label}: ${coreIdx.length} evals marked 'core': true (max one)`);
  }
  for (const i of coreIdx) {
    if (i !== 0 && !defaultIdx.includes(i)) {
      errors.push(`${label}: evals[${i}] is 'core': true but is not the ` +
        `'default' or first eval in file order`);
    }
  }
  if (CORE_SKILLS.has(skill) && coreIdx.length === 0) {
    errors.push(`${label}: core skill '${skill}' must carry 'core': true on its default eval`);
  }
}

function main() {
  const skillsDir = skillsRoot;
  if (!existsSync(skillsDir)) {
    console.error(`FAIL: skills root not found: ${skillsDir}`);
    process.exit(1);
  }

  let manifests = 0;
  for (const skill of readdirSync(skillsDir).sort()) {
    const manifestPath = join(skillsDir, skill, "evals", "evals.json");
    if (!existsSync(manifestPath)) {
      // validate_skill.py owns the "evals are mandatory" rule.
      continue;
    }
    manifests += 1;
    let data;
    try {
      data = JSON.parse(readFileSync(manifestPath, "utf8"));
    } catch (e) {
      errors.push(`skills/${skill}/evals/evals.json: invalid JSON (${e.message})`);
      continue;
    }
    validateManifest(skill, manifestPath, data);
  }

  for (const w of warnings) console.warn(`warn:  ${w}`);
  if (errors.length) {
    console.error(`FAIL: ${errors.length} fixture-schema error(s) across ${manifests} manifests`);
    for (const e of errors) console.error(`      error: ${e}`);
    process.exit(1);
  }
  console.log(`PASS: ${manifests} eval manifests schema-valid, all files[] entries resolve.`);
  process.exit(0);
}

main();
