#!/usr/bin/env bash
# Sync skills from .agents/skills/ to related directories via symlinks.
# Usage:
#   ./scripts/sync_skills.sh          # one-shot sync
#   ./scripts/sync_skills.sh --watch  # continuous watch mode (requires fswatch)

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE_DIR="$PROJECT_DIR/.agents/skills"
TARGETS=(
  "$PROJECT_DIR/skills"
  "$PROJECT_DIR/.cursor/skills"
  "${HOME}/.agents/skills"
)

sync_skills() {
  local changed=0

  for skill_dir in "$SOURCE_DIR"/*/; do
    [ -d "$skill_dir" ] || continue
    local name
    name=$(basename "$skill_dir")
    [[ "$name" == .* ]] && continue

    for target in "${TARGETS[@]}"; do
      mkdir -p "$target"
      local dest="$target/$name"

      [ -e "$dest" ] || [ -L "$dest" ] && continue

      # Use relative path for project-internal target, absolute for global
      if [[ "$target" == "$PROJECT_DIR/"* ]]; then
        local rel
        rel=$(python3 -c "import os; print(os.path.relpath('$SOURCE_DIR/$name', '$target'))")
        ln -s "$rel" "$dest"
      else
        ln -s "$SOURCE_DIR/$name" "$dest"
      fi
      echo "  + $dest -> $skill_dir"
      changed=$((changed + 1))
    done
  done

  if [ "$changed" -eq 0 ]; then
    echo "  (all targets up to date)"
  else
    echo "  synced $changed symlink(s)"
  fi
}

echo "[sync_skills] scanning $SOURCE_DIR ..."
sync_skills

if [ "${1:-}" = "--watch" ]; then
  if ! command -v fswatch &>/dev/null; then
    echo "[sync_skills] fswatch not found, installing via Homebrew ..."
    brew install fswatch
  fi
  echo "[sync_skills] watching for changes (Ctrl+C to stop) ..."
  fswatch -0 -e ".*" -i "\\.agents/skills/" --event Created "$SOURCE_DIR" |
    while IFS= read -r -d '' _; do
      echo "[sync_skills] change detected, syncing ..."
      sync_skills
    done
fi
