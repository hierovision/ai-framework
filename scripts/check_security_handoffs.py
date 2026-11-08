#!/usr/bin/env python3
"""Handoff-brief completeness checker (RM-076 P3-5).

    python3 scripts/check_security_handoffs.py
    python3 scripts/check_security_handoffs.py --handoff-dir DIR

Reads the five briefs RM-075 owns under `.scratch/consumer-security-sweep/`
(overridable with `--handoff-dir` for hermetic fixtures). Each brief must name
its repository, its P0/P1 finding IDs with installed/fixed versions (or an
explicit `N/A — control-only` / `N/A — decommissioned` reason), at least one
verification command and owner action, dated suppression records, and both
guardrail prohibitions.

The command scanner reads fenced shell blocks and inline command spans for an
executable `--force`. The guardrail sentence that forbids `audit fix --force`
is prose (or an inline span inside Guardrails) and is deliberately allowed.

Exit codes: 0 = all five briefs complete; 1 = a brief is missing or
incomplete; 2 = the checker could not read its inputs.
"""
import argparse
import datetime as _dt
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import consumer_security_sweep as sweep  # noqa: E402

DEFAULT_HANDOFF_DIR = os.path.join(REPO_ROOT, ".scratch",
                                   "consumer-security-sweep")
HANDOFFS = (
    ("handoff-paragon-learning-network.md", "paragon-learning-network"),
    ("handoff-pt.md", "pt"),
    ("handoff-marvin-slack.md", "marvin-slack"),
    ("handoff-excel-daily-monitor.md", "excel-daily-monitor"),
    ("handoff-pln.md", "pln"),
)
REPO_LINE = re.compile(r"^Repo:\s*`([^`]+)`\s*\(`([^`]+)`\)\s*$", re.M)
HEADINGS = ("P0/P1 findings", "Verification", "Owner actions",
            "Suppressions", "Guardrails")
FINDING_COLUMNS = ("Finding ID", "Priority", "Installed", "Fixed")
SUPPRESSION_COLUMNS = ("ID", "Owner", "Date", "Review on", "Rationale")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
COMMAND_RE = re.compile(
    r"^(?:sudo\s+)?(?:npm|npx|yarn|pnpm|git|gh|node|python3?|bash|sh|audit)\b")
COMMAND_SEPARATOR_RE = re.compile(r"\|\||&&|;|\|")
ENV_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=\S*\s+")
WRAPPER_RE = re.compile(
    r"^(?:env|command|nohup|time|exec|eval|xargs)\b\s*(?:-\S+\s+)*")
SHELL_KEYWORD_RE = re.compile(
    r"^(?:if|then|elif|else|do|done|while|until)\b\s*")
FIND_EXEC_RE = re.compile(r"(?:^|\s)-exec(?:dir)?\s+")
SUDO_ARG_FLAGS = {"-u", "-g", "-p", "-C", "-h", "-U", "-r", "-t", "-D"}
N_A_CONTROL = "N/A — control-only"
N_A_RETIRED = "N/A — decommissioned"


def _split_sections(text):
    sections, current, buffer = {}, None, []
    for line in text.splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            if current is not None:
                sections[current] = "\n".join(buffer)
            current, buffer = match.group(1), []
        elif current is not None:
            buffer.append(line)
    if current is not None:
        sections[current] = "\n".join(buffer)
    return sections


def _table(section, required_columns):
    lines = section.splitlines()
    header_index = None
    columns = []
    for index, line in enumerate(lines):
        if line.strip().startswith("|"):
            header_index = index
            columns = [cell.strip() for cell in line.strip().strip("|").split("|")]
            break
    if header_index is None:
        return required_columns, []
    rows = []
    for line in lines[header_index + 2:]:
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        rows.append(dict(zip(columns, cells)))
    missing = tuple(column for column in required_columns
                    if column not in columns)
    return missing, rows


def _fenced_blocks(section):
    blocks, current = [], None
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            if current is None:
                current = []
            else:
                blocks.append("\n".join(current))
                current = None
        elif current is not None:
            current.append(line)
    if current is not None:
        blocks.append("\n".join(current))
    return blocks


