#!/usr/bin/env bash
# Symlink skills and agents from this repo into the global opencode discovery
# paths. Idempotent: safe to re-run. Use --uninstall to remove only the links
# that point back into this repo.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_SRC="$REPO_DIR/skills"
AGENTS_SRC="$REPO_DIR/agents"
SKILLS_TARGET="${OPENCODE_SKILLS_DIR:-$HOME/.config/opencode/skills}"
AGENTS_TARGET="${OPENCODE_AGENTS_DIR:-$HOME/.config/opencode/agents}"

usage() {
  echo "Usage: $0 [--uninstall]"
  echo "  Links skills/*/ and agents/*.md into the global opencode config:"
  echo "    $SKILLS_TARGET"
  echo "    $AGENTS_TARGET"
  echo "  Override targets with OPENCODE_SKILLS_DIR / OPENCODE_AGENTS_DIR."
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
}

# Symlink each child of $src into $target.
#   $1 = source dir, $2 = target dir, $3 = kind label,
#   $4 = optional required file inside each child (skills need SKILL.md),
#   $5 = optional extension filter (agents are *.md)
link_children() {
  local src="$1" target="$2" kind="$3" validate="${4:-}" ext="${5:-}"
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
    if [ -n "$validate" ] && [ ! -f "$entry/$validate" ]; then
      echo "skip $name (no $validate)"
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
  link_children "$SKILLS_SRC" "$SKILLS_TARGET" "skill" "SKILL.md" ""
  link_children "$AGENTS_SRC" "$AGENTS_TARGET" "agent" "" "md"
}

case "${1:-}" in
  --uninstall) uninstall ;;
  -h|--help) usage ;;
  "") install ;;
  *) usage >&2; exit 1 ;;
esac
