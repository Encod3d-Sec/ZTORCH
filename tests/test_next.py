"""Tests for offensive.py `next` (cursor + gate walk + method block)."""
import json
import os
import shutil
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import offensive  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "offensive"


def _setup(tmp_path):
    """Copy the FIXTURE vault (populated method blocks), init a bb engagement,
    build the index. Returns (vault, eng)."""
    vault = tmp_path / "vault"
    (vault / "targets").mkdir(parents=True)
    for sub in ("skills", "wiki"):
        shutil.copytree(FIX / sub, vault / sub)
    offensive.main(["--vault", str(vault), "init", "demo", "--type", "bb"])
    eng = vault / "targets" / "demo"
    offensive.build_index(eng, vault)
    return vault, eng


def _row(**kw):
    base = {"id": "", "asset": "", "vuln class": "", "arsenal": "",
            "skill": "", "tool": "", "status": "[ ]", "poc": "", "poc_kind": ""}
    base.update(kw)
    return base


def _next_out(capsys, vault, eng):
    rc = offensive.main(["--vault", str(vault), "--eng", str(eng), "next"])
    return rc, capsys.readouterr().out


def test_g1_withholds_when_arsenal_empty(tmp_path, capsys):
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1", **{"vuln class": "ssrf"},
                                     arsenal="", skill="hunt-ssrf", tool="nuclei")])
    rc, out = _next_out(capsys, vault, eng)
    assert rc == 0
    assert "Skill(wiki-arsenal) ssrf" in out
    assert "nuclei" not in out          # tool withheld
    assert "Skill(hunt-" not in out     # hunt skill withheld


def test_next_persists_last_move(tmp_path, capsys):
    """Compact-boundary discipline (pass 4): the served move is written to
    .offensive.json (row/class/skill/tool/ts) so the pre-compact steer and the
    SessionStart(compact) restore have a durable source, not just context."""
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:2", asset="web1", **{"vuln class": "ssrf"},
                                     arsenal="x", skill="hunt-ssrf", tool="nuclei")])
    _next_out(capsys, vault, eng)
    st = json.loads((eng / ".offensive.json").read_text())
    lm = st.get("last_move")
    assert lm and lm["row"] == "4a:2" and lm["asset"] == "web1"
    assert lm["skill"] == "hunt-ssrf" and lm["tool"] == "nuclei" and lm["ts"]



def test_g2_emits_hunt_skill_when_arsenal_set(tmp_path, capsys):
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1", **{"vuln class": "sqli"},
                                     arsenal="payloads/sqli", skill="hunt-sqli", tool="sqlmap")])
    # oracle present (events file exists) but skill unfired -> G2 enforces
    (eng / ".events.jsonl").write_text("")
    rc, out = _next_out(capsys, vault, eng)
    assert rc == 0
    assert "Skill(hunt-sqli)" in out        # G2 fires (oracle present, skill unfired)
    assert "wiki-arsenal" not in out


def test_next_g2_failopens_without_events(tmp_path, capsys):
    """M1 livelock fix: with the arsenal set, the mapped skill NOT fired, and NO
    .events.jsonl (telemetry hook unwired), G2 must fail-open (mirroring
    cmd_done) and `next` must reach the G8 tool step instead of emitting
    Skill(hunt-*) on every call forever."""
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1", **{"vuln class": "sqli"},
                                     arsenal="payloads/sqli", skill="hunt-sqli", tool="sqlmap")])
    assert not (eng / ".events.jsonl").exists()   # no telemetry oracle
    inv = offensive.load_index(eng)["tools"]["sqlmap"]["invocation"]

    rc1, out1 = _next_out(capsys, vault, eng)
    rc2, out2 = _next_out(capsys, vault, eng)
    assert rc1 == 0 and rc2 == 0
    # G8 tool invocation is reached, NOT a stuck Skill(hunt-*)
    assert inv and inv in out1
    assert "Skill(hunt-sqli)" not in out1
    # two consecutive calls do not both livelock on the same Skill(...) line
    assert "Skill(hunt-sqli)" not in out2
    assert inv in out2

    # WITH an events file lacking the skill, G2 enforcement is UNCHANGED.
    (eng / ".events.jsonl").write_text("")
    _, out3 = _next_out(capsys, vault, eng)
    assert "Skill(hunt-sqli)" in out3
    assert inv not in out3