def _inline_spans(section):
    return re.findall(r"`([^`\n]+)`", section)


def _has_content(section):
    if any(block.strip() for block in _fenced_blocks(section)):
        return True
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if re.match(r"^(?:[-*]|\d+\.)\s+\S", stripped):
            return True
        if re.search(r"`[^`\n]+`", stripped):
            return True
    return False


def _logical_lines(block):
    """Join backslash continuations; drop blank lines and shell comments."""
    lines, current = [], ""
    for raw in block.splitlines():
        line = raw.rstrip()
        if line.endswith("\\"):
            current += line[:-1].rstrip() + " "
            continue
        candidate = (current + line).strip()
        current = ""
        if candidate and not candidate.startswith("#"):
            lines.append(candidate)
    if current.strip():
        lines.append(current.strip())
    return lines


def _strip_sudo(segment):
    """Strip `sudo` plus its positionals (`-u <user>`, `-g <group>`, ...)."""
    tokens = segment[len("sudo"):].lstrip().split()
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in SUDO_ARG_FLAGS:
            index += 2
        elif token.startswith("-"):
            index += 1
        else:
            break
    return " ".join(tokens[index:])


def _strip_command_prefixes(segment):
    """Reach the command token after assignments, wrappers, and shell forms."""
    while True:
        segment = segment.lstrip()
        if not segment:
            return segment
        assignment = ENV_ASSIGNMENT_RE.match(segment)
        if assignment:
            segment = segment[assignment.end():]
            continue
        if re.match(r"^sudo\b", segment):
            segment = _strip_sudo(segment)
            continue
        if segment.startswith("$("):
            segment = segment[2:]
            continue
        if segment.startswith(("(", "{")):
            segment = segment[1:]
            continue
        if segment.split(None, 1)[0] == "find":
            found = FIND_EXEC_RE.search(segment)
            if found:
                segment = segment[found.end():]
                continue
        wrapper = WRAPPER_RE.match(segment)
        if wrapper:
            segment = segment[wrapper.end():]
            continue
        keyword = SHELL_KEYWORD_RE.match(segment)
        if keyword:
            segment = segment[keyword.end():]
            continue
        return segment


def _dequote_first_token(segment):
    """Undo quote-splitting in the command token (`np""m` -> `npm`)."""
    parts = segment.split(None, 1)
    if not parts:
        return segment
    first = parts[0].replace('"', "").replace("'", "")
    return first if len(parts) == 1 else f"{first} {parts[1]}"


def _line_has_executable_force(line):
    """True when a command segment on this logical line carries --force."""
    for segment in COMMAND_SEPARATOR_RE.split(line):
        segment = _strip_command_prefixes(segment.strip())
        if "--force" not in segment:
            continue
        if COMMAND_RE.match(_dequote_first_token(segment)):
            return True
    return False


def _executable_force(section, include_inline=True):
    for block in _fenced_blocks(section):
        if "--force" not in block:
            continue
        if any(_line_has_executable_force(line)
               for line in _logical_lines(block)):
            return True
    if include_inline:
        for span in _inline_spans(section):
            if "--force" in span and _line_has_executable_force(span.strip()):
                return True
    return False


def _iso(value):
    if not DATE_RE.match(value or ""):
        return False
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _normalize_na(value):
    return re.sub(r"\s+-\s+", " — ", value).strip()


