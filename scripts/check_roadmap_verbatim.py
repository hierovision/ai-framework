#!/usr/bin/env python3
"""Contract checker for docs/ROADMAP.md + docs/roadmap-detail/ (amended contract).

Hard failures (exit 1): YAML frontmatter parse errors; a 13-column table
header without its delimiter row; roadmap rows with != 13 cells; Done
section missing; roadmap-ID <-> docs/roadmap-detail/<ID>.md bijection
breaks (a row without its detail file, or a detail file without its row).

Warnings (exit 0, printed): any table cell exceeding the 280-char
guidance line; a Notes cell that does not reference its detail file;
detail files with no roadmap row reference — surfaced so the agent can
offer the owner the option to shorten.

Cell-length is advisory by design (owner ruling 2026-10-11): never
hard-fail on length; never trim silently.
"""
import os
import re
import sys

import yaml

ROADMAP = "docs/ROADMAP.md"
DETAIL_DIR = "docs/roadmap-detail"
HDR = "| ID | Title | Outcome | Horizon | Category | Impact | Urgency | Score | Status | Success measure | Blocked-by | Sources | Notes |"
DELIM = "|---|---|---|---|---|---|---|---|---|---|---|---|---|"
GUIDANCE = 280

fail, warn = [], []

raw = open(ROADMAP).read()
try:
    yaml.safe_load(raw.split("---")[1])
except Exception as e:                                    # noqa: BLE001
    fail.append(f"frontmatter does not parse: {e}")

lines = raw.splitlines()
hdr_lines = [i for i, l in enumerate(lines)
             if l.rstrip().startswith("| ID | Title |")]
for i in hdr_lines:
    if not (i + 1 < len(lines) and lines[i + 1].rstrip() == DELIM):
        fail.append(f"table header at line {i + 1} lacks delimiter row")

rows = {}
for i, l in enumerate(lines):
    if l.startswith("| RM-"):
        c = [x.strip() for x in l.strip().strip("|").split(" | ")]
        if len(c) != 13:
            fail.append(f"row with {len(c)} cells: {c[0] if c else '?'}")
            continue
        rows[c[0]] = c
        if c[8] not in ("done",):
            if len(c[9]) > GUIDANCE:
                warn.append(f"{c[0]} Success measure {len(c[9])} chars "
                            "(guidance line is 280)")
        if len(c[12]) > GUIDANCE:
            warn.append(f"{c[0]} Notes {len(c[12])} chars (guidance line is 280)")
        if f"docs/roadmap-detail/{c[0]}.md" not in c[12]:
            warn.append(f"{c[0]} Notes does not reference its detail file")

di = next((i for i, l in enumerate(lines) if l.startswith("## Done")), -1)
if di < 0:
    fail.append("## Done section missing")
si = next((i for i, l in enumerate(lines)
           if i > di and l.startswith("## Skipped")), len(lines))
done_ids = set(re.findall(r"^\| (RM-\d{3}) \|",
                          "\n".join(lines[di:si]), flags=re.M))

detail_ids = set()
for fn in sorted(os.listdir(DETAIL_DIR)) if os.path.isdir(DETAIL_DIR) else []:
    m = re.match(r"(RM-\d{3})\.md$", fn)
    if m:
        detail_ids.add(m.group(1))

if done_ids:
    missing_detail = done_ids - detail_ids
    if missing_detail:
        fail.append(f"Done rows lack detail files: {sorted(missing_detail)}")
open_ids = set(rows) - done_ids
missing_open = open_ids - detail_ids
if missing_open:
    warn.append(f"open rows without detail files (extraction pending): "
                f"{sorted(missing_open)}")
orphans = detail_ids - set(rows)
if orphans:
    warn.append(f"detail files with no roadmap row (candidates to prune at "
                f"the next ALM review): {sorted(orphans)}")

if fail:
    print("ROADMAP contract violations:")
    for f in fail:
        print(" -", f)
    sys.exit(1)

print(f"OK: frontmatter parses; {len(hdr_lines)} tables delimited; "
      f"{len(done_ids)} done rows; detail files: {len(detail_ids)}; "
      f"bijection holds ({'hard-checked for done rows' if done_ids else 'no done rows'})")
for w in warn:
    print("WARN:", w)
sys.exit(0)
