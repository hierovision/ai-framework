#!/usr/bin/env bash
# install.sh manifest tests (RM-073 P1-9).
#
# Run: bash scripts/test_install_sh.sh
#
# Hermetic: builds a throw-away git repo containing a minimal skills/agents/
# reference tree, runs the REAL install.sh against a temp HOME, and asserts:
#   1. install writes ~/.config/opencode/.ai-framework-install.json with the
#      four manifest fields, the true HEAD, dirty=false and an ISO timestamp;
#   2. every expected symlink exists;
#   3. --check passes on a matching install and creates nothing;
#   4. --check fails after a new commit (commit drift) and after a dirty
#      install, and does not repair anything;
#   5. --require-clean refuses on an uncommitted tree without rewriting the
#      manifest;
#   6. --check fails when no manifest exists.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL="$REPO_DIR/install.sh"
WORK_ROOT="$REPO_DIR/.scratch/test-tmp"
mkdir -p "$WORK_ROOT"
WORK="$(mktemp -d "$WORK_ROOT/install-sh-XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

fail() { echo "FAIL  $*" >&2; exit 1; }
pass() { echo "PASS  $*"; }

SRC="$WORK/repo"
HOME_DIR="$WORK/home"
mkdir -p "$SRC/skills/alpha" "$SRC/agents" "$SRC/reference" "$HOME_DIR"
cp "$INSTALL" "$SRC/install.sh"
printf '# alpha\n\nA test skill.\n' > "$SRC/skills/alpha/SKILL.md"
printf -- '---\ndescription: probe agent\nmodel: test/model\n---\n\nProbe.\n' \
  > "$SRC/agents/probe.md"
printf 'policy\n' > "$SRC/reference/policy.md"

git -C "$SRC" init -q -b main
git -C "$SRC" config user.email test@example.com
git -C "$SRC" config user.name "Install Test"
git -C "$SRC" add -A
git -C "$SRC" commit -qm "initial"

MANIFEST="$HOME_DIR/.config/opencode/.ai-framework-install.json"
CONFIG="$HOME_DIR/.config/opencode"

run_install() { HOME="$HOME_DIR" bash "$SRC/install.sh" "$@"; }

validate_manifest() {
  python3 - "$MANIFEST" "$SRC" "$1" <<'PY'
import json, re, subprocess, sys
manifest, repo, expected_dirty = sys.argv[1], sys.argv[2], sys.argv[3]
with open(manifest, encoding="utf-8") as fh:
    data = json.load(fh)
assert set(data) == {"repo_path", "commit", "dirty", "installed_at"}, data
assert data["repo_path"] == repo, data
head = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                      capture_output=True, text=True, check=True).stdout.strip()
assert data["commit"] == head, (data["commit"], head)
assert data["dirty"] is (expected_dirty == "true"), data
assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", data["installed_at"]), data
PY
}

# 1 — install from a clean tree
run_install >/dev/null
[ -f "$MANIFEST" ] || fail "install did not write the manifest"
validate_manifest false
[ -L "$CONFIG/skills/alpha" ] || fail "missing skill symlink"
[ -L "$CONFIG/agents/probe.md" ] || fail "missing agent symlink"
[ -L "$CONFIG/reference" ] || fail "missing reference symlink"
pass "clean install writes the manifest and every symlink"

# 2 — --check on a clean install, and it must not write
BEFORE="$(find "$HOME_DIR" -type l | sort)"
run_install --check >/dev/null || fail "--check failed on a matching install"
AFTER="$(find "$HOME_DIR" -type l | sort)"
[ "$BEFORE" = "$AFTER" ] || fail "--check modified the install"
pass "--check passes on a matching install (no writes)"

# 3 — commit drift
git -C "$SRC" commit -q --allow-empty -m drift
if run_install --check >/dev/null 2>&1; then
  fail "--check accepted a stale commit"
fi
pass "--check fails after a new commit"
run_install >/dev/null
run_install --check >/dev/null || fail "--check failed after reinstall"
pass "reinstall resynchronises the manifest"

# 4 — --require-clean refuses a dirty tree and does not rewrite the manifest
echo "uncommitted" > "$SRC/untracked.txt"
COMMIT_BEFORE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["commit"])' "$MANIFEST")"
if run_install --require-clean >/dev/null 2>&1; then
  fail "--require-clean accepted a dirty tree"
fi
COMMIT_AFTER="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["commit"])' "$MANIFEST")"
[ "$COMMIT_BEFORE" = "$COMMIT_AFTER" ] || fail "--require-clean rewrote the manifest"
run_install --check >/dev/null || fail "--check should still match HEAD"
pass "--require-clean refuses a dirty tree without touching the manifest"

# 5 — a dirty install is recorded, and --check rejects it as non-reproducible
run_install >/dev/null
validate_manifest true
if run_install --check >/dev/null 2>&1; then
  fail "--check accepted a dirty install"
fi
pass "dirty install is recorded and rejected by --check"

# 6 — no manifest: --check fails and creates nothing
FRESH_HOME="$WORK/fresh-home"
mkdir -p "$FRESH_HOME"
if HOME="$FRESH_HOME" bash "$SRC/install.sh" --check >/dev/null 2>&1; then
  fail "--check passed with no manifest"
fi
[ ! -e "$FRESH_HOME/.config/opencode/skills" ] || fail "--check created links"
pass "--check fails with no manifest and writes nothing"

# 7 — --uninstall removes the manifest
run_install --uninstall >/dev/null
[ ! -f "$MANIFEST" ] || fail "--uninstall left the manifest"
pass "--uninstall removes the manifest"

echo "OK: install.sh manifest tests"
