#!/usr/bin/env bash
# ZTORCH hermes lane wrapper: one headless hermes-agent one-shot per dispatched
# lane (hermes -z prints ONLY the final response; approvals are auto-bypassed
# inside hermes, so the seat skill's no-live-target rule is the safety floor).
# Seat config comes from setup/hermes-seat-init.sh (isolated HERMES_HOME).
# Usage: bash scripts/hermes.sh '<prompt>' [--tier haiku|sonnet|opus]
#                                  [--dir <workdir>] [--capture <dir>]
#                                  [--toolsets a,b] [check]
#   check              static seat checks only (no API spend)
# Env: ZTORCH_HERMES_HOME (default ~/.hermes-ztorch), ZTORCH_HERMES_PY (python
#      that runs the clone; default: newest ~/.hermes/tools/python-*/bin/python3),
#      HERMES_BIN (fallback binary when no clone checkout exists)
# Exit codes mirror hermes -z: 0 ok, 1 empty, 2 failed/partial, 130 interrupted.
set -uo pipefail
VAULT="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
HOME_DIR="${ZTORCH_HERMES_HOME:-$HOME/.hermes-ztorch}"
CLONE="$VAULT/raw/git/hermes-agent"

PYBIN="${ZTORCH_HERMES_PY:-}"
if [ -z "$PYBIN" ]; then
  for c in "$HOME"/.hermes/tools/python-*/bin/python3; do [ -x "$c" ] && PYBIN="$c"; done
fi

# The published ~/.local/bin/hermes shim runs python -I (isolated: user-site
# stripped), which cannot see the checkout's deps; drive the clone directly.
run_hermes() {
  if [ -n "$PYBIN" ] && [ -d "$CLONE/hermes_cli" ]; then
    (cd "$CLONE" && env -u ANTHROPIC_BASE_URL -u ANTHROPIC_AUTH_TOKEN \
      HERMES_HOME="$HOME_DIR" "$PYBIN" -c \
      "from hermes_cli.main import main; import sys; sys.exit(main())" "$@")
  else
    HERMES_HOME="$HOME_DIR" "${HERMES_BIN:-hermes}" "$@"
  fi
}

TIER=haiku; DIR="$PWD"; CAPTURE=""; TOOLSETS="file,search,skills,web,todo"
while [ $# -gt 0 ]; do
  case "$1" in
    check)
      if ! { [ -n "$PYBIN" ] || [ -x "$(command -v "${HERMES_BIN:-hermes}")" ]; }; then
        echo "FAIL: no hermes runtime (clone python or HERMES_BIN)" >&2; exit 2; fi
      [ -f "$HOME_DIR/config.yaml" ] || { echo "FAIL: no seat config at $HOME_DIR/config.yaml (run setup/hermes-seat-init.sh)" >&2; exit 2; }
      grep -q 'ztorch-gw' "$HOME_DIR/config.yaml" || { echo "FAIL: provider ztorch-gw missing from seat config" >&2; exit 2; }
      grep -q '^ZTORCH_HERMES_KEY=' "$HOME_DIR/.env" 2>/dev/null || { echo "FAIL: ZTORCH_HERMES_KEY not set in $HOME_DIR/.env" >&2; exit 2; }
      EXTD="$(grep -A2 'external_dirs' "$HOME_DIR/config.yaml" | grep -oE '/[^"]+/skills' | head -1)"
      [ -n "$EXTD" ] && [ -d "$EXTD" ] || { echo "FAIL: skills external_dirs not a dir: $EXTD" >&2; exit 2; }
      echo "OK: py=${PYBIN:-external-bin} home=$HOME_DIR skills=$EXTD"; exit 0 ;;
    --tier) TIER="$2"; shift 2 ;;
    --dir) DIR="$2"; shift 2 ;;
    --capture) CAPTURE="$2"; shift 2 ;;
    --toolsets) TOOLSETS="$2"; shift 2 ;;
    -*) echo "unknown flag: $1" >&2; exit 2 ;;
    *) PROMPT="$1"; shift ;;
  esac
done
[ -n "${PROMPT:-}" ] || { echo "need a prompt (see header usage)" >&2; exit 2; }
case "$TIER" in haiku|sonnet|opus) ;; *) echo "bad tier: $TIER (haiku|sonnet|opus)" >&2; exit 2 ;; esac
[ -d "$DIR" ] || { echo "bad --dir: $DIR" >&2; exit 2; }

USAGE_ARGS=()
if [ -n "$CAPTURE" ]; then
  mkdir -p "$CAPTURE"
  USAGE_ARGS=(--usage-file "$CAPTURE/usage.json")
fi
case "$TIER" in
  haiku) MODEL="glm-5.3-flash" ;;
  sonnet) MODEL="glm-5.3" ;;
  opus) MODEL="glm-5.3" ;;  # glm-5.3-max rejected by the gateway wire
esac
if [ -n "$CAPTURE" ]; then
  run_hermes -z "$PROMPT" -m "$MODEL" --provider ztorch-gw --in "$DIR" \
    -t "$TOOLSETS" --accept-hooks "${USAGE_ARGS[@]}" | tee "$CAPTURE/response.md"
  exit "${PIPESTATUS[0]}"
fi
run_hermes -z "$PROMPT" -m "$MODEL" --provider ztorch-gw --in "$DIR" \
  -t "$TOOLSETS" --accept-hooks "${USAGE_ARGS[@]}"
exit $?
