#!/usr/bin/env bash
# Symlink every skill in this repo into the global opencode discovery path.
# Idempotent: safe to re-run after adding skills. Use --uninstall to remove
# only the links that point back into this repo.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_SRC="$REPO_DIR/skills"
TARGET_DIR="${OPENCODE_SKILLS_DIR:-$HOME/.config/opencode/skills}"

usage() {
  echo "Usage: $0 [--uninstall]"
  echo "  Links skills/*/ into $TARGET_DIR"
  echo "  Override target with OPENCODE_SKILLS_DIR."
}

uninstall() {
  local removed=0
  [ -d "$TARGET_DIR" ] || { echo "Nothing installed at $TARGET_DIR"; return 0; }
  for link in "$TARGET_DIR"/*; do
    [ -L "$link" ] || continue
    case "$(readlink "$link")" in
      "$SKILLS_SRC"/*)
        rm "$link"
        echo "removed $(basename "$link")"
        removed=$((removed + 1))
        ;;
    esac
  done
  echo "Uninstalled $removed skill link(s)."
}

install() {
  [ -d "$SKILLS_SRC" ] || { echo "No skills/ directory found at $SKILLS_SRC" >&2; exit 1; }
  mkdir -p "$TARGET_DIR"
  local linked=0 skipped=0
  for skill_dir in "$SKILLS_SRC"/*/; do
    [ -d "$skill_dir" ] || continue
    local name
    name="$(basename "$skill_dir")"
    if [ ! -f "$skill_dir/SKILL.md" ]; then
      echo "skip $name (no SKILL.md)"
      skipped=$((skipped + 1))
      continue
    fi
    local dest="$TARGET_DIR/$name"
    if [ -L "$dest" ]; then
      # Refresh existing symlink (may point at an old location)
      rm "$dest"
    elif [ -e "$dest" ]; then
      echo "skip $name (non-symlink already exists at $dest)" >&2
      skipped=$((skipped + 1))
      continue
    fi
    ln -s "${skill_dir%/}" "$dest"
    echo "linked $name"
    linked=$((linked + 1))
  done
  echo "Installed $linked skill(s) into $TARGET_DIR ($skipped skipped)."
}

case "${1:-}" in
  --uninstall) uninstall ;;
  -h|--help) usage ;;
  "") install ;;
  *) usage >&2; exit 1 ;;
esac
