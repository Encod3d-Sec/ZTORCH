#!/usr/bin/env bash
# Verifier for the engagement-state automation on ZCode.
# Hook registration lives in the COMMITTED <vault>/.zcode/config.json (workspace
# scope, portable via the ${ZCODE_PROJECT_DIR} template var), so unlike the old
# per-device ~/.claude/settings.json installer there is nothing to register per
# machine: this script verifies the registration is intact and runnable.
#
#   bash setup/install-hooks.sh
#
# Idempotent: safe to re-run. Self-locating: works on any user/path.
set -euo pipefail

VAULT="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
CONFIG="$VAULT/.zcode/config.json"
HOOKS_SRC="$VAULT/skills/hooks"

echo "Vault:  $VAULT"
echo "Config: $CONFIG"
echo "Hooks:  $HOOKS_SRC"

[ -d "$HOOKS_SRC" ] || { echo "ERROR: $HOOKS_SRC missing (vault code not synced here?)"; exit 1; }
[ -f "$CONFIG" ] || { echo "ERROR: $CONFIG missing. Repair: git restore .zcode/config.json"; exit 1; }

# Interpreters must exist: every hook command invokes python3 or bash.
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not on PATH (ZCode hook commands need it)"; exit 1; }
# bash is optional on this seat: only setup/install-skills.sh (called by session-start.py,
# fail-open) and win-vm.sh need it; hooks themselves are python3.

python3 - "$CONFIG" "$HOOKS_SRC" <<'PY'
import json, os, re, sys

config_path, hooks_src = sys.argv[1], sys.argv[2]
present = set(os.listdir(hooks_src))
ZCODE_EVENTS = {"SessionStart", "UserPromptSubmit", "PreToolUse",
                "PermissionRequest", "PostToolUse", "PostToolUseFailure", "Stop"}
# Canonical expected set: (event, script basename). Must match scripts/check-hooks.py.
EXPECTED = [
    ("SessionStart", "engagement-init.py"),
    ("SessionStart", "session-start.py"),
    ("UserPromptSubmit", "hunt-trigger.py"),
    ("PostToolUse", "recon-capture.py"),
    ("PostToolUse", "capture-poc.py"),
    ("PostToolUse", "tool-telemetry.py"),
    ("PostToolUse", "wiki-reindex.py"),
    ("PreToolUse", "scope-guard.py"),
    ("PreToolUse", "sleep-guard.py"),
    ("PreToolUse", "session-guard.py"),
    ("PreToolUse", "drift-guard.py"),
    ("Stop", "close-out.py"),
]

try:
    with open(config_path, encoding="utf-8") as f:
        cfg = json.load(f)
except Exception as e:
    print("ERROR: .zcode/config.json is not valid JSON: %s" % e)
    print("Repair: git restore .zcode/config.json")
    sys.exit(1)

hooks = cfg.get("hooks") or {}
if not hooks.get("enabled"):
    print("ERROR: hooks.enabled is not true -- configuration-file hooks are disabled by default.")
    sys.exit(1)

events = hooks.get("events") or {}
registered = {}   # basename -> event
bad = []
for event, groups in events.items():
    if event not in ZCODE_EVENTS:
        bad.append("unsupported event %r (ZCode supports exactly: %s)"
                   % (event, ", ".join(sorted(ZCODE_EVENTS))))
        continue
    for g in groups if isinstance(groups, list) else []:
        matcher = g.get("matcher")
        if matcher is not None:
            try:
                re.compile(matcher)
            except re.error:
                bad.append("invalid matcher regex %r on %s (never matches)" % (matcher, event))
        for hk in g.get("hooks", []):
            cmd = hk.get("command", "") if isinstance(hk, dict) else ""
            for token in cmd.split():
                if "skills/hooks/" in token:
                    name = token.replace("${ZCODE_PROJECT_DIR}", "").strip("\"'").rsplit("/", 1)[-1]
                    if name not in present:
                        bad.append("%s registered but skills/hooks/%s is missing" % (name, name))
                    registered.setdefault(name, event)

rc = 0
missing = [(e, n) for e, n in EXPECTED if n not in registered]
if missing:
    print("Missing from .zcode/config.json: " + ", ".join(n for _e, n in missing))
    print("Repair: git restore .zcode/config.json")
    rc = 1
else:
    print("all %d vault hooks registered" % len(EXPECTED))
for msg in bad:
    print("PROBLEM: " + msg)
    rc = 1
if not bad and not missing:
    print("hook scripts present, events + matchers valid, hooks.enabled: true")
sys.exit(rc)
PY

echo "Done. Restart ZCode (or start a new session) if you just changed .zcode/config.json."