def test_g8_emits_tool_when_skill_fired(tmp_path, capsys):
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1", **{"vuln class": "sqli"},
                                     arsenal="payloads/sqli", skill="hunt-sqli", tool="sqlmap")])
    # seed the skill-fired event AFTER started_at
    state = json.loads((eng / offensive.STATE_NAME).read_text())
    (eng / ".events.jsonl").write_text(json.dumps(
        {"tool": "Skill", "skill": "hunt-sqli", "ts": state["started_at"]}) + "\n")
    rc, out = _next_out(capsys, vault, eng)
    assert rc == 0
    inv = offensive.load_index(eng)["tools"]["sqlmap"]["invocation"]
    assert inv and inv in out               # G8 tool invocation
    assert "Skill(hunt-sqli)" not in out    # skill already fired -> withheld
    assert "Burp Repeater" in out           # sqli is exploit-shaped


def test_next_includes_method_block(tmp_path, capsys):
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1", **{"vuln class": "sqli"},
                                     arsenal="payloads/sqli", skill="hunt-sqli", tool="sqlmap")])
    _, out = _next_out(capsys, vault, eng)
    method = offensive.load_index(eng)["methods"]["hunt-sqli"]
    assert "APPROACH" in out and method["approach"] in out
    assert "AVOID" in out and method["avoid"] in out
    assert "REFS" in out and method["refs"].split()[0] in out


def test_g9_refuses_on_stale_index(tmp_path, capsys):
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1", **{"vuln class": "sqli"},
                                     arsenal="payloads/sqli", skill="hunt-sqli", tool="sqlmap")])
    # touch a routing source newer than the cache
    src = vault / "skills" / "hunt" / "hunt-core" / "SKILL.md"
    future = time.time() + 10
    os.utime(src, (future, future))
    with pytest.raises(SystemExit) as ex:
        offensive.main(["--vault", str(vault), "--eng", str(eng), "next"])
    assert ex.value.code != 0
    assert "index" in capsys.readouterr().err.lower()


def test_next_never_asks(tmp_path, capsys):
    vault, eng = _setup(tmp_path)
    # all rows closed -> terminal state, must not print a question/menu
    offensive.write_board(eng, [_row(id="4a:1", asset="web1", **{"vuln class": "sqli"},
                                     arsenal="payloads/sqli", skill="hunt-sqli",
                                     tool="sqlmap", status="[x]")])
    _, out = _next_out(capsys, vault, eng)
    assert "?" not in out
    low = out.lower()
    assert "choose" not in low and "which" not in low


def test_g8_scan_class_wraps_vm_scan(tmp_path, capsys):
    """Route+advise: scan-class tool rows emit the vm-scan.sh tmux launch, bare
    invocation still visible."""
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1", **{"vuln class": "recon"},
                                     arsenal="wiki/recon", skill="", tool="nmap")])
    rc, out = _next_out(capsys, vault, eng)
    assert rc == 0
    assert "vm-scan.sh --win nmap demo web1" in out
    assert "nmap <target>" in out            # bare invocation still visible


def test_g8_output_class_wraps_vm_bg(tmp_path, capsys):
    """Route+advise: output-class tool rows emit vm-bg.sh launch + read hint."""
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1", **{"vuln class": "sqli"},
                                     arsenal="payloads/sqli", skill="hunt-sqli", tool="sqlmap")])
    state = json.loads((eng / offensive.STATE_NAME).read_text())
    (eng / ".events.jsonl").write_text(json.dumps(
        {"tool": "Skill", "skill": "hunt-sqli", "ts": state["started_at"]}) + "\n")
    rc, out = _next_out(capsys, vault, eng)
    assert rc == 0
    assert "vm-bg.sh demo sqlmap-web1" in out
    assert "vm-bg.sh --read demo sqlmap-web1" in out


def test_next_parallel_hint_on_two_open_assets(tmp_path, capsys):
    """Default brain posture: 2+ open assets -> the driver names the parallel
    posture (Skill(brain), 2-3 disjoint lanes)."""
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [
        _row(id="4a:1", asset="web1", **{"vuln class": "recon"},
             arsenal="wiki/recon", skill="", tool="nmap"),
        _row(id="4a:2", asset="db1", **{"vuln class": "secrets"},
             arsenal="wiki/secrets", skill="", tool="nuclei"),
    ])
    rc, out = _next_out(capsys, vault, eng)
    assert rc == 0
    assert "Skill(brain)" in out and "2-3" in out
    # single open asset -> no parallel directive
    offensive.write_board(eng, [_row(id="4a:1", asset="web1", **{"vuln class": "recon"},
                                     arsenal="wiki/recon", skill="", tool="nmap")])
    _, out1 = _next_out(capsys, vault, eng)
    assert "Skill(brain)" not in out1
