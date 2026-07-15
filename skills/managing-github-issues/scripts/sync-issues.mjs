#!/usr/bin/env node
// sync-issues.mjs — persist an established ROADMAP.md as GitHub issues.
//
// Two-way, idempotent sync:
//   - one GitHub issue per OPEN roadmap row (Features / Bugs / Tech Debt / Chores)
//   - each issue tagged `roadmap-id:<id>` (+ a category label) for dedup
//   - issue bodies enriched from the row's `Sources` files
//   - issue numbers written back into the row's `Sources` cell (owner/repo#n)
//   - once every open row is backed, enumerates (and can archive) the now
//     redundant legacy docs named in the roadmap `sources:` frontmatter.
//
// Default is --dry-run (safe, no side effects). A real run requires --apply.
// The run-as-main gate survives a symlinked install (realpath'd argv[1]).

import { readFileSync, writeFileSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { realpathSync } from "node:fs";
import { dirname, resolve, join, basename, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";

const __filename = fileURLToPath(import.meta.url);

const CATEGORY_LABEL = { feature: "enhancement", bug: "bug", debt: "tech-debt", chore: "chore" };

// ---- args ----
function parseArgs(argv) {
  const a = { dryRun: false, apply: false, offline: false, checkCleanup: false, applyCleanup: false, repo: null, roadmap: null, withProject: false, project: null, projectTitle: null };
  for (let i = 0; i < argv.length; i++) {
    const t = argv[i];
    if (t === "--dry-run") a.dryRun = true;
    else if (t === "--apply") a.apply = true;
    else if (t === "--offline") a.offline = true;
    else if (t === "--check-cleanup") a.checkCleanup = true;
    else if (t === "--apply-cleanup") a.applyCleanup = true;
    else if (t === "--repo") a.repo = argv[++i];
    else if (t === "--roadmap") a.roadmap = argv[++i];
    else if (t === "--with-project") a.withProject = true;
    else if (t === "--project") a.project = argv[++i];
    else if (t === "--project-title") a.projectTitle = argv[++i];
    else if (t === "--help" || t === "-h") {
      console.log("Usage: node sync-issues.mjs --roadmap <path> [--dry-run|--apply] [--repo owner/name] [--offline] [--with-project] [--project <number>] [--project-title <title>] [--check-cleanup|--apply-cleanup]");
      process.exit(0);
    }
  }
  if (!a.roadmap) { console.error("error: --roadmap <path> is required"); process.exit(2); }
  if (!existsSync(a.roadmap)) { console.error(`error: roadmap not found: ${a.roadmap}`); process.exit(2); }
  // Default-safe: if neither --apply nor --dry-run is given, dry-run.
  if (!a.apply && !a.dryRun) a.dryRun = true;
  return a;
}

// ---- frontmatter ----
function splitFrontmatter(text) {
  const m = text.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
  if (!m) return { fm: "", body: text };
  return { fm: m[1], body: m[2] };
}

function parseSourcesFrontmatter(fm) {
  // Minimal YAML list parse for the `sources:` block.
  const lines = fm.split("\n");
  const out = [];
  let inSources = false;
  for (const ln of lines) {
    if (/^sources:\s*$/.test(ln)) { inSources = true; continue; }
    if (inSources) {
      const mm = ln.match(/^\s*-\s+(.+?)\s*$/);
      if (mm) out.push(mm[1]);
      else if (ln.trim() === "" || /^\S/.test(ln)) inSources = false; // next top-level key
    }
  }
  return out;
}

// ---- roadmap parse ----
export function parseRoadmap(body) {
  const lines = body.split("\n");
  const items = [];
  let headerCols = null; // column index map when inside an open table
  let inOpenTable = false;

  for (const ln of lines) {
    if (!ln.startsWith("|")) { inOpenTable = false; headerCols = null; continue; }
    const cells = ln.split("|").slice(1, -1).map((c) => c.trim());
    if (cells.length && cells[0].toLowerCase() === "id" && cells.includes("Status") && cells.includes("Sources") && cells.includes("Score")) {
      headerCols = {};
      cells.forEach((c, i) => { headerCols[c.toLowerCase()] = i; });
      inOpenTable = true;
      continue;
    }
    if (inOpenTable && cells.length && cells.every((c) => c === "" || /^-+$/.test(c))) {
      // separator row like |---|---|
      continue;
    }
    if (inOpenTable && cells.length > 1) {
      const get = (name) => (headerCols[name] != null ? (cells[headerCols[name]] || "").trim() : "");
      const id = get("id");
      if (!id) continue;
      items.push({
        id,
        title: get("title"),
        category: get("category"),
        impact: get("impact"),
        urgency: get("urgency"),
        score: get("score"),
        status: get("status"),
        sourcesRaw: get("sources"),
        notes: get("notes"),
      });
    }
  }
  return items;
}

export function findSourceFiles(sourcesRaw) {
  if (!sourcesRaw) return [];
  const files = [];
  const re = /(\S+\.md)/g;
  let mm;
  while ((mm = re.exec(sourcesRaw))) files.push(mm[1]);
  return files;
}

export function findSectionHints(sourcesRaw) {
  if (!sourcesRaw) return [];
  const hints = [];
  const re = /\(([^):]+):/g;
  let mm;
  while ((mm = re.exec(sourcesRaw))) hints.push(mm[1].trim());
  return hints;
}

// ---- body enrichment ----
export function extractChecklist(item, roadmapDir) {
  const files = findSourceFiles(item.sourcesRaw);
  const hints = findSectionHints(item.sourcesRaw).map((h) => h.toLowerCase());
  const bullets = [];

  for (const f of files) {
    const p = resolve(roadmapDir, f);
    if (!p.startsWith(resolve(roadmapDir) + sep)) continue; // containment guard
    if (!existsSync(p)) continue;
    const text = readFileSync(p, "utf8");
    const secs = text.split(/^(#{1,6})\s+(.+)$/m).slice(1); // [level, title, content, level, title, content, ...]
    for (let i = 0; i < secs.length; i += 3) {
      const title = (secs[i + 1] || "").trim().toLowerCase();
      const content = secs[i + 2] || "";
      const matched = hints.some((h) => title.includes(h)) || title.includes(item.id.toLowerCase());
      if (!matched) continue;
      for (const line of content.split("\n")) {
        const b = line.match(/^\s*[-*]\s+(.+)$/);
        if (b) bullets.push(b[1].trim());
      }
    }
  }
  return bullets;
}

export function buildBody(item, roadmapDir) {
  const checklist = extractChecklist(item, roadmapDir);
  const lines = [];
  lines.push(`## ${item.title}`);
  lines.push("");
  lines.push(`**Roadmap ID:** \`${item.id}\``);
  lines.push(`**Category:** ${item.category}`);
  lines.push(`**Score:** ${item.impact || "?"}×${item.urgency || "?"} = ${item.score || "?"}  (status: ${item.status || "open"})`);
  if (item.notes) lines.push(`**Notes:** ${item.notes}`);
  lines.push("");
  lines.push("### Acceptance / source checklist");
  if (checklist.length) {
    for (const b of checklist) lines.push(`- [ ] ${b}`);
  } else {
    lines.push("_No source checklist extracted._");
  }
  lines.push("");
  lines.push("> Synced from ROADMAP.md via the `managing-github-issues` skill.");
  return lines.join("\n");
}

// ---- safe gh runner with rate-limit backoff ----
// Every `gh` call goes through runGh so rate-limit / transient transport
// errors are retried with exponential backoff instead of failing silently
// (a silent failure would otherwise skip dedup checks or create duplicates).
function sleep(ms) { const end = Date.now() + ms; while (Date.now() < end) {} }

function runGh(args, cwd) {
  let lastErr;
  for (let attempt = 0; attempt < 4; attempt++) {
    try {
      return execFileSync("gh", args, { encoding: "utf8", cwd, stdio: ["ignore", "pipe", "ignore"] });
    } catch (e) {
      lastErr = e;
      const msg = (e.stderr || e.message || "").toString();
      const rateLimited = /rate limit|HTTP 403|secondary rate|abuse limit|please wait/i.test(msg);
      if (rateLimited && attempt < 3) {
        const delay = 2000 * Math.pow(2, attempt);
        console.error(`  (rate limited; retrying in ${delay}ms)`);
        sleep(delay);
        continue;
      }
      throw e;
    }
  }
  throw lastErr;
}

function runGhSafe(args, cwd) {
  try { return runGh(args, cwd); } catch { return null; }
}

// ---- repo resolution ----
function inferRepo(roadmapDir) {
  const out = runGhSafe(["repo", "view", "--json", "nameWithOwner"], roadmapDir);
  if (!out) return null;
  try { return JSON.parse(out).nameWithOwner; } catch { return null; }
}

export function isBacked(item, repo) {
  // Idempotency: a row is "backed" once its Sources cell carries owner/repo#n.
  // This is the written-back signal from a prior run and works offline.
  const re = new RegExp(`${repo.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}#\\d+`);
  return re.test(item.sourcesRaw || "");
}

// One batched call: list all issues and index those carrying a `roadmap-id:`
// label. Far cheaper than one API call per open row. For repos with more than
// 1000 issues this single page may truncate; roadmap backlogs are normally
// far smaller, and the write-back idempotency signal covers the rest.
function existingIssueMap(repo) {
  const out = runGhSafe(["issue", "list", "--repo", repo, "--state", "all", "--limit", "1000", "--json", "number,labels"]);
  const map = new Map();
  if (!out) return map;
  let arr;
  try { arr = JSON.parse(out); } catch { return map; }
  if (!Array.isArray(arr)) return map;
  for (const it of arr) {
    for (const l of (it.labels || [])) {
      const name = typeof l === "string" ? l : (l && l.name);
      const m = /^roadmap-id:(.+)$/.exec(name || "");
      if (m) { map.set(m[1], it.number); break; }
    }
  }
  return map;
}

// ---- gh command builder ----
const _tmpFiles = [];
function issueBodyFile(item, body) {
  const tmp = join(tmpdir(), `mgh-issue-${item.id}-${process.pid}.md`);
  writeFileSync(tmp, body, "utf8");
  _tmpFiles.push(tmp);
  return tmp;
}
function cleanupTmp() {
  for (const f of _tmpFiles) { try { rmSync(f); } catch { /* ignore */ } }
}

// ---- label provisioning (idempotent; applies only on --apply) ----
// GitHub rejects `gh issue create` for labels that don't exist yet, so we
// ensure every label we intend to use is present before issuing.
const LABEL_COLORS = {
  enhancement: "a2eeef",
  bug: "d73a4a",
  "tech-debt": "bfd4f2",
  chore: "c5def5",
  "roadmap-id": "ededed",
};
function existingLabelNames(repo) {
  const out = runGhSafe(["label", "list", "--repo", repo, "--limit", "200", "--json", "name"]);
  if (!out) return new Set();
  try { return new Set(JSON.parse(out).map((l) => l.name)); } catch { return new Set(); }
}
function ensureLabel(repo, name, color, description, existing) {
  if (existing.has(name)) return;
  try {
    runGh(["label", "create", name, "--repo", repo, "--color", color, "--description", description]);
    console.log(`  + created label "${name}"`);
  } catch (e) {
    console.error(`  WARN could not create label "${name}": ${e.message}`);
  }
}
function ensureAllLabels(repo, items) {
  const existing = existingLabelNames(repo);
  const seen = new Set();
  for (const it of items) {
    const cat = CATEGORY_LABEL[it.category] || it.category;
    if (!seen.has(cat)) { seen.add(cat); ensureLabel(repo, cat, LABEL_COLORS[cat] || "ededed", `Roadmap category: ${cat}`, existing); }
    const rid = `roadmap-id:${it.id}`;
    if (!seen.has(rid)) { seen.add(rid); ensureLabel(repo, rid, LABEL_COLORS["roadmap-id"], `Roadmap item ${it.id}`, existing); }
  }
}

// ---- GitHub Project (V2) ranking ----
// Plain issues have no priority/rank field; a Project holds a `Priority`
// single-select so the roadmap's score buckets are sortable in GitHub.
const PROJECT_TITLE_SUFFIX = " Roadmap";
export function priorityForScore(score) {
  const s = Number(score) || 0;
  if (s >= 6) return "High";
  if (s >= 3) return "Medium";
  return "Low";
}
function ghJson(args, cwd) {
  return JSON.parse(runGh(args, cwd));
}
function ensureProject(owner, title) {
  const list = ghJson(["project", "list", "--owner", owner, "--format", "json"]);
  const found = (list || []).find((p) => p.title === title);
  if (found) return found.number;
  const created = ghJson(["project", "create", "--owner", owner, "--title", title, "--format", "json"]);
  return created.number;
}
function projectNodeId(owner, number) {
  return ghJson(["project", "view", number, "--owner", owner, "--format", "json"]).id;
}
function ensurePriorityField(owner, number) {
  const fl = ghJson(["project", "field-list", number, "--owner", owner, "--format", "json"]);
  let f = (fl.fields || []).find((x) => x.name === "Priority" && x.type === "ProjectV2SingleSelectField");
  if (!f) {
    f = ghJson(["project", "field-create", number, "--owner", owner, "--name", "Priority",
      "--data-type", "SINGLE_SELECT", "--single-select-options", "High,Medium,Low", "--format", "json"]);
  }
  const options = {};
  for (const o of (f.options || [])) options[o.name] = o.id;
  return { fieldId: f.id, options };
}
function projectItems(owner, number) {
  // number -> item node id, for idempotent add/edit
  const out = ghJson(["project", "item-list", number, "--owner", owner, "--format", "json"]);
  const map = new Map();
  for (const it of (out.items || [])) {
    if (it.content && it.content.number) map.set(it.content.number, it.id);
  }
  return map;
}
function issueNumberOf(item) {
  const m = (item.sourcesRaw || "").match(/#(\d+)/);
  return m ? Number(m[1]) : null;
}
function addIssueToProject(owner, number, issueUrl) {
  return ghJson(["project", "item-add", number, "--owner", owner, "--url", issueUrl, "--format", "json"]).id;
}
function setItemPriority(projectId, itemId, fieldId, optionId) {
  execFileSync("gh", ["project", "item-edit", "--id", itemId, "--field-id", fieldId,
    "--project-id", projectId, "--single-select-option-id", optionId, "--format", "json"],
    { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
}
function runProjectRanking(repo, items, projectNumber, projectTitle) {
  const [owner, repoName] = repo.split("/");
  const title = projectTitle || `${repoName}${PROJECT_TITLE_SUFFIX}`;
  const pnum = projectNumber || ensureProject(owner, title);
  const pnode = projectNodeId(owner, pnum);
  const { fieldId, options } = ensurePriorityField(owner, pnum);
  const inProject = projectItems(owner, pnum);
  console.log(`\nRanking in Project #${pnum} "${title}" (priority from score buckets):`);
  let added = 0, updated = 0;
  for (const it of items) {
    const n = issueNumberOf(it);
    if (!n) { console.log(`  skip ${it.id}: no issue number in Sources`); continue; }
    const pr = priorityForScore(it.score);
    const optId = options[pr];
    if (!optId) { console.log(`  skip ${it.id}: unknown priority "${pr}"`); continue; }
    let itemId = inProject.get(n);
    if (!itemId) { itemId = addIssueToProject(owner, pnum, `https://github.com/${repo}/issues/${n}`); added++; }
    setItemPriority(pnode, itemId, fieldId, optId);
    updated++;
    console.log(`  #${n} (${it.id}) -> ${pr}`);
  }
  console.log(`Project ranking done: ${added} added, ${updated} priority-set.`);
}

function issueCreateCommand(item, repo, body) {
  const cat = CATEGORY_LABEL[item.category] || item.category;
  const labels = [`roadmap-id:${item.id}`, cat].filter(Boolean).join(",");
  const tmp = issueBodyFile(item, body);
  return `gh issue create --repo ${repo} --title ${JSON.stringify(item.title)} --label ${JSON.stringify(labels)} --body-file ${tmp}`;
}

// ---- write-back (header-driven, robust to column reordering) ----
// Locate the Sources column of the open table by reading its header row, so
// the writer matches the header-driven parser instead of a hard-coded index.
export function findOpenTableSourcesCol(text) {
  for (const ln of text.split("\n")) {
    if (!ln.startsWith("|")) continue;
    const cells = ln.split("|").slice(1, -1).map((c) => c.trim());
    const isOpenHeader = cells[0] && cells[0].toLowerCase() === "id"
      && cells.includes("Status") && cells.includes("Sources") && cells.includes("Score");
    if (isOpenHeader) return cells.indexOf("Sources");
  }
  return -1;
}

function writeBackRef(roadmapPath, id, repoRef) {
  const text = readFileSync(roadmapPath, "utf8");
  const idx = findOpenTableSourcesCol(text);
  if (idx < 0) {
    console.error(`  WARN could not locate the open-table Sources column; skipping write-back for ${id}`);
    return;
  }
  const out = text.split("\n").map((ln) => {
    if (!ln.startsWith("|")) return ln;
    const cells = ln.split("|").slice(1, -1).map((c) => c.trim());
    if (cells[0] !== id) return ln;
    if (cells[idx] == null) return ln;
    if (cells[idx].includes(repoRef)) return ln;
    const newCell = cells[idx] ? `${cells[idx]}; ${repoRef}` : repoRef;
    cells[idx] = newCell;
    return `| ${cells.join(" | ")} |`;
  });
  writeFileSync(roadmapPath, out.join("\n"), "utf8");
}

// ---- cleanup ----
function archivePathFor(repoDir, src) {
  return join(repoDir, "archive", "roadmap-source", src);
}

function planCleanup(args, repo, items) {
  const roadmapDir = dirname(resolve(args.roadmap));
  const sources = parseSourcesFrontmatter(splitFrontmatter(readFileSync(args.roadmap, "utf8")).fm);
  const unbacked = items.filter((it) => !isBacked(it, repo)).map((it) => it.id);
  return { roadmapDir, sources, unbacked };
}

function doApplyCleanup(roadmapDir, sources) {
  const archiveRoot = join(roadmapDir, "archive", "roadmap-source");
  for (const src of sources) {
    const from = resolve(roadmapDir, src);
    if (!from.startsWith(resolve(roadmapDir) + sep)) continue; // containment guard
    if (!existsSync(from)) { console.log(`  skip (missing): ${src}`); continue; }
    const to = resolve(roadmapDir, archivePathFor(roadmapDir, src));
    mkdirSync(dirname(to), { recursive: true });
    try {
      execFileSync("git", ["mv", from, to], { cwd: roadmapDir, stdio: ["ignore", "pipe", "ignore"] });
      console.log(`  git mv ${src} -> ${relative(roadmapDir, to)}`);
    } catch {
      // fall back to a plain move if not a git repo
      execFileSync("mv", [from, to], { stdio: ["ignore", "pipe", "ignore"] });
      console.log(`  mv ${src} -> ${relative(roadmapDir, to)} (no git)`);
    }
  }
}

// ---- main ----
function main() {
  const args = parseArgs(process.argv.slice(2));
  const roadmapDir = dirname(resolve(args.roadmap));
  const { fm, body } = splitFrontmatter(readFileSync(args.roadmap, "utf8"));
  const items = parseRoadmap(body);
  const sources = parseSourcesFrontmatter(fm);

  const repo = args.repo || (args.offline ? null : inferRepo(roadmapDir));
  if (!repo) {
    console.error("error: could not resolve repo. Pass --repo owner/name (or run outside --offline with gh authed).");
    process.exit(2);
  }

  // Cleanup subcommands short-circuit the sync.
  if (args.checkCleanup || args.applyCleanup) {
    const { roadmapDir: rd, sources: srcs, unbacked } = planCleanup(args, repo, items);
    if (unbacked.length) {
      console.log(`Cleanup NOT ready: ${unbacked.length} open row(s) still lack an issue ref:`);
      for (const id of unbacked) console.log(`  - ${id}`);
      console.log("Run a full sync first (every open row must carry owner/repo#n).");
      process.exit(0);
    }
    console.log(`All ${items.length} open rows are backed. Candidate legacy docs (from sources: frontmatter):`);
    for (const s of srcs) console.log(`  - ${s}`);
    if (args.applyCleanup) {
      console.log("Applying archive (git-tracked move into archive/roadmap-source/):");
      doApplyCleanup(rd, srcs);
    } else {
      console.log("PENDING CONFIRMATION: re-run with --apply-cleanup to archive the above (no deletion).");
    }
    cleanupTmp();
    process.exit(0);
  }

  // Sync: enumerate planned creates. Dedup is resolved once in a single
  // batched call, then looked up per row (no per-row API call).
  const issueMap = args.offline ? new Map() : existingIssueMap(repo);
  const toCreate = [];
  const backed = [];
  for (const it of items) {
    if (isBacked(it, repo)) { backed.push(it); continue; }
    const liveN = issueMap.get(it.id) ?? null;
    if (liveN) {
      backed.push(it);
      console.log(`[SKIP] ${it.id} — issue #${liveN} already exists (label roadmap-id:${it.id})`);
      continue;
    }
    toCreate.push(it);
  }

  console.log(`\n=== managing-github-issues sync — repo ${repo} ===`);
  if (args.dryRun) console.log("[DRY-RUN] no issues created; commands shown below are what --apply would run.\n");

  if (!args.dryRun && toCreate.length) {
    console.log("Ensuring labels exist (idempotent):");
    ensureAllLabels(repo, toCreate);
    console.log("");
  }

  for (const it of toCreate) {
    const bodyText = buildBody(it, roadmapDir);
    const cmd = issueCreateCommand(it, repo, bodyText);
    console.log(`[${args.dryRun ? "DRY-RUN" : "CREATE"}] ${it.id} (${it.category}, score ${it.score})`);
    console.log(`  ${cmd}`);
    if (!args.dryRun) {
      const bodyFile = issueBodyFile(it, bodyText);
      try {
        const out = runGh(["issue", "create", "--repo", repo, "--title", it.title,
          "--label", `roadmap-id:${it.id},${CATEGORY_LABEL[it.category] || it.category}`,
          "--body-file", bodyFile]);
        const n = (out.match(/issues\/(\d+)/) || [])[1];
        if (n) {
          const repoRef = `${repo}#${n}`;
          writeBackRef(args.roadmap, it.id, repoRef);
          console.log(`  -> created #${n}; wrote back ${repoRef} to ROADMAP.md`);
        }
      } catch (e) {
        console.error(`  ERROR creating ${it.id}: ${e.message}`);
      }
    }
  }

  console.log(`\nSummary: ${toCreate.length} to create, ${backed.length} already backed, ${items.length - toCreate.length - backed.length} (done/skipped excluded).`);
  if (toCreate.length === 0 && backed.length === items.length) {
    console.log("Roadmap is current. Run --check-cleanup to review redundant source docs.");
  }

  // Ranking via GitHub Project (V2): additive; runs over all open items.
  if (args.withProject) {
    if (args.dryRun) {
      console.log("\n[DRY-RUN] --with-project would ensure a Project, add open issues, and set Priority (High≥6 / Medium 3–5 / Low≤2). No project changes made.");
    } else if (args.offline) {
      console.log("\nSkipping --with-project: requires network (gh authed).");
    } else {
      const allOpen = [...toCreate, ...backed];
      runProjectRanking(repo, allOpen, args.project, args.projectTitle);
    }
  }

  cleanupTmp();
}

// Run-as-main gate that survives a symlinked install.
const invoked = process.argv[1] ? realpathSync(process.argv[1]) : null;
if (invoked === realpathSync(__filename)) {
  main();
}
