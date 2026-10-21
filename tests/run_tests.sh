#!/usr/bin/env bash
# Smoke-test every helper script that ships inside a skill.
#
#   1. Every skills/*/*/*/scripts/* entry point (.py, .sh, .rs with fn main)
#      must run `--help` successfully and print "usage".
#   2. Every entry point needs at least one case in tests/cases/*.sh: it runs
#      against the fixtures in tests/fixtures and must exit with the expected
#      code and print the expected text (stdout + stderr).
#
# Rust scripts are standalone, std-only files: each one is compiled once with
# `rustc -O` into a cache keyed on its sources and the compiler version, so
# reruns skip compilation. Cases run in parallel; results print in order.
#
# Usage:
#   tests/run_tests.sh               # everything
#   tests/run_tests.sh -k rust       # only scripts/cases whose path or name contains "rust"
#   tests/run_tests.sh -j 4          # at most 4 jobs at once (default: CPU count)
#   tests/run_tests.sh -v            # print output of passing cases too
#
# Case syntax (see tests/cases/*.sh):
#   t NAME EXIT_CODE EXPECTED_TEXT SCRIPT [ARGS...]
#   STDIN=$'text\n' t ...            # feed text on stdin
#   STDIN_FILE=path t ...            # feed a file on stdin
#
# Requires: bash 4.3+, python3 (Python scripts), rustc (Rust scripts).
# Exit code: 0 all passed, 1 any failure, 2 usage error.

set -uo pipefail
shopt -s nullglob

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 2

FILTER="" JOBS="$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)" VERBOSE=0 TIMEOUT=60
while getopts "k:j:vh" opt; do
  case $opt in
    k) FILTER=$OPTARG ;;
    j) JOBS=$OPTARG ;;
    v) VERBOSE=1 ;;
    h) sed -n '2,/^$/s/^# \{0,1\}//p' "$0"; exit 0 ;;
    *) exit 2 ;;
  esac
done

# Paths used by the case files.
FX=tests/fixtures
SQL=skills/programming/sql
XL=skills/productivity/excel
PY=skills/programming/python
RS=skills/programming/rust
export FX SQL XL PY RS

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
BIN_CACHE="${SKILL_TEST_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/vector-agentic-skills/bin}"