def check_brief(path, expected_slug, consumers):
    """Return a list of problems for one brief."""
    problems = []
    if not os.path.isfile(path):
        return [f"{os.path.basename(path)}: missing"]
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    match = REPO_LINE.search(text)
    if not match:
        problems.append("Repo line must be: Repo: `<slug>` (`<owner/repository>`)")
    else:
        slug, repository = match.group(1), match.group(2)
        record = next((row for row in consumers if row["slug"] == slug), None)
        if record is None:
            problems.append(f"unknown consumer slug: {slug}")
        elif slug != expected_slug:
            problems.append(
                f"slug {slug} does not match filename ({expected_slug})")
        elif repository != record["repository"]:
            problems.append(
                f"repository {repository} does not match inventory "
                f"({record['repository']})")

    sections = _split_sections(text)
    for heading in HEADINGS:
        if heading not in sections:
            problems.append(f"missing section: ## {heading}")
    if problems:
        return problems

    missing, rows = _table(sections["P0/P1 findings"], FINDING_COLUMNS)
    if missing:
        problems.append(f"findings table lacks column(s): {list(missing)}")
    if not rows:
        problems.append("findings table has no P0/P1 row")
    for row in rows:
        finding_id = row.get("Finding ID", "")
        priority = row.get("Priority", "").upper()
        if not finding_id:
            problems.append("findings row without Finding ID")
        if priority not in ("P0", "P1"):
            problems.append(f"finding {finding_id or '?'}: Priority must be P0 or P1")
        for column in ("Installed", "Fixed"):
            value = _normalize_na(row.get(column, ""))
            if value in (N_A_CONTROL, N_A_RETIRED):
                continue
            if not value:
                problems.append(
                    f"finding {finding_id or '?'}: {column} must be a version "
                    f"or an explicit N/A reason")

    if not _has_content(sections["Verification"]):
        problems.append("Verification needs at least one command")
    if not _has_content(sections["Owner actions"]):
        problems.append("Owner actions needs at least one action")

    suppressions = sections["Suppressions"].strip()
    if re.fullmatch(r"None\.?", suppressions, flags=re.I):
        pass
    else:
        missing, rows = _table(suppressions, SUPPRESSION_COLUMNS)
        if missing:
            problems.append(
                f"Suppressions table lacks column(s): {list(missing)}")
        if suppressions and not rows and not missing:
            problems.append("Suppressions must be `None.` or a dated table")
        for row in rows:
            entry = row.get("ID", "") or "?"
            if not row.get("ID", "").strip():
                problems.append("suppression row without ID")
            if not row.get("Owner", "").strip():
                problems.append(f"suppression {entry}: owner missing")
            if not _iso(row.get("Date", "")):
                problems.append(f"suppression {entry}: date missing or invalid")
            if not _iso(row.get("Review on", "")):
                problems.append(
                    f"suppression {entry}: review date missing or invalid "
                    "(undated suppression)")
            if not row.get("Rationale", "").strip():
                problems.append(f"suppression {entry}: rationale missing")

    guardrails = sections["Guardrails"]
    lowered = guardrails.lower()
    if "audit fix --force" not in lowered:
        problems.append("Guardrails must forbid `audit fix --force`")
    if "undated" not in lowered:
        problems.append("Guardrails must forbid undated suppression")

    for heading, section in sections.items():
        if heading == "Guardrails":
            if _executable_force(section, include_inline=False):
                problems.append("Guardrails contains an executable --force command")
            continue
        if _executable_force(section):
            problems.append(f"## {heading} contains an executable --force command")
    return problems


def run(handoff_dir, consumers):
    failures = []
    for filename, slug in HANDOFFS:
        path = os.path.join(handoff_dir, filename)
        for problem in check_brief(path, slug, consumers):
            failures.append(f"{filename}: {problem}")
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handoff-dir", default=DEFAULT_HANDOFF_DIR)
    parser.add_argument("--inventory", default=sweep.DEFAULT_INVENTORY)
    args = parser.parse_args(argv)
    try:
        consumers = sweep.load_inventory(args.inventory)
    except (sweep.SchemaError, OSError) as exc:
        print(f"ERROR  {exc}", file=sys.stderr)
        return 2
    if not os.path.isdir(args.handoff_dir):
        print(f"BLOCKED  handoff directory missing: {args.handoff_dir}",
              file=sys.stderr)
        print("RM-075 owns the five real briefs; fixture success cannot "
              "satisfy this gate.", file=sys.stderr)
        return 1
    failures = run(args.handoff_dir, consumers)
    if failures:
        for failure in failures:
            print(f"FAIL  {failure}")
        print(f"\nHANDOFFS INCOMPLETE: {len(failures)} problem(s)")
        return 1
    print(f"OK: {len(HANDOFFS)} handoff briefs complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
