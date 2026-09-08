"""Batch 5: board escalate-to-deny. The board-bypass drift (~17x): drift-guard ADVISES the agent
back to the driver and the advice was ignored for whole boxes (85 raw exploit calls observed).
Policy: deterministic guards enforce; streak 1-3/25 stays advisory (a probe is not a pattern),
but streak >= 6 exploit-shaped calls with zero driver contact is no longer a judgement call --
it DENIES, naming the driver step that clears it. Escape hatches: any offensive.py driver call
resets the streak; .enforce-off downgrades to advisory."""
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOOK = ROOT / "skills" / "hooks" / "drift-guard.py"

APPROACH = ("| step | class | tool | status | notes |\n|---|---|---|---|---|\n"
            "| 1 | recon | nuclei | [ ] | x |\n")
STATE = "---\nengagement_type: pentest\n---\n\n" \
        "| target | service | port | access | notes |\n|---|---|---|---|---|\n" \
        "| 10.0.0.5 | http | 80 | port-open | x |\n"
OFFBOARD_CMD = "bash /root/vm.sh 'python3 /tmp/exp.py'"


def _mk(tmp_path, streak, access="port-open", enforce_off=False):
    t = tmp_path / "targets" / "engd"
    t.mkdir(parents=True, exist_ok=True)
    (t / ".offensive.json").write_text(
        json.dumps({"type": "pentest", "pass": 6, "off_board_streak": streak,
                    "emitted_bins": []}), encoding="utf-8")
    (t / "Approach.md").write_text(APPROACH, encoding="utf-8")
    (t / "state.md").write_text(STATE.replace("port-open", access), encoding="utf-8")
    (tmp_path / "targets" / "active.md").write_text("engd\n", encoding="utf-8")
    if enforce_off:
        (tmp_path / ".enforce-off").write_text("", encoding="utf-8")
    return tmp_path


def _run(vault, cmd=OFFBOARD_CMD):
    env = dict(os.environ, ZTORCH_VAULT=str(vault),
               ENFORCE_OFF_MARKER=str(vault / ".enforce-off"))
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
    return subprocess.run([sys.executable, str(HOOK)], input=payload,
                          capture_output=True, text=True, timeout=30, env=env)


def _decoded(r):
    return json.loads(r.stdout) if r.stdout.strip() else {}


def test_low_streak_stays_advisory(tmp_path):
    r = _run(_mk(tmp_path, streak=1))
    out = _decoded(r)
    assert out.get("hookSpecificOutput", {}).get("permissionDecision") is None
    assert "additionalContext" in out.get("hookSpecificOutput", {})


def test_streak_six_denies_with_driver_fix(tmp_path):
    r = _run(_mk(tmp_path, streak=5))          # increments to 6 inside the hook
    out = _decoded(r)["hookSpecificOutput"]
    assert out.get("permissionDecision") == "deny"
    assert "offensive.py" in out.get("permissionDecisionReason", "")


def test_enforce_off_downgrades_deny_to_advisory(tmp_path):
    r = _run(_mk(tmp_path, streak=5, enforce_off=True))
    out = _decoded(r)["hookSpecificOutput"]
    assert out.get("permissionDecision") is None
    assert "additionalContext" in out


def test_post_foothold_never_denies(tmp_path):
    r = _run(_mk(tmp_path, streak=5, access="foothold"))
    out = _decoded(r)
    hso = out.get("hookSpecificOutput", {})
    assert hso.get("permissionDecision") is None    # advisory-only once a foothold exists
    # streak is 6 (not 1) and post-foothold advice fires only once -> silent allow
    assert "additionalContext" not in hso


def test_driver_call_resets_streak(tmp_path):
    v = _mk(tmp_path, streak=5)
    _run(v, cmd="python3 scripts/offensive.py next")
    st = json.loads((v / "targets" / "engd" / ".offensive.json").read_text())
    assert st["off_board_streak"] == 0