# ---------------------------------------------------------------- case registry
NAMES=() CODES=() WANTS=() INPUTS=() CMDS=()
t() {
  local name=$1 code=$2 want=$3; shift 3
  local input=""
  if [[ -n ${STDIN_FILE-} ]]; then input="file:$STDIN_FILE"
  elif [[ -n ${STDIN+x} ]]; then input="text:$STDIN"; fi
  NAMES+=("$name") CODES+=("$code") WANTS+=("$want") INPUTS+=("$input")
  CMDS+=("$(printf '%q ' "$@")")
}
for f in tests/cases/*.sh; do source "$f"; done

matches() { [[ -z $FILTER || $1 == *"$FILTER"* ]]; }

# ---------------------------------------------------------------- entry points
is_entry() {  # Rust files without fn main are modules shared by the scripts
  [[ $1 != *.rs ]] || grep -qE '^[[:space:]]*(pub[[:space:]]+)?fn[[:space:]]+main[[:space:]]*\(' "$1"
}
SCRIPTS=()
for s in skills/*/*/*/scripts/*.{py,sh,rs}; do is_entry "$s" && SCRIPTS+=("$s"); done
mapfile -t SCRIPTS < <(printf '%s\n' "${SCRIPTS[@]}" | sort)

hash_of() { if command -v sha256sum >/dev/null; then sha256sum | cut -c1-16; else shasum -a 256 | cut -c1-16; fi; }

# Compile every Rust entry point once (in parallel) and record its binary.
declare -A BIN
compile_rust() {
  local src=$1 key out
  key="$( { rustc --version; cat "$(dirname "$src")"/*.rs; echo "$src"; } | hash_of)"
  out="$BIN_CACHE/$key/$(basename "$src" .rs)"
  if [[ ! -x $out ]]; then
    mkdir -p "$(dirname "$out")"
    if ! rustc -O --edition 2021 -o "$out.tmp" "$src" 2>"$WORK/rustc.$key.log"; then
      echo "FAIL compile $src"; sed 's/^/     | /' "$WORK/rustc.$key.log" | head -40
      return 1
    fi
    mv "$out.tmp" "$out"
  fi
  echo "$out" > "$WORK/bin.$key"
  echo "$key"
}
FAILURES=0
# Compile Rust scripts that match the filter or that a selected case runs.
SELECTED_CMDS=""
for i in "${!NAMES[@]}"; do
  if matches "${NAMES[$i]}" || matches "${CMDS[$i]}"; then SELECTED_CMDS+="${CMDS[$i]}"$'\n'; fi
done
RUST_SCRIPTS=()
for s in "${SCRIPTS[@]}"; do
  [[ $s == *.rs ]] || continue
  if matches "$s" || grep -qF -- "$s " <<<"$SELECTED_CMDS"; then RUST_SCRIPTS+=("$s"); fi
done
if ((${#RUST_SCRIPTS[@]})); then
  command -v rustc >/dev/null || PATH="$HOME/.cargo/bin:$PATH" # rustup without a PATH change
  if ! command -v rustc >/dev/null; then
    echo "FAIL rustc not found; install Rust (https://rustup.rs) to test ${#RUST_SCRIPTS[@]} Rust script(s)"
    exit 1
  fi
  for s in "${RUST_SCRIPTS[@]}"; do compile_rust "$s" > "$WORK/key.${s//\//_}" & done
  wait
  for s in "${RUST_SCRIPTS[@]}"; do
    key="$(tail -n1 "$WORK/key.${s//\//_}")"
    if [[ -f $WORK/bin.$key ]]; then BIN[$s]="$(cat "$WORK/bin.$key")"
    else cat "$WORK/key.${s//\//_}"; ((FAILURES++)); fi
  done
fi

run_script() {  # run_script SCRIPT [ARGS...]
  local s=$1; shift
  case $s in
    *.py) timeout "$TIMEOUT" python3 "$s" "$@" ;;
    *.sh) timeout "$TIMEOUT" bash "$s" "$@" ;;
    *.rs) [[ -n ${BIN[$s]-} ]] || { echo "not compiled: $s"; return 127; }; timeout "$TIMEOUT" "${BIN[$s]}" "$@" ;;
    *) echo "unknown script type: $s"; return 127 ;;
  esac
}

# ---------------------------------------------------------------- job runner
# Each job writes <id>.out (stdout+stderr) and <id>.rc; reports print in order.
ORDER=()
throttle() { while (($(jobs -rp | wc -l) >= JOBS)); do wait -n; done; }

launch() {  # launch ID INPUT CMD...
  local id=$1 input=$2; shift 2
  throttle
  (
    case $input in
      file:*) exec <"${input#file:}" ;;
      text:*) exec < <(printf '%s' "${input#text:}") ;;
      *) exec </dev/null ;;
    esac
    eval "$*" >"$WORK/$id.out" 2>&1
    echo $? >"$WORK/$id.rc"
  ) &
  ORDER+=("$id")
}

COVERED=""
for i in "${!CMDS[@]}"; do COVERED+="${CMDS[$i]}"$'\n'; done

for s in "${SCRIPTS[@]}"; do
  matches "$s" || continue
  [[ $s == *.rs && -z ${BIN[$s]-} ]] && continue
  launch "help${s//\//_}" "" "run_script $(printf '%q' "$s") --help"
done
for i in "${!NAMES[@]}"; do
  matches "${NAMES[$i]}" || matches "${CMDS[$i]}" || continue
  launch "case$i" "${INPUTS[$i]}" "run_script ${CMDS[$i]}"
done
wait

# ---------------------------------------------------------------- report
for s in "${SCRIPTS[@]}"; do
  matches "$s" || continue
  id="help${s//\//_}"
  if [[ -f $WORK/$id.rc ]]; then
    rc=$(<"$WORK/$id.rc")
    if [[ $rc == 0 ]] && grep -qi usage "$WORK/$id.out"; then echo "ok   --help $s"
    else echo "FAIL --help $s (exit $rc)"; ((FAILURES++)); fi
  fi
  if ! grep -qF -- "$s " <<<"$COVERED"; then
    echo "FAIL no test case for $s; add one to tests/cases/"; ((FAILURES++))
  fi
done

for i in "${!NAMES[@]}"; do
  [[ -f $WORK/case$i.rc ]] || continue
  rc=$(<"$WORK/case$i.rc") out="$WORK/case$i.out"
  if [[ $rc == "${CODES[$i]}" ]] && grep -qF -- "${WANTS[$i]}" "$out"; then
    echo "ok   ${NAMES[$i]}"
    ((VERBOSE)) && sed 's/^/     | /' "$out"
  else
    ((FAILURES++))
    [[ $rc == 124 ]] && rc="timeout after ${TIMEOUT}s"
    echo "FAIL ${NAMES[$i]}"
    echo "     expected exit ${CODES[$i]} and '${WANTS[$i]}'; got exit $rc:"
    sed 's/^/     | /' "$out" | head -15
  fi
done

echo
if ((FAILURES)); then echo "$FAILURES failure(s)."; exit 1; fi
echo "All script tests passed."
