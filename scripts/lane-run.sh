#!/usr/bin/env bash
# Docker-wrapped lane execution (native port of the hermes sandbox baseline; spec:
# docs/port-specs/sandbox-tooling.md). Validates the lane manifest via
# lane_manifest.py, then runs the command in a hardened container: cap-drop ALL +
# DAC_OVERRIDE/CHOWN/FOWNER back, no-new-privileges, pids-limit 512, cpus 2 /
# memory 4g, shm 1g, three tmpfs mounts (/tmp, /var/tmp, /run), --init --rm -i.
# Mounts: vault wiki/ read-only at /ztorch/wiki, engagement cwd rw at /eng
# (-w /eng), manifest mounts appended. Network defaults to none; a lane needing
# egress sets network: true in its manifest (docker-arg injection fails closed).
# Env: only manifest-named vars pass through (values read at run; provider keys
# blocklisted). Output is teed to ingest/lane-<ts>.out, exit code passes through;
# timeout_s (default 600) is enforced via timeout(1). Default image
# kalilinux/kali-rolling, tool-heavy lanes build/pull their own. Docker binary
# missing or daemon unreachable: exit 2 (falling back to raw lane execution is
# the brain's explicit decision, never silent). Usage (from the engagement dir):
#   bash scripts/lane-run.sh <lane-manifest.json> <cmd...>
set -uo pipefail

HERE="$(dirname "$(readlink -f "$0")")"
VAULT="$(dirname "$HERE")"
HELPER="$HERE/lane_manifest.py"
DOCKER_BIN="${DOCKER_BIN:-docker}"   # overridable for tests, like VM_KEY in vm-ssh.sh

if [ $# -lt 2 ]; then
  echo "usage: bash scripts/lane-run.sh <lane-manifest.json> <cmd...>   (run from the engagement dir)" >&2
  exit 2
fi
command -v python3 >/dev/null 2>&1 || { echo "lane-run: python3 not found" >&2; exit 2; }
command -v "$DOCKER_BIN" >/dev/null 2>&1 || { echo "lane-run: docker binary not found ($DOCKER_BIN); raw-execution fallback is the brain's explicit decision, never silent" >&2; exit 2; }
"$DOCKER_BIN" info >/dev/null 2>&1 || { echo "lane-run: docker daemon unreachable; raw-execution fallback is the brain's explicit decision, never silent" >&2; exit 2; }
command -v timeout >/dev/null 2>&1 || { echo "lane-run: timeout(1) not found" >&2; exit 2; }

MANIFEST="$1"
shift

PLAN="$(mktemp)"
python3 "$HELPER" "$MANIFEST" "$PWD" "$VAULT/wiki" >"$PLAN" || { rm -f "$PLAN"; exit 2; }
TIMEOUT_S=""
ENVS=()
ARGS=()
while IFS= read -r line; do
  case "$line" in
    timeout=*) TIMEOUT_S="${line#timeout=}" ;;
    envs=*) IFS=',' read -r -a ENVS <<<"${line#envs=}" ;;
    # advisory P4 cells (per-lane window + budget): consumed by the brain, never
    # docker argv - swallowed here so they cannot reach `docker run`
    window_m=*) ;;
    budget=*) ;;
    *) ARGS+=("$line") ;;
  esac
done <"$PLAN"
rm -f "$PLAN"
[ -n "$TIMEOUT_S" ] || { echo "lane-run: malformed manifest plan (no timeout)" >&2; exit 2; }

for n in "${ENVS[@]}"; do
  [ -n "$n" ] || continue
  [ -n "${!n:-}" ] || { echo "lane-run: manifest env '$n' is not set; refusing to start the lane without it" >&2; exit 2; }
done

mkdir -p ingest
OUT="ingest/lane-$(date +%Y%m%d-%H%M%S)-$$.out"
timeout "$TIMEOUT_S" "$DOCKER_BIN" run "${ARGS[@]}" "$@" | tee "$OUT"
RC=$?
if [ "$RC" -eq 124 ]; then
  echo "lane-run: lane timed out after ${TIMEOUT_S}s; output: $OUT" >&2
elif [ "$RC" -ne 0 ]; then
  echo "lane-run: lane exited $RC; output: $OUT" >&2
fi
exit "$RC"
