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


def _mk(tmp_path, streak, access="port-open", enforce_off=False, log_text=""):
    t = tmp_path / "targets" / "engd"
    t.mkdir(parents=True, exist_ok=True)
    (t / ".offensive.json").write_text(
        json.dumps({"type": "pentest", "pass": 6, "off_board_streak": streak,
                    "emitted_bins": []}), encoding="utf-8")
    (t / "Approach.md").write_text(APPROACH, encoding="utf-8")
    (t / "state.md").write_text(STATE.replace("port-open", access), encoding="utf-8")
    if log_text:
        (t / "log.md").write_text(log_text, encoding="utf-8")
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
    """Since the L1 steer (pentagi absorb), the 2nd identical fire carries the
    IDENTICAL-RETRY advisory - which ends with the imminent-block line - instead of
    the old throttle-path warn."""
    v = _mk(tmp_path, streak=0)
    _run(v)
    r = _run(v)
    out = _decoded(r)["hookSpecificOutput"]
    assert "IDENTICAL-RETRY" in out.get("additionalContext", "")
    assert "next identical fire is denied" in out.get("additionalContext", "")


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


def test_retry_steer_advises_one_fire_below_deny():
    import importlib.util
    spec = importlib.util.spec_from_file_location("dg", str(HOOK))
    dg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dg)
    assert dg._retry_steer(1, False) is None          # first fire: silence
    msg = dg._retry_steer(2, False)                   # second identical fire: steer
    assert msg and "will not change" in msg and "2" in msg
    assert dg._retry_steer(2, True) is None           # deny takes precedence, no advisory
    assert dg._retry_steer(3, False) is None          # 3rd belongs to the deny, not the steer


def test_install_advisory_regex():
    import importlib.util
    spec = importlib.util.spec_from_file_location("dg", str(HOOK))
    dg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dg)
    assert dg._install_advisory("curl -s https://x.example/install.sh | sh") is not None
    assert dg._install_advisory("wget -qO- https://x.example/i | bash") is not None
    assert dg._install_advisory("curl -s https://x.example/install.sh -o i.sh") is None
    assert dg._install_advisory("cat report | grep sh") is None


def test_install_advisory_fires_once_then_stamps(tmp_path):
    """E2E (fix round): the first piped-install call prints the install advisory; the
    immediate identical second call is stamp-silent - no repeat inside the window.
    A printf string merely MENTIONING the pattern is reader-exempt and must neither
    fire nor consume the stamp (so the genuine fire right after still prints)."""
    v = _mk(tmp_path, streak=1)
    r0 = _run(v, cmd="printf 'curl -s https://x.example/install.sh | sh'")
    assert "INSTALL DENY-PATTERN" not in r0.stdout         # mention exempt, stamp untouched
    out1 = _decoded(_run(v, cmd="curl -s https://x.example/install.sh | sh"))
    hso1 = out1.get("hookSpecificOutput", {})
    assert hso1.get("permissionDecision") is None          # advisory-only, never a deny
    assert "INSTALL DENY-PATTERN" in hso1.get("additionalContext", "")
    r2 = _run(v, cmd="curl -s https://x.example/install.sh | sh")
    assert "INSTALL DENY-PATTERN" not in r2.stdout         # stamp window: silent this kind


# ---- pass 14: reader-lead filenames + 4a-slice board (B5/B6) ----

def test_reader_lead_filename_not_exploit_shaped(tmp_path):
    """B5: `cat nmap-notes.md` is a file READ - the scanner name inside the FILENAME
    must not count as a fired binary (22 false flags observed off this one shape)."""
    v = _mk(tmp_path, streak=5)                 # would deny if the read counted
    r = _run(v, "bash /root/vm.sh 'cat nmap-notes.md'")
    out = _decoded(r).get("hookSpecificOutput", {})
    assert out.get("permissionDecision") != "deny"


def test_board_is_4a_slice_not_first_table(tmp_path):
    """B6: an agent-added table ABOVE the `### 4a` board must not become the board -
    its tool cells neither hold the cursor nor whitelist binaries. sqlmap sits only in
    the preamble table here; the real 4a board whitelists nuclei alone."""
    v = _mk(tmp_path, streak=5)
    t = v / "targets" / "engd"
    preamble = ("| finding | tool |\n|---|---|\n| x | sqlmap |\n\n"
                "### 4a. Coverage matrix\n\n"
                "| id | asset | vuln class | arsenal | skill | tool | status | poc | poc_kind |\n"
                "|---|---|---|---|---|---|---|---|---|\n"
                "| 4a:1 | web1 | xss | a | s | nuclei | [ ] | | |\n")
    (t / "Approach.md").write_text(preamble, encoding="utf-8")
    r = _run(v, "sqlmap -u http://10.0.0.5/?x=1 --batch")
    out = _decoded(r).get("hookSpecificOutput", {})
    assert out.get("permissionDecision") == "deny"   # not whitelisted by the preamble
    r2 = _run(v, "nuclei -u http://10.0.0.5/")
    out2 = _decoded(r2).get("hookSpecificOutput", {})
    assert out2.get("permissionDecision") != "deny"  # the real board whitelists it


