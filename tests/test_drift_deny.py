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


def test_driver_mention_does_not_reset_streak(tmp_path):
    """Regression (host-internals pass 1): the reset was a whole-string regex, so a
    command merely MENTIONING the driver (echo/grep text) cleared the off-board streak
    without any real driver contact. Command-position only now (_driver_called)."""
    v = _mk(tmp_path, streak=5)
    r = _run(v, cmd="echo run offensive.py next")
    st = json.loads((v / "targets" / "engd" / ".offensive.json").read_text())
    assert r.stdout.strip() == ""                 # framework-meta: silent either way
    assert st["off_board_streak"] == 5            # a mention is not contact


def test_mixed_meta_and_exploit_counts(tmp_path):
    """Regression (host-internals pass 1): _META_RE matched whole-string, so
    `git status && nmap <target>` was fully exempt (the nmap never counted toward the
    streak). Meta is per-segment now: only the meta part is exempt."""
    v = _mk(tmp_path, streak=5)
    r = _run(v, cmd="git status && nmap -sV 10.0.0.5")
    out = _decoded(r)["hookSpecificOutput"]
    st = json.loads((v / "targets" / "engd" / ".offensive.json").read_text())
    assert out.get("permissionDecision") == "deny"
    assert st["off_board_streak"] > 5             # the nmap segment counted


def test_pure_meta_command_still_exempt(tmp_path):
    """A whole-command framework/dev call keeps its old silent exemption."""
    v = _mk(tmp_path, streak=5)
    r = _run(v, cmd="git status")
    assert r.stdout.strip() == ""
    st = json.loads((v / "targets" / "engd" / ".offensive.json").read_text())
    assert st["off_board_streak"] == 5



# --- pass-6 additions: identical-retry ring (doom-loop break) --------------------------

def test_identical_retry_three_times_denies_as_doom_loop(tmp_path):
    """Same unchanged command 3x: the retry deny fires at streak 3 (< 6), proving the
    loop-break trigger is independent of the streak pattern trigger."""
    v = _mk(tmp_path, streak=0)
    _run(v)
    _run(v)
    r = _run(v)
    out = _decoded(r)["hookSpecificOutput"]
    assert out.get("permissionDecision") == "deny"
    assert "doom-loop" in out.get("permissionDecisionReason", "")
    assert "dead" in out.get("permissionDecisionReason", "")     # names the close-the-row way out


def test_changed_command_avoids_retry_deny(tmp_path):
    """The deny's named way out (change one variable) works: a different script name never
    accumulates on the first key."""
    v = _mk(tmp_path, streak=0)
    _run(v, cmd="bash /root/vm.sh 'python3 /tmp/exp.py'")
    _run(v, cmd="bash /root/vm.sh 'python3 /tmp/exp.py'")
    r = _run(v, cmd="bash /root/vm.sh 'python3 /tmp/exp2.py'")
    out = _decoded(r).get("hookSpecificOutput", {})
    assert out.get("permissionDecision") is None


def test_driver_contact_clears_retry_ring(tmp_path):
    v = _mk(tmp_path, streak=0)
    _run(v)
    _run(v)
    _run(v, cmd="python3 scripts/offensive.py next")
    st = json.loads((v / "targets" / "engd" / ".offensive.json").read_text())
    assert not st.get("retry_counts")             # a re-plan makes later re-runs new attempts


def test_second_identical_run_warns_of_imminent_block(tmp_path):
    v = _mk(tmp_path, streak=0)
    _run(v)
    r = _run(v)
    out = _decoded(r)["hookSpecificOutput"]
    assert "one more identical run is BLOCKED" in out.get("additionalContext", "")


# ---- ring laundering: same-row re-serve does not clear the retry ring (driver audit) ----

DRIVER_CMD = "python3 scripts/offensive.py --eng engd next"

def _mk_ring(tmp_path, retry_counts, driver_row, last_row):
    t = _mk(tmp_path, streak=0)
    sp = t / "targets" / "engd" / ".offensive.json"
    st = json.loads(sp.read_text())
    st.update({"retry_counts": retry_counts, "_driver_row": driver_row,
               "last_move": {"row": last_row}})
    sp.write_text(json.dumps(st))
    return t

def test_same_row_reserve_keeps_ring(tmp_path):
    """tool -> next(same row) -> tool must still accumulate to the 3x deny."""
    v = _mk_ring(tmp_path, {"abc123": 2}, "4a:1", "4a:1")
    r = _run(v, cmd=DRIVER_CMD)
    st = json.loads((v / "targets" / "engd" / ".offensive.json").read_text())
    assert st["off_board_streak"] == 0            # driver contact still resets streak
    assert st["retry_counts"] == {"abc123": 2}    # ring survives a same-row re-serve

def test_new_row_serve_clears_ring(tmp_path):
    v = _mk_ring(tmp_path, {"abc123": 2}, "4a:1", "4a:2")
    r = _run(v, cmd=DRIVER_CMD)
    st = json.loads((v / "targets" / "engd" / ".offensive.json").read_text())
    assert st["retry_counts"] == {}               # board advanced = genuine re-plan
    assert st["_driver_row"] == "4a:2"


def test_budget_over_cap_denies_every_bash_call(tmp_path, monkeypatch):
    """pass 12: ZT_MAX_ENG_USD set + .metrics.json spend_usd over cap -> the deny
    shape on an otherwise CLEAN command (no off-board streak needed). Under cap or
    without the env var -> silent (opt-in only)."""
    v = _mk(tmp_path, streak=0)
    (v / "targets" / "engd" / ".metrics.json").write_text(
        json.dumps({"spend_usd": 4.25}), encoding="utf-8")
    monkeypatch.setenv("ZT_MAX_ENG_USD", "3.00")
    r = _run(v, cmd="ls -la")
    out = _decoded(r)
    assert out.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"
    assert "ZT_MAX_ENG_USD" in out["hookSpecificOutput"]["permissionDecisionReason"]
    monkeypatch.setenv("ZT_MAX_ENG_USD", "9.00")
    assert _decoded(_run(v, cmd="ls -la")) == {}          # under cap -> silent
    monkeypatch.delenv("ZT_MAX_ENG_USD")
    assert _decoded(_run(v, cmd="ls -la")) == {}          # unset -> silent


def test_retry_key_quote_variance_is_same_loop(tmp_path):
    """pass 12: cosmetic quoting variance must not launder the identical-retry
    ring - `curl http://x/f` and `curl 'http://x/f'` are one loop."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("dg", str(HOOK))
    dg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dg)
    assert dg._retry_key("curl http://x/f") == dg._retry_key("curl 'http://x/f'")
    assert dg._retry_key("curl http://x/f") != dg._retry_key("curl http://x/f2")
