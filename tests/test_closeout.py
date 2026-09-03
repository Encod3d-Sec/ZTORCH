"""Tests for offensive.py `coverage`, `closeout`, and the wall-break
(dry_streak -> Skill(redteamlead)) self-correction in `next`."""
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import offensive  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "offensive"


def _setup(tmp_path, etype="bb"):
    vault = tmp_path / "vault"
    (vault / "targets").mkdir(parents=True)
    for sub in ("skills", "wiki"):
        shutil.copytree(FIX / sub, vault / sub)
    offensive.main(["--vault", str(vault), "init", "demo", "--type", etype])
    eng = vault / "targets" / "demo"
    offensive.build_index(eng, vault)
    return vault, eng


def _row(**kw):
    base = {"id": "", "asset": "", "vuln class": "", "arsenal": "",
            "skill": "", "tool": "", "status": "[ ]", "poc": "", "poc_kind": ""}
    base.update(kw)
    return base


def _run(argv):
    return offensive.main(argv)


def _state(eng):
    return json.loads((eng / offensive.STATE_NAME).read_text())


def _set_state(eng, **kw):
    st = _state(eng)
    st.update(kw)
    (eng / offensive.STATE_NAME).write_text(json.dumps(st, indent=2))


# --------------------------------------------------------------------------- closeout

def test_closeout_chain_per_type(tmp_path, capsys):
    expected = {
        "pentest": ["triage", "evidence", "walkthrough", "learn"],
        "bb": ["triage", "evidence", "walkthrough", "learn"],
        "ctf": ["walkthrough", "learn"],
    }
    for etype, chain in expected.items():
        vault, eng = _setup(tmp_path / etype, etype)
        rc = _run(["--vault", str(vault), "--eng", str(eng), "closeout"])
        out = capsys.readouterr().out
        assert rc == 0
        # each skill appears, in order
        for i, s in enumerate(chain, 1):
            assert "Skill(%s)" % s in out
        positions = [out.index("Skill(%s)" % s) for s in chain]
        assert positions == sorted(positions)
        # no nonexistent 'report' skill (a stale close-out step, since removed)
        assert "Skill(report)" not in out


# --------------------------------------------------------------------------- coverage

def test_coverage_lists_untested_classes(tmp_path, capsys):
    vault, eng = _setup(tmp_path, "bb")
    # web1: sqli tested [x], ssrf still open -> ssrf (+ every other base class) is a gap
    offensive.write_board(eng, [
        _row(id="4a:1", asset="web1", **{"vuln class": "sqli"},
             arsenal="payloads/sqli", skill="hunt-sqli", tool="sqlmap", status="[x]"),
        _row(id="4a:2", asset="web1", **{"vuln class": "ssrf"},
             arsenal="", skill="hunt-ssrf", tool="nuclei", status="[ ]"),
    ])
    rc = _run(["--vault", str(vault), "--eng", str(eng), "coverage"])
    out = capsys.readouterr().out
    assert rc == 0
    # untested classes listed for web1
    assert "web1" in out
    assert "ssrf" in out
    # a base class with no row at all is still an untested gap
    assert "rce" in out
    # the tested class is omitted from web1's gap list
    line = [l for l in out.splitlines() if l.strip().startswith("web1")][0]
    assert "sqli" not in line
    # G7: no question
    assert "?" not in out


# --------------------------------------------------------------------------- wall-break

def _min_board(eng):
    offensive.write_board(eng, [
        _row(id="4a:1", asset="web1", **{"vuln class": "sqli"},
             arsenal="payloads/sqli", skill="hunt-sqli", tool="sqlmap")])


def test_wallbreak_emits_redteamlead_on_dry_streak(tmp_path, capsys):
    # bb threshold = 3
    vault, eng = _setup(tmp_path, "bb")
    _min_board(eng)
    _set_state(eng, dry_streak=3)
    rc = _run(["--vault", str(vault), "--eng", str(eng), "next"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Skill(redteamlead)" in out
    assert "?" not in out                       # G7 no question

    # below threshold -> normal gate walk, no redteamlead
    _set_state(eng, dry_streak=2)
    _run(["--vault", str(vault), "--eng", str(eng), "next"])
    out = capsys.readouterr().out
    assert "Skill(redteamlead)" not in out


def test_wallbreak_ctf_threshold_two(tmp_path, capsys):
    vault, eng = _setup(tmp_path, "ctf")
    _min_board(eng)
    _set_state(eng, dry_streak=2)
    _run(["--vault", str(vault), "--eng", str(eng), "next"])
    out = capsys.readouterr().out
    assert "Skill(redteamlead)" in out          # ctf threshold is 2


def test_dry_streak_increments_and_resets(tmp_path):
    vault, eng = _setup(tmp_path, "bb")
    offensive.write_board(eng, [
        _row(id="4a:1", asset="web1", **{"vuln class": "sqli"},
             arsenal="payloads/sqli", skill="hunt-sqli", tool="sqlmap"),
        _row(id="4a:2", asset="web1", **{"vuln class": "ssrf"},
             arsenal="payloads/ssrf", skill="hunt-ssrf", tool="nuclei")])
    # a dead-end bumps the streak
    _run(["--vault", str(vault), "--eng", str(eng), "done", "4a:1", "--dead", "no injection"])
    assert _state(eng)["dry_streak"] == 1
    # a find (poc) resets it; seed the skill-fired event so G2 passes
    st = _state(eng)
    (eng / ".events.jsonl").write_text(json.dumps(
        {"tool": "Skill", "skill": "hunt-ssrf", "ts": st["started_at"]}) + "\n")
    _run(["--vault", str(vault), "--eng", str(eng), "done", "4a:2",
          "--poc", "poc/ssrf.png", "--kind", "req"])
    assert _state(eng)["dry_streak"] == 0
