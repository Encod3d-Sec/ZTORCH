"""Tuple-diff drift in missing_hooks(): a hook registered under the WRONG event
must fail like a missing one, naming the expected vs found event. The old
presence-only match (basename anywhere in any command) let e.g. a PostToolUse
scope-guard pass while the canonical registration is PreToolUse."""
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


def _write_settings(tmp_path, hooks):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"hooks": hooks}))
    return str(p)


def test_wrong_event_registration_fails_like_missing(tmp_path):
    hooks = {}
    for event, base in check_hooks.EXPECTED_HOOKS:
        if base == "scope-guard.py":
            event = "PostToolUse"  # canonical event is PreToolUse
        hooks.setdefault(event, []).append(
            {"hooks": [{"command": "python3 ~/.claude/vault-hooks/%s" % base}]})
    problems = check_hooks.missing_hooks(settings_path=_write_settings(tmp_path, hooks))
    assert problems == ["scope-guard.py (expected PreToolUse, registered under PostToolUse)"]

    # and with it back on the canonical event, the same fixture is fully clean
    hooks["PostToolUse"] = [g for g in hooks["PostToolUse"]
                            if "scope-guard.py" not in json.dumps(g)]
    hooks.setdefault("PreToolUse", []).append(
        {"hooks": [{"command": "python3 ~/.claude/vault-hooks/scope-guard.py"}]})
    assert check_hooks.missing_hooks(settings_path=_write_settings(tmp_path, hooks)) == []
