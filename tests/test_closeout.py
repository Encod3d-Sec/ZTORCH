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
    for sub in ("skills", "wiki", "scripts"):
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


def _seed_asset(eng, asset="web1"):
    """Insert a state.md asset row (the bb/ctf table) below its separator. `coverage`
    derives the asset set from state.md via next_move.in_scope_assets -- a board-only
    fixture mirrors no real engagement (assets always start in state.md)."""
    state = eng / "state.md"
    lines = state.read_text().splitlines()
    sep = next(i for i, l in enumerate(lines)
               if l.startswith("|") and set(l.strip("| ")) <= set("-:| "))
    lines.insert(sep + 1, "| %s | http://t/ | / | | | recon | |" % asset)
    state.write_text("\n".join(lines) + "\n")


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
    _seed_asset(eng)
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
    (eng / "poc").mkdir(parents=True, exist_ok=True)
    (eng / "poc" / "ssrf.png").write_text("x")
    _run(["--vault", str(vault), "--eng", str(eng), "done", "4a:2",
          "--poc", "poc/ssrf.png", "--kind", "req"])
    assert _state(eng)["dry_streak"] == 0


def test_coverage_type_alias_and_deadend_credit(tmp_path, capsys):
    """D-D2 (pass 15): a state frontmatter carrying the normalized `bugbounty` spelling
    must not silently empty the report (BASE_CLASSES keys use `bb`), and a Deadends.md
    line naming a class must clear it here exactly like it clears next_move's [gap]
    floor - the two reports can never disagree."""
    vault, eng = _setup(tmp_path / "a", "bb")
    st = json.loads((eng / offensive.STATE_NAME).read_text())
    st["type"] = "bugbounty"                      # the normalized spelling, not `bb`
    (eng / offensive.STATE_NAME).write_text(json.dumps(st, indent=2))
    _seed_asset(eng)
    offensive.write_board(eng, [
        _row(id="4a:1", asset="web1", **{"vuln class": "sqli"},
             arsenal="payloads/sqli", skill="hunt-sqli", tool="sqlmap", status="[x]"),
        _row(id="4a:2", asset="web1", **{"vuln class": "smuggling"},
             arsenal="", skill="", tool="nuclei", status="[ ]"),
    ])
    # the smuggling row exhausted -> one Deadends line (credit path next_move already uses)
    (eng / "Deadends.md").write_text(
        "| asset | class | what was tried | why exhausted | date | reopen-if |\n"
        "|---|---|---|---|---|---|\n"
        "| web1 | request smuggling desync | tee-cl probe | not a desync-capable proxy "
        "| 2026-09-10 | new proxy version |\n", encoding="utf-8")
    rc = _run(["--vault", str(vault), "--eng", str(eng), "coverage"])
    out = capsys.readouterr().out
    assert rc == 0 and "web1" in out
    line = [l for l in out.splitlines() if l.strip().startswith("web1")][0]
    assert "smuggling" not in line            # deadend credit cleared the driver spelling
    assert "request-smuggling" not in line    # ...and the JSON spelling


def test_collect_rulings(tmp_path):
    import offensive
    log = tmp_path / "log.md"
    log.write_text(
        "[laneA] tool ffuf ok\n"
        "Ruling: skip staging vhost - VPN-blocked, evidence closed - one lane re-run if access lands\n"
        "2026-10-05 | scope | note | ok | plain audit line\n",
        encoding="utf-8",
    )
    rulings = offensive.collect_rulings(log)
    assert len(rulings) == 1
    assert rulings[0].startswith("Ruling: skip staging")
    assert offensive.collect_rulings(tmp_path / "nope.md") == []