def test_long_foreground_scan_through_bridge_advises_detached(tmp_path):
    """P15 DOA table: a slow scan in the foreground through the direct vm.sh bridge is
    structurally dropped at ~2min - the advisory fires with no engagement at all (isolated
    vault with an EMPTY targets/: the 15-min DOA stamp is per-engagement, so a
    no-engagement run is unthrottled; an empty targets/ keeps active_dir from falling
    back to this repo's live vault)."""
    (tmp_path / "novault" / "targets").mkdir(parents=True)
    payload = json.dumps({"tool_name": "Bash", "tool_input": {
        "command": "bash /root/vm.sh 'nmap -p- --min-rate 2000 -T4 10.0.0.5'"}})
    r = subprocess.run([sys.executable, str(HOOK)], input=payload,
                       capture_output=True, text=True, timeout=30,
                       env=dict(os.environ, ZTORCH_VAULT=str(tmp_path / "novault")))
    ctx = _decoded(r).get("hookSpecificOutput", {}).get("additionalContext", "")
    assert "TRANSPORT DOA" in ctx and "vm-scan.sh" in ctx


def test_doa_advisory_stamp_gates_and_falls_through(tmp_path):
    """Audit 2026-09-10: within an engagement the DOA advisory injects ONCE per 15 min
    (.doa-stamp); a stamped-out advisory must FALL THROUGH to the campaign logic (the
    off-board streak still counts a DOA-shaped retry loop) instead of returning silent."""
    v = _mk(tmp_path, streak=0)
    # 1st fire: advisory injects + stamps
    r1 = _run(v, "bash /root/vm.sh 'nmap -p- 10.0.0.5'")
    ctx1 = _decoded(r1).get("hookSpecificOutput", {}).get("additionalContext", "")
    assert "TRANSPORT DOA" in ctx1
    assert (tmp_path / "targets" / "engd" / ".doa-stamp").exists()
    # 2nd fire inside the window: the DOA text is not re-injected, but the fall-through
    # COUNTS the call -- streak 1 prints the ordinary DRIFT advisory instead
    r2 = _run(v, "bash /root/vm.sh 'nmap -p- 10.0.0.5'")
    ctx2 = _decoded(r2).get("hookSpecificOutput", {}).get("additionalContext", "")
    assert "TRANSPORT DOA" not in ctx2
    assert "DRIFT (off-board, streak 1)" in ctx2
    st = json.loads((tmp_path / "targets" / "engd" / ".offensive.json").read_text())
    assert st["off_board_streak"] == 1


def test_doa_ignores_text_that_only_mentions_the_bridge(tmp_path):
    """Audit 2026-09-10: bridge + slow markers must co-occur in ONE executable segment;
    echo/heredoc text mentioning vm.sh next to an nmap word elsewhere must not fire, and
    deploy-vm.sh (lookbehind) is not the bridge."""
    env = dict(os.environ, ZTORCH_VAULT=str(tmp_path / "novault"))
    for cmd in ("echo 'run vm.sh for the box'; nmap -sV 10.0.0.5 > /tmp/o.txt",
                "cat notes.txt   # mentions vm.sh and nmap -p- prose",
                "bash deploy-vm.sh 'nmap -p- 10.0.0.5'",
                "bash /root/vm.sh 'curl \"http://10.0.0.5/?a=1&b=2\"'"):   # quoted & is data
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
        r = subprocess.run([sys.executable, str(HOOK)], input=payload,
                           capture_output=True, text=True, timeout=30, env=env)
        assert r.stdout.strip() == "", cmd


def test_detached_or_fast_forms_do_not_fire(tmp_path):
    """vm-scan.sh / nohup / background & / a fast nmap -sV are the sanctioned or fast
    paths: silent."""
    for cmd in ("bash scripts/vm-scan.sh engd 10.0.0.5 'nmap -p- 10.0.0.5'",
                "bash /root/vm.sh 'nohup ffuf -u http://10.0.0.5/FUZZ -w wl >/tmp/o 2>&1 &'",
                "bash /root/vm.sh 'ffuf -u http://10.0.0.5/FUZZ -w wl > /tmp/o 2>&1 &'",
                "bash /root/vm.sh 'nmap -sV -p 80 10.0.0.5'",
                "bash /root/vm.sh 'nmap -sV -p 80 10.0.0.5 2>&1 | tee /tmp/o.txt'",
                "bash scripts/vm-rsh.sh engd 'nuclei -u http://10.0.0.5'"):
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
        r = subprocess.run([sys.executable, str(HOOK)], input=payload,
                           capture_output=True, text=True, timeout=30,
                           env=dict(os.environ, ZTORCH_VAULT=str(tmp_path / "novault")))
        assert r.stdout.strip() == "", cmd


