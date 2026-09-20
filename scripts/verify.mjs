#!/usr/bin/env node
// verify.mjs — eval-manifest / fixture schema validator (Layer 1 pre-commit).
//
// Validates every skills/*/evals/evals.json against the eval-manifest schema
// and checks that each eval's files[] entry resolves on disk. This is the
// fixture half of the hermetic pre-commit gate (the skill-structure half is
// validate_skill.py); it is filesystem-only — no network, no model.
//
// RM-003 pass 5 adds the closed typed-assertion schema: an `expect` block is
// an object with >=1 non-empty action/artifact/text entry (unknown keys
// rejected); an eval carrying a `default`/`core` marker must carry `expect`;
// `expected_behavior` is required only when `expect` is absent. This JS mirror
// is kept in step with scripts/check_typed_evals.py (the Python source of
// truth) because Layer 1 must stay hermetic (no Python import).
//
// Exit 0 = every manifest is schema-valid and all files[] resolve.
// Exit 1 = at least one error (printed).
//
// DO NOT add network or live-agent checks here: Layer 1 must stay hermetic
// and fast (~14s for the whole gate).
//
// Usage: node scripts/verify.mjs [--skills-root <path>]

import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, "..");
const defaultSkillsRoot = join(repoRoot, "skills");

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

// RM-003 pass 5: closed typed-assertion taxonomy (mirror of
// scripts/check_typed_evals.py).
const ALLOWED_EXPECT = new Set(["action", "artifact", "text"]);
const ALLOWED_ACTION = new Set(["tool", "args"]);
const ALLOWED_ARTIFACT = new Set(["path", "phrases"]);

const errors = [];
const warnings = [];

function isPlainObject(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

function isNonEmptyStr(v) {
  return typeof v === "string" && v.trim() !== "";
}

// Closed-shape validation for one `expect` block; returns an array of errors.
function validateExpect(expect, where) {
  const errs = [];
  for (const k of Object.keys(expect)) {
    if (!ALLOWED_EXPECT.has(k)) errs.push(`${where} has unknown key(s): ${k}`);
  }
  const present = [...ALLOWED_EXPECT].filter((k) => k in expect);
  if (present.length === 0) {
    errs.push(`${where} must contain at least one of action/artifact/text`);
  }
  for (const key of present) {
    const value = expect[key];
    if (!Array.isArray(value) || value.length === 0) {
      errs.push(`${where}.${key} must be a non-empty array`);
      continue;
    }
    if (key === "text") {
      value.forEach((item, i) => {
        if (!isNonEmptyStr(item)) errs.push(`${where}.text[${i}] must be a non-empty string`);
      });
    } else if (key === "action") {
      value.forEach((item, i) => {
        if (!isPlainObject(item)) {
          errs.push(`${where}.action[${i}] must be an object`);
          return;
        }
        for (const k of Object.keys(item)) {
          if (!ALLOWED_ACTION.has(k)) errs.push(`${where}.action[${i}] has unknown key(s): ${k}`);
        }
        if (!isNonEmptyStr(item.tool)) errs.push(`${where}.action[${i}].tool must be a non-empty string`);
        const a = item.args === undefined ? {} : item.args;
        if (!isPlainObject(a)) {
          errs.push(`${where}.action[${i}].args must be an object`);
        } else {
          for (const [ak, av] of Object.entries(a)) {
            if (!isNonEmptyStr(av)) {
              errs.push(`${where}.action[${i}].args['${ak}'] must be a non-empty glob string`);
            }
          }
        }
      });
    } else if (key === "artifact") {
      value.forEach((item, i) => {
        if (!isPlainObject(item)) {
          errs.push(`${where}.artifact[${i}] must be an object`);
          return;
        }
        for (const k of Object.keys(item)) {
          if (!ALLOWED_ARTIFACT.has(k)) errs.push(`${where}.artifact[${i}] has unknown key(s): ${k}`);
        }
        if (!isNonEmptyStr(item.path)) errs.push(`${where}.artifact[${i}].path must be a non-empty string`);
        if (!Array.isArray(item.phrases) || item.phrases.length === 0
            || item.phrases.some((p) => !isNonEmptyStr(p))) {
          errs.push(`${where}.artifact[${i}].phrases must be a non-empty array of non-empty strings`);
        }
      });
    }
  }
  return errs;
}

function hasExpect(e) {
  return isPlainObject(e.expect) && Object.keys(e.expect).length > 0;
}

function validateManifest(skill, manifestPath, data, evalsDir) {
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
    if (e.expect !== undefined) {
      if (!isPlainObject(e.expect)) {
        errors.push(`${where}: 'expect' must be an object`);
      } else {
        for (const err of validateExpect(e.expect, `${where}.expect`)) errors.push(err);
      }
    }
    if (e.expected_behavior === undefined) {
      if (!hasExpect(e)) {
        errors.push(`${where}: 'expected_behavior' is required when 'expect' is absent ` +
          `(must be a non-empty array of non-empty strings)`);
      }
    } else if (!Array.isArray(e.expected_behavior)
        || e.expected_behavior.some((b) => !isNonEmptyStr(b))) {
      errors.push(`${where}: 'expected_behavior' must be an array of non-empty strings`);
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
    if ((e.default === true || e.core === true) && !hasExpect(e)) {
      errors.push(`${where}: carries a default/core marker without a typed ` +
        `'expect' block (AC12/AC17)`);
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
          const target = resolve(evalsDir, rel);
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
  const argv = process.argv.slice(2);
  let skillsDir = defaultSkillsRoot;
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--skills-root" && argv[i + 1]) {
      skillsDir = resolve(argv[i + 1]);
      i += 1;
    }
  }

  if (!existsSync(skillsDir)) {
    console.error(`FAIL: skills root not found: ${skillsDir}`);
    process.exit(1);
  }

  let manifests = 0;
  for (const skill of readdirSync(skillsDir).sort()) {
    const evalsDir = join(skillsDir, skill, "evals");
    const manifestPath = join(evalsDir, "evals.json");
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
    validateManifest(skill, manifestPath, data, evalsDir);
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
