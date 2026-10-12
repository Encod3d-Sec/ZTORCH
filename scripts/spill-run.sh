#!/usr/bin/env bash
# spill-run.sh - run a command under a tool-result size budget (hermes port P1).
#
#   scripts/spill-run.sh <cmd> [args...]
#
# At or under ZT_SPILL_BYTES (default 100000) the output passes through unchanged.
# Over it, the FULL output is spilled to targets/<active-eng>/ingest/spill-<slug>-<ts>.out
# and stdout keeps only the FIRST 30% + LAST 30%, joined by ONE [ZT-ELIDE:n/M] pointer
# line (non-prose marker, proposals-prompt-layer P3 style: computed counts, never a
# bare '...'). The wrapped command's exit code propagates.
#
# Fail-open: no engagement dir, OUTPUT_ECON=0, or any spill-path error -> plain
# passthrough of the real output. ZTORCH_VAULT overrides the vault root (tests).
set -u

[ $# -ge 1 ] || { echo "usage: spill-run.sh <cmd> [args...]" >&2; exit 2; }
[ "${OUTPUT_ECON:-1}" = "0" ] && exec "$@"

CAP="${ZT_SPILL_BYTES:-100000}"
VAULT="${ZTORCH_VAULT:-$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)}"
ENG=""
if [ -f "$VAULT/targets/active.md" ]; then
  ENG=$(grep -m1 -Ev '^[[:space:]]*($|#|<|<!--|-|\*)' "$VAULT/targets/active.md" | awk '{print $1}')
fi
if [ -z "$ENG" ] || [ ! -d "$VAULT/targets/$ENG" ]; then
  exec "$@"                                    # fail-open: no engagement, plain passthrough
fi

TMP=$(mktemp) || exec "$@"
trap 'rm -f "$TMP"' EXIT
"$@" > "$TMP" 2>&1
RC=$?
SIZE=$(wc -c < "$TMP" | tr -d '[:space:]')
if [ "$SIZE" -le "$CAP" ]; then
  cat "$TMP"
  exit $RC
fi

ING="$VAULT/targets/$ENG/ingest"
mkdir -p "$ING" 2>/dev/null || { cat "$TMP"; exit $RC; }
SLUG=$(printf '%s' "${1##*/}" | tr -cs 'a-zA-Z0-9' '-' | cut -c1-24)
SLUG=${SLUG#-}; SLUG=${SLUG%-}
[ -n "$SLUG" ] || SLUG=cmd
OUT="$ING/spill-$SLUG-$(date +%s).out"
if ! cp "$TMP" "$OUT" 2>/dev/null; then
  cat "$TMP"                                   # spill failed: never lose the output
  exit $RC
fi

KEEP=$((SIZE * 30 / 100))
OMIT=$((SIZE - 2 * KEEP))
head -c "$KEEP" "$TMP"
printf '\n[ZT-ELIDE:%d/%d bytes elided here; full output (%d B) at %s; not target output; never reproduce or imitate]\n' \
  "$OMIT" "$SIZE" "$SIZE" "$OUT"
tail -c "$KEEP" "$TMP"
exit $RC
