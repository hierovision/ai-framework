#!/usr/bin/env bash
# Symlink skills and agents from this repo into the global opencode discovery
# paths. Idempotent: safe to re-run. Use --uninstall to remove only the links
# that point back into this repo.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_SRC="$REPO_DIR/skills"
AGENTS_SRC="$REPO_DIR/agents"
REFERENCE_SRC="$REPO_DIR/reference"
SKILLS_TARGET="${OPENCODE_SKILLS_DIR:-$HOME/.config/opencode/skills}"
AGENTS_TARGET="${OPENCODE_AGENTS_DIR:-$HOME/.config/opencode/agents}"
REFERENCE_TARGET="${OPENCODE_REFERENCE_DIR:-$HOME/.config/opencode/reference}"
# RM-073 P1-9: the install manifest records what was installed, from which
# commit, and whether the tree was dirty. `--check` compares the live tree to
# it; `--require-clean` refuses to install from an uncommitted tree.
MANIFEST="${OPENCODE_INSTALL_MANIFEST:-$HOME/.config/opencode/.ai-framework-install.json}"

usage() {
  echo "Usage: $0 [--uninstall | --check | --require-clean]"
  echo "  Links skills/*/, agents/*.md and reference/ into the global opencode config:"
  echo "    $SKILLS_TARGET"
  echo "    $AGENTS_TARGET"
  echo "    $REFERENCE_TARGET"
  echo "  Writes the install manifest: $MANIFEST"
  echo "    {repo_path, commit, dirty, installed_at}"
  echo "  --check         verify the manifest matches HEAD and every link exists (no writes)"
  echo "  --require-clean refuse to install from a tree with uncommitted changes"
  echo "  Override targets with OPENCODE_SKILLS_DIR / OPENCODE_AGENTS_DIR / OPENCODE_REFERENCE_DIR"
  echo "  and the manifest path with OPENCODE_INSTALL_MANIFEST."
  echo "  After the supported @opencode/cli install, stage the reviewed V2 config:"
  echo "    python3 scripts/stage_opencode_config.py --backup"
}

# --- install manifest (RM-073 P1-9) ---------------------------------------
json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

repo_commit() {
  git -C "$REPO_DIR" rev-parse HEAD 2>/dev/null || echo "unknown"
}

repo_dirty() {
  if ! git -C "$REPO_DIR" rev-parse --git-dir >/dev/null 2>&1; then
    echo false
    return 0
  fi
  if [ -n "$(git -C "$REPO_DIR" status --porcelain 2>/dev/null)" ]; then
    echo true
  else
    echo false
  fi
}

manifest_write() {
  local commit dirty installed_at
  commit="$(repo_commit)"
  dirty="$(repo_dirty)"
  installed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  mkdir -p "$(dirname "$MANIFEST")"
  cat > "$MANIFEST" <<EOF
{
  "repo_path": "$(json_escape "$REPO_DIR")",
  "commit": "$(json_escape "$commit")",
  "dirty": $dirty,
  "installed_at": "$installed_at"
}
EOF
  echo "wrote manifest $MANIFEST (commit $commit, dirty=$dirty)"
}

manifest_string() {
  sed -n 's/^[[:space:]]*"'"$1"'":[[:space:]]*"\([^"]*\)".*/\1/p' "$MANIFEST" | head -1
}

manifest_bool() {
  sed -n 's/^[[:space:]]*"'"$1"'":[[:space:]]*\(true\|false\).*/\1/p' "$MANIFEST" | head -1
}