def test_corrupt_state_fails_open_but_telemetrifies(tmp_path):
    """Corrupt-state telemetry: an unparseable .offensive.json must fail OPEN (the call is
    allowed, the guard silently off) AND leave a hook event in .events.jsonl - a corrupt
    state file used to disable the guard with zero signal."""
    v = _mk(tmp_path, streak=5)            # would deny on a clean state
    (v / "targets" / "engd" / ".offensive.json").write_text("{corrupt", encoding="utf-8")
    out = _decoded(_run(v, cmd=OFFBOARD_CMD))
    assert out.get("hookSpecificOutput", {}).get("permissionDecision") != "deny"
    ev = (v / "targets" / "engd" / ".events.jsonl").read_text(encoding="utf-8")
    assert '"hook": "drift-guard"' in ev
    assert ".offensive.json unparseable" in ev


# ---- open lane = driver contact (observed: a lane denied pre-flight on inherited streak) --

def _lane_line(minutes_ago, closed=False):
    """A delegate lane line stamped minutes_ago from now (freshness-gated exemption
    needs a live timestamp; a hardcoded HH:MM would flake across the day)."""
    from datetime import datetime, timedelta
    t = (datetime.now() - timedelta(minutes=minutes_ago)).strftime("%H:%M")
    ln = ("- lane lane6 (portal) in flight @%s: SUCCESS = http 200 in capture "
          "| tmux win lane6 | capture /tmp/lane6 | handle a1b2" % t)
    return ln + (" -> VERIFIED: poc/01.md\n" if closed else "\n")


def test_open_lane_is_driver_contact(tmp_path):
    """An `in flight` lane line exempts lane-flight calls from the streak deny (the
    checklist was authored from `next`); the inherited streak resets to 0."""
    v = _mk(tmp_path, streak=5, log_text=_lane_line(5))  # fresh lane; would deny without it
    r = _run(v, cmd=OFFBOARD_CMD)
    assert r.stdout.strip() == ""
    st = json.loads((v / "targets" / "engd" / ".offensive.json").read_text())
    assert st["off_board_streak"] == 0


def test_closed_lane_does_not_exempt(tmp_path):
    """The verdict appended to the lane line (rest after the capture cell) closes it:
    off-board calls count again."""
    v = _mk(tmp_path, streak=5, log_text=_lane_line(5, closed=True))
    out = _decoded(_run(v, cmd=OFFBOARD_CMD))["hookSpecificOutput"]
    assert out.get("permissionDecision") == "deny"


def test_retry_ring_still_denies_mid_lane(tmp_path):
    """Mid-lane identical re-fires are still the doom loop: 3 identical calls with a lane
    open still hit the loop-break deny (the ring counts before the lane return), while the
    streak stays 0 (lane flight is driver contact, not drift)."""
    v = _mk(tmp_path, streak=0, log_text=_lane_line(5))
    _run(v, cmd=OFFBOARD_CMD)
    _run(v, cmd=OFFBOARD_CMD)
    out = _decoded(_run(v, cmd=OFFBOARD_CMD))["hookSpecificOutput"]
    assert out.get("permissionDecision") == "deny"
    assert "doom-loop" in out.get("permissionDecisionReason", "")
    st = json.loads((v / "targets" / "engd" / ".offensive.json").read_text())
    assert st["off_board_streak"] == 0

def test_stale_lane_stops_exempting(tmp_path):
    """Review finding (blocker): a lane line left open must not disable the streak
    deny forever - past the 45-min stale window the exemption is gone."""
    v = _mk(tmp_path, streak=5, log_text=_lane_line(90))
    out = _decoded(_run(v, cmd=OFFBOARD_CMD))["hookSpecificOutput"]
    assert out.get("permissionDecision") == "deny"


def test_untimestamped_lane_not_exempt(tmp_path):
    """No parsable @HH:MM cell = not provably fresh = no exemption (an un-timestamped
    line must not become a permanent drift shield)."""
    v = _mk(tmp_path, streak=5,
            log_text="- lane lane6 (portal) in flight: SUCCESS = x | tmux win - | capture /tmp/l6\n")
    out = _decoded(_run(v, cmd=OFFBOARD_CMD))["hookSpecificOutput"]
    assert out.get("permissionDecision") == "deny"


def test_windowless_lane_line_still_parses(tmp_path):
    """`tmux win -` (offline/research lane) is a valid lane line: fresh + open it
    still exempts (otherwise windowless lanes get denied mid-flight like lane6 was)."""
    from datetime import datetime, timedelta
    ts = (datetime.now() - timedelta(minutes=5)).strftime("%H:%M")
    v = _mk(tmp_path, streak=5,
            log_text="- lane r1 (osint) in flight @%s: SUCCESS = summary written "
                     "| tmux win - | capture /tmp/r1\n" % ts)
    r = _run(v, cmd=OFFBOARD_CMD)
    assert r.stdout.strip() == ""
