"""W2-adjacent (Wave 4): .zcode/config.json is ZCode's committed, direct hook registration --
the parallel of ~/.claude/settings.json for the Claude Code seat. It should carry the same
(event, script_basename) pairs as scripts/check-hooks.py's canonical EXPECTED_HOOKS list, with a
ZCode-appropriate interpreter (bash for .sh scripts, python3 for .py scripts) and the
${ZCODE_PROJECT_DIR} path prefix. Regression test for: a stale session-start.py reference (should
be session-start.sh, run via bash) and a missing PreCompact/pre-compact.sh entry."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import importlib.util

# scripts/check-hooks.py has a hyphen in its filename, so it can't be `import`ed directly.
_spec = importlib.util.spec_from_file_location(
    "check_hooks", str(ROOT / "scripts" / "check-hooks.py"))
check_hooks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_hooks)


def _zcode_hook_pairs():
    """(event, script_basename) pairs actually registered in .zcode/config.json."""
    d = json.loads((ROOT / ".zcode" / "config.json").read_text())
    pairs = set()
    for event, groups in d.get("hooks", {}).get("events", {}).items():
        for g in groups:
            for h in g.get("hooks", []):
                cmd = h.get("command", "")
                base = cmd.rsplit("/", 1)[-1].rstrip('"')
                pairs.add((event, base))
    return pairs


def test_zcode_config_matches_expected_hooks():
    zcode_pairs = _zcode_hook_pairs()
    expected = set(check_hooks.EXPECTED_HOOKS)
    missing = expected - zcode_pairs
    assert not missing, (
        f".zcode/config.json is missing hooks that scripts/check-hooks.py's EXPECTED_HOOKS "
        f"requires: {sorted(missing)}")


def test_zcode_config_session_start_uses_bash_and_sh():
    d = json.loads((ROOT / ".zcode" / "config.json").read_text())
    session_start_cmds = [
        h.get("command", "")
        for g in d["hooks"]["events"].get("SessionStart", [])
        for h in g.get("hooks", [])
    ]
    matching = [c for c in session_start_cmds if "session-start" in c]
    assert matching, "no session-start hook found in .zcode/config.json SessionStart"
    assert all(c.startswith("bash ") and c.rstrip('"').endswith("session-start.sh")
               for c in matching), (
        f"session-start hook must run via bash against the .sh file, got: {matching}")