check_links() {
  local failed=0 entry name
  for entry in "$SKILLS_SRC"/*; do
    [ -d "$entry" ] || continue
    [ -f "$entry/SKILL.md" ] || continue
    name="$(basename "$entry")"
    if [ ! -L "$SKILLS_TARGET/$name" ]; then
      echo "error: missing skill link: $SKILLS_TARGET/$name" >&2
      failed=1
    fi
  done
  for entry in "$AGENTS_SRC"/*.md; do
    [ -e "$entry" ] || continue
    name="$(basename "$entry")"
    if [ ! -L "$AGENTS_TARGET/$name" ]; then
      echo "error: missing agent link: $AGENTS_TARGET/$name" >&2
      failed=1
    fi
  done
  if [ ! -L "$REFERENCE_TARGET" ]; then
    echo "error: missing reference link: $REFERENCE_TARGET" >&2
    failed=1
  fi
  return "$failed"
}

check_install() {
  if [ ! -f "$MANIFEST" ]; then
    echo "error: no install manifest at $MANIFEST — run $0 first" >&2
    return 1
  fi
  local failed=0 recorded_path recorded_commit recorded_dirty head
  recorded_path="$(manifest_string repo_path)"
  recorded_commit="$(manifest_string commit)"
  recorded_dirty="$(manifest_bool dirty)"
  head="$(repo_commit)"
  if [ "$recorded_path" != "$REPO_DIR" ]; then
    echo "error: manifest repo_path '$recorded_path' != '$REPO_DIR'" >&2
    failed=1
  fi
  if [ "$recorded_commit" != "$head" ]; then
    echo "error: manifest commit $recorded_commit != HEAD $head (re-run $0)" >&2
    failed=1
  fi
  if [ "$recorded_dirty" != "false" ]; then
    echo "error: manifest records a dirty install (re-run $0 from a clean commit)" >&2
    failed=1
  fi
  check_links || failed=1
  if [ "$failed" -eq 0 ]; then
    echo "OK: install manifest matches HEAD $head and every link exists"
  fi
  return "$failed"
}

require_clean() {
  if [ "$(repo_dirty)" = "true" ]; then
    echo "error: $REPO_DIR has uncommitted changes; --require-clean refuses to install (commit or stash first)" >&2
    return 1
  fi
}

# Remove symlinks in $target that point under $src (this repo).
uninstall_dir() {
  local src="$1" target="$2"
  [ -d "$target" ] || return 0
  local removed=0
  for link in "$target"/*; do
    [ -L "$link" ] || continue
    case "$(readlink "$link")" in
      "$src"/*)
        rm "$link"
        echo "removed $(basename "$link")"
        removed=$((removed + 1))
        ;;
    esac
  done
  echo "Uninstalled $removed link(s) from $target."
}

uninstall() {
  uninstall_dir "$SKILLS_SRC" "$SKILLS_TARGET"
  uninstall_dir "$AGENTS_SRC" "$AGENTS_TARGET"
  uninstall_dir "$REPO_DIR" "$REFERENCE_TARGET"
  if [ -f "$MANIFEST" ]; then
    rm "$MANIFEST"
    echo "removed manifest $MANIFEST"
  fi
}

# Validate an agent's native V2 frontmatter: the ID is path-derived, so a
# non-empty description and model are required and a legacy `name:` is
# rejected (the corpus must not carry one). A malformed agent is skipped with
# a named reason, never linked with a silent default.
validate_agent_frontmatter() {
  local file="$1"
  local fm description model stem
  fm="$(awk 'BEGIN{c=0} /^---/{c++; next} c==1{print}' "$file")"
  description="$(printf '%s\n' "$fm" | awk -F': ' '/^description:/{print $2; exit}')"
  model="$(printf '%s\n' "$fm" | awk -F': ' '/^model:/{print $2; exit}')"
  stem="${file##*/}"; stem="${stem%.md}"
  if [ -z "$stem" ]; then echo "skip $(basename "$file") (empty path-derived id)" >&2; return 1; fi
  if printf '%s\n' "$fm" | grep -q '^name:'; then
    echo "skip $(basename "$file") (legacy name: present; the id is path-derived)" >&2
    return 1
  fi
  if [ -z "$description" ]; then echo "skip $(basename "$file") (no description in frontmatter)" >&2; return 1; fi
  if [ -z "$model" ]; then echo "skip $(basename "$file") (no model in frontmatter)" >&2; return 1; fi
  return 0
}

# Symlink each child of $src into $target.
#   $1 = source dir, $2 = target dir, $3 = kind label,
#   $4 = optional required file inside each child (skills need SKILL.md),
#   $5 = optional extension filter (agents are *.md),
#   $6 = optional validator command (run per entry; non-zero -> skip)
link_children() {
  local src="$1" target="$2" kind="$3" reqfile="${4:-}" ext="${5:-}" validator="${6:-}"
  [ -d "$src" ] || { echo "No $kind directory found at $src" >&2; exit 1; }
  mkdir -p "$target"
  local linked=0 skipped=0
  for entry in "$src"/*; do
    [ -e "$entry" ] || continue
    local name
    name="$(basename "$entry")"
    if [ -n "$ext" ] && [ "${name##*.}" != "$ext" ]; then
      continue
    fi
    if [ -n "$reqfile" ] && [ ! -f "$entry/$reqfile" ]; then
      echo "skip $name (no $reqfile)"
      skipped=$((skipped + 1))
      continue
    fi
    if [ -n "$validator" ] && ! "$validator" "$entry"; then
      skipped=$((skipped + 1))
      continue
    fi
    local dest="$target/$name"
    if [ -L "$dest" ]; then
      # Refresh existing symlink (may point at an old location)
      rm "$dest"
    elif [ -e "$dest" ]; then
      echo "skip $name (non-symlink already exists at $dest)" >&2
      skipped=$((skipped + 1))
      continue
    fi
    ln -s "$entry" "$dest"
    echo "linked $name"
    linked=$((linked + 1))
  done
  echo "Installed $linked $kind(s) into $target ($skipped skipped)."
}

install() {
  link_children "$SKILLS_SRC" "$SKILLS_TARGET" "skill" "SKILL.md" "" ""
  link_children "$AGENTS_SRC" "$AGENTS_TARGET" "agent" "" "md" "validate_agent_frontmatter"
  # reference/ is a flat dir of library policy docs, linked wholesale.
  if [ ! -d "$REFERENCE_SRC" ]; then
    echo "No reference directory found at $REFERENCE_SRC" >&2
    exit 1
  fi
  mkdir -p "$(dirname "$REFERENCE_TARGET")"
  if [ -L "$REFERENCE_TARGET" ]; then
    rm "$REFERENCE_TARGET"
    ln -s "$REFERENCE_SRC" "$REFERENCE_TARGET"
    echo "linked reference"
  elif [ -e "$REFERENCE_TARGET" ]; then
    echo "skip reference (non-symlink already exists at $REFERENCE_TARGET)" >&2
  else
    ln -s "$REFERENCE_SRC" "$REFERENCE_TARGET"
    echo "linked reference"
  fi
  manifest_write
}

case "${1:-}" in
  --uninstall) uninstall ;;
  --check) check_install ;;
  --require-clean) require_clean && install ;;
  -h|--help) usage ;;
  "") install ;;
  *) usage >&2; exit 1 ;;
esac
