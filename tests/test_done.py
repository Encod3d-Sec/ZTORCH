"""Tests for offensive.py `note` + `done` gates (G1/G2/G3) + `park` (G7)."""
import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import offensive  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "offensive"


def _setup(tmp_path):
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


def _fire(eng, skill):
    """Seed a Skill-fired event dated at started_at so G2 passes."""
    state = json.loads((eng / offensive.STATE_NAME).read_text())
    (eng / ".events.jsonl").write_text(json.dumps(
        {"tool": "Skill", "skill": skill, "row": "4a:1",
         "ts": state["started_at"]}) + "\n")


def _run(argv):
    return offensive.main(argv)


# --------------------------------------------------------------------------- note

def test_note_sets_arsenal(tmp_path):
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1",
                                     **{"vuln class": "sqli"}, skill="hunt-sqli",
                                     tool="sqlmap")])
    rc = _run(["--vault", str(vault), "--eng", str(eng), "note", "4a:1",
               "--arsenal", "payloads/sqli"])
    assert rc == 0
    row = offensive.read_board(eng)[0]
    assert row["arsenal"] == "payloads/sqli"       # G1 now satisfied


# --------------------------------------------------------------------------- G1

def test_done_refused_without_arsenal(tmp_path):
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1",
                                     **{"vuln class": "sqli"}, arsenal="",
                                     skill="hunt-sqli", tool="sqlmap")])
    _fire(eng, "hunt-sqli")
    with pytest.raises(SystemExit) as ex:
        _run(["--vault", str(vault), "--eng", str(eng), "done", "4a:1",
              "--poc", "poc/x.png", "--kind", "req"])
    assert ex.value.code != 0


# --------------------------------------------------------------------------- G2

def test_done_refused_without_skill_fired(tmp_path, capsys):
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1",
                                     **{"vuln class": "sqli"},
                                     arsenal="payloads/sqli", skill="hunt-sqli",
                                     tool="sqlmap")])
    # events file EXISTS (oracle present) but the skill never fired -> refuse
    (eng / ".events.jsonl").write_text("")
    with pytest.raises(SystemExit) as ex:
        _run(["--vault", str(vault), "--eng", str(eng), "done", "4a:1",
              "--poc", "poc/x.png", "--kind", "req"])
    assert ex.value.code != 0
    # seed the event -> now it passes
    _fire(eng, "hunt-sqli")
    rc = _run(["--vault", str(vault), "--eng", str(eng), "done", "4a:1",
               "--poc", "poc/x.png", "--kind", "req"])
    assert rc == 0
    assert offensive.read_board(eng)[0]["status"] == "[x]"


def test_g2_same_second_skill_fire_passes(tmp_path):
    """started_at and event ts share full-precision +00:00 format (offensive.py
    G2 correctness fix): an event fired in the SAME wall-clock second as
    started_at, microseconds later, must still satisfy G2 under a
    lexicographic string compare. An event BEFORE started_at must still fail."""
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1",
                                     **{"vuln class": "sqli"},
                                     arsenal="payloads/sqli", skill="hunt-sqli",
                                     tool="sqlmap")])
    state = json.loads((eng / offensive.STATE_NAME).read_text())
    started = datetime.fromisoformat(state["started_at"])
    assert started.utcoffset() == timezone.utc.utcoffset(None)  # full +00:00 form, not "Z"

    # event BEFORE started_at -> G2 must still refuse
    before_ts = (started - timedelta(seconds=1)).isoformat()
    (eng / ".events.jsonl").write_text(json.dumps(
        {"tool": "Skill", "skill": "hunt-sqli", "row": "4a:1", "ts": before_ts}) + "\n")
    with pytest.raises(SystemExit) as ex:
        _run(["--vault", str(vault), "--eng", str(eng), "done", "4a:1",
              "--poc", "poc/x.png", "--kind", "req"])
    assert ex.value.code != 0

    # event in the SAME second as started_at, microseconds later -> G2 passes
    same_second_ts = (started + timedelta(microseconds=1)).isoformat()
    (eng / ".events.jsonl").write_text(json.dumps(
        {"tool": "Skill", "skill": "hunt-sqli", "row": "4a:1", "ts": same_second_ts}) + "\n")
    rc = _run(["--vault", str(vault), "--eng", str(eng), "done", "4a:1",
               "--poc", "poc/x.png", "--kind", "req"])
    assert rc == 0
    assert offensive.read_board(eng)[0]["status"] == "[x]"


