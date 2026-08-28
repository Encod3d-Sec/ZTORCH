#!/usr/bin/env bash
# fleet-lane.sh <lane> <promptfile> - launch one GLM fleet subprocess, output-isolated.
# Runs from vault cwd so the subprocess inherits AGENTS.md + hunt skills + scope-guard hook.
# Output dir derives from the active engagement (targets/active.md) - no codename in this file.
set -u
VAULT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
lane="${1:?lane}"; pf="${2:?promptfile}"
cd "$VAULT" || exit 1
eng="$(head -1 targets/active.md | tr -d '[:space:]')"
out="targets/${eng}/ingest/fleet/${lane}.log"
: > "$out"
# Headless ZCode CLI. The binary name / flags vary by install (desktop app vs CLI
# package) - override with FLEET_ZCODE / FLEET_ARGS if yours differs. Check
# `zcode --help` for the headless/print mode + permission bypass flags of your build.
command -v "${FLEET_ZCODE:-zcode}" >/dev/null 2>&1 || {
  echo "ERROR: no ZCode CLI on PATH (tried '${FLEET_ZCODE:-zcode}'). Set FLEET_ZCODE." >> "$out"
  exit 1
}
IS_SANDBOX=1 ${FLEET_ZCODE:-zcode} -p ${FLEET_ARGS:-} "$(cat "$pf")" >> "$out" 2>&1
echo "=== LANE ${lane} EXIT $? $(date -u +%FT%TZ) ===" >> "$out"
