#!/usr/bin/env bash
# Self-locate the vault root from this script's real path (ZCode invokes it as
# ${ZCODE_PROJECT_DIR}/skills/hooks/session-start.sh, so ../.. is the vault root).
# Honor explicit overrides first so it works on any user/path/spelling.
VAULT="${ZTORCH_VAULT:-${QMD_VAULT:-${CLAUDEBRAIN_VAULT:-$(cd "$(dirname "$(readlink -f "$0")")/../.." && pwd)}}}"

# Auto-register vault skills so a freshly-authored skill is invocable without a
# manual `setup/install-skills.sh` run. Idempotent (symlinks each skills/*/SKILL.md
# into <vault>/.zcode/skills/, skipping existing); the harness rescans on session start.
# Output suppressed so it never pollutes the context injected below; fails open.
bash "$VAULT/setup/install-skills.sh" >/dev/null 2>&1 || true

# Inject session hot cache into context. ZCode parses hook stdout as strict
# hook JSON, so emit hot.md as SessionStart additionalContext (plain text would
# be discarded by schema validation). Fail open: no hot.md / no python3 -> silence.
HOT="$VAULT/session/hot.md"
if [ -f "$HOT" ] && command -v python3 >/dev/null 2>&1; then
  python3 - "$HOT" <<'PY'
import json, sys
try:
    txt = open(sys.argv[1], encoding="utf-8", errors="replace").read().strip()
except Exception:
    txt = ""
if txt:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                             "additionalContext": txt}}))
PY
fi
exit 0   # fail open: never let a missing hot.md make the SessionStart hook exit non-zero