# --------------------------------------------------------------------------- G3

def test_done_refused_without_typed_evidence(tmp_path):
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1",
                                     **{"vuln class": "sqli"},
                                     arsenal="payloads/sqli", skill="hunt-sqli",
                                     tool="sqlmap")])
    _fire(eng, "hunt-sqli")
    # no disposition at all -> refuse
    with pytest.raises(SystemExit) as ex:
        _run(["--vault", str(vault), "--eng", str(eng), "done", "4a:1"])
    assert ex.value.code != 0
    # a 'web' render for a non-visual class (sqli) -> refuse
    with pytest.raises(SystemExit) as ex2:
        _run(["--vault", str(vault), "--eng", str(eng), "done", "4a:1",
              "--poc", "poc/x.png", "--kind", "web"])
    assert ex2.value.code != 0


# --------------------------------------------------------------------------- poc happy path

def test_done_poc_marks_row_x(tmp_path):
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1",
                                     **{"vuln class": "sqli"},
                                     arsenal="payloads/sqli", skill="hunt-sqli",
                                     tool="sqlmap")])
    _fire(eng, "hunt-sqli")
    rc = _run(["--vault", str(vault), "--eng", str(eng), "done", "4a:1",
               "--poc", "poc/sqli.png", "--kind", "req"])
    assert rc == 0
    row = offensive.read_board(eng)[0]
    assert row["status"] == "[x]"
    assert row["poc"] == "poc/sqli.png"
    assert row["poc_kind"] == "req"


# --------------------------------------------------------------------------- dead

def test_done_dead_advances_cursor(tmp_path, capsys):
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [
        _row(id="4a:1", asset="web1", **{"vuln class": "sqli"},
             arsenal="payloads/sqli", skill="hunt-sqli", tool="sqlmap"),
        _row(id="4a:2", asset="web2", **{"vuln class": "ssrf"},
             arsenal="payloads/ssrf", skill="hunt-ssrf", tool="nuclei"),
    ])
    rc = _run(["--vault", str(vault), "--eng", str(eng), "done", "4a:1", "--dead"])
    assert rc == 0
    rows = offensive.read_board(eng)
    assert rows[0]["status"] == "[!]"
    de = (eng / "Deadends.md").read_text()
    assert "web1" in de and "sqli" in de           # asset + class line
    # cursor advances to the other asset
    capsys.readouterr()
    offensive.main(["--vault", str(vault), "--eng", str(eng), "next"])
    out = capsys.readouterr().out
    assert "web2" in out


# --------------------------------------------------------------------------- park (G7)

def test_park_writes_decision_and_advances(tmp_path, capsys):
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [
        _row(id="4a:1", asset="web1", **{"vuln class": "sqli"},
             arsenal="payloads/sqli", skill="hunt-sqli", tool="sqlmap"),
        _row(id="4a:2", asset="web2", **{"vuln class": "ssrf"},
             arsenal="payloads/ssrf", skill="hunt-ssrf", tool="nuclei"),
    ])
    rc = _run(["--vault", str(vault), "--eng", str(eng), "done", "4a:1",
               "--park", "needs client sign-off before active exploitation"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "?" not in out                          # G7: no question printed
    dec = (eng / "decisions.md").read_text()
    assert "4a:1" in dec and "client sign-off" in dec
    rows = offensive.read_board(eng)
    assert rows[0]["status"] not in ("[x]", "[!]")  # row left open (parked, revisitable)
    # cursor advances to the other asset
    offensive.main(["--vault", str(vault), "--eng", str(eng), "next"])
    out2 = capsys.readouterr().out
    assert "web2" in out2
