#!/usr/bin/env bash
# Gather the raw material for a release: the last tag, the commits since it,
# and a suggested SemVer bump derived from Conventional Commits.
#
# Usage:
#   collect-release-inputs.sh [--from <tag>]
#
# Run from anywhere inside the target git repository. Prints a Markdown report
# to stdout. Exits non-zero with a message when the repository or tag cannot be
# resolved, so the caller can fall back to a user-provided change list instead
# of guessing.
set -euo pipefail

from=""
while [ $# -gt 0 ]; do
  case "$1" in
    --from) from="${2:-}"; shift 2 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "error: not inside a git repository" >&2
  exit 1
fi

if [ -z "$from" ]; then
  from="$(git describe --tags --abbrev=0 2>/dev/null || true)"
fi
if [ -z "$from" ]; then
  echo "error: no tag found; pass --from <tag> or create an initial tag" >&2
  exit 1
fi
if ! git rev-parse -q --verify "refs/tags/$from" >/dev/null 2>&1; then
  echo "error: tag '$from' does not exist" >&2
  exit 1
fi

range="$from..HEAD"
subjects="$(git log --no-merges --pretty=format:'%s' "$range")"
breaking="$(git log --no-merges --pretty=format:'%s%n%b' "$range" \
  | grep -E '(^|[^[:alnum:]_])!:|BREAKING CHANGE' || true)"

# Highest-precedence Conventional Commit type wins: breaking > feat > fix/perf.
bump="none"
if [ -n "$breaking" ]; then
  bump="major"
elif printf '%s\n' "$subjects" | grep -qE '^feat(\(|:|!)'; then
  bump="minor"
elif printf '%s\n' "$subjects" | grep -qE '^(fix|perf)(\(|:|!)'; then
  bump="patch"
fi

count="$(printf '%s' "$subjects" | grep -c . || true)"

echo "# Release inputs"
echo
echo "- Last tag: $from"
echo "- Commits since: $count"
echo "- Suggested bump: $bump"
echo
echo "## Commit subjects"
echo
if [ -n "$subjects" ]; then
  printf '%s\n' "$subjects"
else
  echo "(none)"
fi
