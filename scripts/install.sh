#!/usr/bin/env bash
# Install skills from this repo into an agent's skills directory.
#
# Usage:
#   ./scripts/install.sh --all                      # every skill -> ~/.claude/skills
#   ./scripts/install.sh --category programming     # one category
#   ./scripts/install.sh --subcategory sql           # one sub-category
#   ./scripts/install.sh sql-query-writer excel-formulas
#   ./scripts/install.sh --project . --all          # -> ./.claude/skills (shared with your team via git)
#   ./scripts/install.sh --dest ~/.codex/skills --all   # any agent that reads SKILL.md folders
#   ./scripts/install.sh --list
#
# Existing copies of the same skill are replaced. Use --link to symlink instead
# of copying, so `git pull` in this repo updates installed skills.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_DIR="$REPO_ROOT/skills"
DEST="$HOME/.claude/skills"
MODE=copy
SELECTED=()

usage() { sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

# Portable to macOS bash 3.2: no mapfile, no GNU-only find flags.
# Layout: skills/<category>/<subcategory>/<skill>/SKILL.md
all_skills() { for f in "$SKILLS_DIR"/*/*/*/SKILL.md; do [[ -e "$f" ]] && dirname "$f"; done; }

add_skills() { while IFS= read -r dir; do SELECTED+=("$dir"); done; }

add_skill() {
  local match
  for match in "$SKILLS_DIR"/*/*/"$1"; do
    [[ -f "$match/SKILL.md" ]] && { SELECTED+=("$match"); return; }
  done
  echo "error: unknown skill '$1' (try --list)" >&2
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)      add_skills < <(all_skills) ;;
    --category)
      [[ -d "$SKILLS_DIR/${2:-}" ]] || { echo "error: unknown category '${2:-}'" >&2; exit 1; }
      add_skills < <(all_skills | grep "^$SKILLS_DIR/$2/")
      shift ;;
    --subcategory)
      matches=("$SKILLS_DIR"/*/"${2:-}")
      [[ -n "${2:-}" && -d "${matches[0]}" ]] || { echo "error: unknown sub-category '${2:-}'" >&2; exit 1; }
      add_skills < <(all_skills | grep "^${matches[0]}/")
      shift ;;
    --project)  DEST="$(cd "${2:?--project needs a directory}" && pwd)/.claude/skills"; shift ;;
    --dest)     DEST="${2:?--dest needs a directory}"; shift ;;
    --link)     MODE=link ;;
    --list)
      all_skills | while read -r dir; do
        printf '%-14s %-8s %s\n' "$(basename "$(dirname "$(dirname "$dir")")")" "$(basename "$(dirname "$dir")")" "$(basename "$dir")"
      done
      exit 0 ;;
    -h|--help)  usage ;;
    -*)         echo "error: unknown option $1" >&2; usage 1 ;;
    *)          add_skill "$1" ;;
  esac
  shift
done

[[ ${#SELECTED[@]} -gt 0 ]] || usage 1

mkdir -p "$DEST"
for src in "${SELECTED[@]}"; do
  name="$(basename "$src")"
  rm -rf "${DEST:?}/$name"
  if [[ $MODE == link ]]; then
    ln -s "$src" "$DEST/$name"
  else
    cp -R "$src" "$DEST/$name"
    find "$DEST/$name" -name __pycache__ -type d -prune -exec rm -rf {} +
  fi
  echo "installed $name -> $DEST/$name"
done
echo "Done. Restart your agent session to pick up new skills."
