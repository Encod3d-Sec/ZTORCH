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


def _mk_poc(eng, rel):
    """Create an empty file at `rel` under eng, for G3's --poc existence check."""
    p = eng / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("")


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
    _mk_poc(eng, "poc/x.png")
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
    _mk_poc(eng, "poc/x.png")
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


# --------------------------------------------------------------------------- G2 per-row anchor

def test_g2_skill_fired_before_row_opened_does_not_satisfy_it(tmp_path):
    """Regression: G2 was anchored to engagement start, so a Skill(x) fired once at
    minute 1 silently satisfied every future row mapped to that skill, however much
    later it was discovered/seeded. Anchoring to the row's own opened_at closes this:
    a skill invocation dated BEFORE the row's own board-seed stamp must not satisfy G2."""
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1",
                                     **{"vuln class": "sqli"},
                                     arsenal="payloads/sqli", skill="hunt-sqli",
                                     tool="sqlmap")])
    # simulate the row having been stamped open AFTER an earlier Skill(hunt-sqli) fire
    st = json.loads((eng / offensive.STATE_NAME).read_text())
    early_ts = st["started_at"]
    later_ts = (datetime.fromisoformat(early_ts) + timedelta(hours=2)).isoformat()
    st.setdefault("row_opened_at", {})["web1|sqli"] = later_ts
    (eng / offensive.STATE_NAME).write_text(json.dumps(st))
    (eng / ".events.jsonl").write_text(json.dumps(
        {"tool": "Skill", "skill": "hunt-sqli", "ts": early_ts}) + "\n")
    _mk_poc(eng, "poc/x.png")
    with pytest.raises(SystemExit) as ex:
        _run(["--vault", str(vault), "--eng", str(eng), "done", "4a:1",
              "--poc", "poc/x.png", "--kind", "req"])
    assert ex.value.code != 0


def test_g2_batch_seeded_rows_share_one_invocation(tmp_path):
    """A single Skill(x) invocation fired right after a batch of same-skill rows is seeded
    (vector-workflow's normal behavior: several rows born together from one asset) must
    satisfy G2 for ALL of them -- they share a birth moment, so this must not force a
    redundant re-invocation per row."""
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [
        _row(id="4a:1", asset="web1", **{"vuln class": "content-discovery"},
             arsenal="wordlists", skill="hunt-rce", tool="ffuf"),
        _row(id="4a:2", asset="web1", **{"vuln class": "recon-nuclei"},
             arsenal="nuclei-arsenal", skill="hunt-rce", tool="nuclei"),
    ])
    st = json.loads((eng / offensive.STATE_NAME).read_text())
    # simulate both rows born in the same board-seed batch
    offensive._stamp_row_opened(st, "web1", "content-discovery")
    offensive._stamp_row_opened(st, "web1", "recon-nuclei")
    (eng / offensive.STATE_NAME).write_text(json.dumps(st))
    st = json.loads((eng / offensive.STATE_NAME).read_text())
    latest = max(st["row_opened_at"].values())
    after = (datetime.fromisoformat(latest) + timedelta(seconds=1)).isoformat()
    # ONE post-batch invocation of the shared skill
    (eng / ".events.jsonl").write_text(json.dumps(
        {"tool": "Skill", "skill": "hunt-rce", "ts": after}) + "\n")
    assert offensive._skill_fired(eng, "hunt-rce",
                                   offensive._row_since(st, "web1", "content-discovery"))
    assert offensive._skill_fired(eng, "hunt-rce",
                                   offensive._row_since(st, "web1", "recon-nuclei"))


# --------------------------------------------------------------------------- G3 poc-file-exists

def test_done_poc_nonexistent_file_refused(tmp_path):
    """Regression: --poc was never checked to actually exist -- any string satisfied G3."""
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1",
                                     **{"vuln class": "sqli"},
                                     arsenal="payloads/sqli", skill="hunt-sqli",
                                     tool="sqlmap")])
    _fire(eng, "hunt-sqli")
    with pytest.raises(SystemExit) as ex:
        _run(["--vault", str(vault), "--eng", str(eng), "done", "4a:1",
              "--poc", "poc/never-captured.png", "--kind", "req"])
    assert ex.value.code != 0


def test_done_poc_cli_kind_accepted(tmp_path):
    """G3's --kind now includes 'cli', capture.sh's default PoC mode for a
    command-execution finding (RCE/AD/privesc), previously unrepresentable."""
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1",
                                     **{"vuln class": "rce"},
                                     arsenal="payloads/rce", skill="hunt-rce",
                                     tool="metasploit")])
    _fire(eng, "hunt-rce")
    _mk_poc(eng, "poc/shell.md")
    rc = _run(["--vault", str(vault), "--eng", str(eng), "done", "4a:1",
               "--poc", "poc/shell.md", "--kind", "cli"])
    assert rc == 0
    assert offensive.read_board(eng)[0]["poc_kind"] == "cli"


# --------------------------------------------------------------------------- poc happy path

def test_done_poc_marks_row_x(tmp_path):
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1",
                                     **{"vuln class": "sqli"},
                                     arsenal="payloads/sqli", skill="hunt-sqli",
                                     tool="sqlmap")])
    _fire(eng, "hunt-sqli")
    _mk_poc(eng, "poc/sqli.png")
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
