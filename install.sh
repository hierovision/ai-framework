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

usage() {
  echo "Usage: $0 [--uninstall]"
  echo "  Links skills/*/, agents/*.md and reference/ into the global opencode config:"
  echo "    $SKILLS_TARGET"
  echo "    $AGENTS_TARGET"
  echo "    $REFERENCE_TARGET"
  echo "  Override targets with OPENCODE_SKILLS_DIR / OPENCODE_AGENTS_DIR / OPENCODE_REFERENCE_DIR."
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
}

# Validate an agent's frontmatter: it must carry a `name:` that matches the
# file stem and a non-empty `model:` (so a broken agent is skipped, not linked
# with a silent default). Consistency with skills, which validate SKILL.md.
validate_agent_frontmatter() {
  local file="$1"
  local fm name model stem
  fm="$(awk 'BEGIN{c=0} /^---/{c++; next} c==1{print}' "$file")"
  name="$(printf '%s\n' "$fm" | awk -F': ' '/^name:/{print $2; exit}')"
  model="$(printf '%s\n' "$fm" | awk -F': ' '/^model:/{print $2; exit}')"
  stem="${file##*/}"; stem="${stem%.md}"
  if [ -z "$name" ]; then echo "skip $(basename "$file") (no name in frontmatter)" >&2; return 1; fi
  if [ "$name" != "$stem" ]; then echo "skip $(basename "$file") (name '$name' != file stem '$stem')" >&2; return 1; fi
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
}

case "${1:-}" in
  --uninstall) uninstall ;;
  -h|--help) usage ;;
  "") install ;;
  *) usage >&2; exit 1 ;;
esac
