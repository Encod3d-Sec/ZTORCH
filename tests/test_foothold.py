"""Tests for offensive.py `foothold` + `done --win` post-foothold 4b re-board."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import offensive  # noqa: E402


def _setup(tmp_path, etype="pentest"):
    """Init a pentest engagement against the REAL vault (so the routing table
    carries windows/macos/ad classes the 4b rows resolve against), build index."""
    vault = tmp_path / "vault"
    (vault / "targets").mkdir(parents=True)
    # symlink (read-only for these tests); setup/ is never read via --vault
    for sub in ("skills", "wiki"):
        (vault / sub).symlink_to(ROOT / sub, target_is_directory=True)
    offensive.main(["--vault", str(vault), "init", "demo", "--type", etype])
    eng = vault / "targets" / "demo"
    offensive.build_index(eng, vault)
    return vault, eng


def _state(eng):
    return json.loads((eng / offensive.STATE_NAME).read_text())


def _row(**kw):
    base = {"id": "", "asset": "", "vuln class": "", "arsenal": "",
            "skill": "", "tool": "", "status": "[ ]", "poc": "", "poc_kind": ""}
    base.update(kw)
    return base


def _fire(eng, skill):
    st = _state(eng)
    (eng / ".events.jsonl").write_text(json.dumps(
        {"tool": "Skill", "skill": skill, "row": "4a:1", "ts": st["started_at"]}) + "\n")


# 4b non-hollow invariant (new, post-Fix-2): every row carries a non-empty
# arsenal AND tool; the skill cell is non-empty ONLY when the row routes to a
# real hunt skill (windows/macos/ad). A Linux privesc row correctly has an empty
# skill (there is no hunt-linux class - it routes via arsenal hint + tool).
_HUNT_SKILLED = {"hunt-windows", "hunt-macos", "hunt-ad"}


def _assert_4b_invariant(rows):
    assert rows, "expected 4b rows"
    for r in rows:
        assert r["arsenal"], "empty arsenal: %r" % r
        assert r["tool"], "empty tool: %r" % r
        if r["skill"]:
            assert r["skill"] in _HUNT_SKILLED, "unexpected skill cell: %r" % r


def test_foothold_seeds_4b_rows(tmp_path):
    vault, eng = _setup(tmp_path)
    rc = offensive.main(["--vault", str(vault), "--eng", str(eng),
                         "foothold", "demo-asset", "--win", "2"])
    assert rc == 0
    assert _state(eng)["foothold"] is True
    assert _state(eng)["footholds"]["demo-asset"] == "2"
    b4 = offensive.read_board_4b(eng)
    assert b4, "foothold should seed a ### 4b section"
    classes = {r["vuln class"] for r in b4}
    assert "privesc" in classes and "lateral" in classes
    _assert_4b_invariant(b4)


def test_done_win_records_foothold(tmp_path):
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1",
                                     **{"vuln class": "rce"}, arsenal="payloads/command-injection",
                                     skill="hunt-rce", tool="metasploit")])
    _fire(eng, "hunt-rce")
    rc = offensive.main(["--vault", str(vault), "--eng", str(eng), "done", "4a:1",
                         "--poc", "poc/shell.png", "--kind", "req", "--win", "3"])
    assert rc == 0
    st = _state(eng)
    assert st["foothold"] is True
    assert st["footholds"]["web1"] == "3"
    b4 = offensive.read_board_4b(eng)
    assert any(r["asset"] == "web1" for r in b4)


def test_4b_rows_not_hollow(tmp_path):
    vault, eng = _setup(tmp_path)
    offensive.main(["--vault", str(vault), "--eng", str(eng),
                    "foothold", "box1", "--win", "1"])
    b4 = offensive.read_board_4b(eng)
    _assert_4b_invariant(b4)


def test_4b_idempotent(tmp_path):
    vault, eng = _setup(tmp_path)
    argv = ["--vault", str(vault), "--eng", str(eng), "foothold", "box1", "--win", "1"]
    offensive.main(argv)
    first = offensive.read_board_4b(eng)
    offensive.main(argv)          # re-run
    second = offensive.read_board_4b(eng)
    assert len(first) == len(second), "4b rows duplicated on re-run"
    ids = [r["id"] for r in second]
    assert len(ids) == len(set(ids)), "duplicate 4b ids"


def test_ctf_privesc_rows(tmp_path):
    vault, eng = _setup(tmp_path, etype="ctf")
    offensive.main(["--vault", str(vault), "--eng", str(eng),
                    "foothold", "box1", "--win", "1"])
    b4 = offensive.read_board_4b(eng)
    classes = {r["vuln class"] for r in b4}
    assert "privesc-auto" in classes and "privesc-manual" in classes
    tools = {r["tool"] for r in b4}
    assert "pspy" in tools          # ctf auto privesc uses pspy
    _assert_4b_invariant(b4)


def test_next_serves_4b_after_4a(tmp_path, capsys):
    """With all 4a rows closed and a foothold recorded, `next` walks into the
    asset's 4b rows (serving its id + class) instead of printing closeout; only
    once the 4b rows are also closed does `next` report the board exhausted."""
    vault, eng = _setup(tmp_path)
    # one CLOSED 4a row for box1 -> 4a exhausted for that asset
    offensive.write_board(eng, [_row(id="4a:1", asset="box1", **{"vuln class": "rce"},
                                     arsenal="payloads/x", skill="hunt-rce",
                                     tool="metasploit", status="[x]",
                                     poc="poc/a.png", poc_kind="req")])
    offensive.main(["--vault", str(vault), "--eng", str(eng),
                    "foothold", "box1", "--win", "1"])
    b4 = offensive.read_board_4b(eng)
    assert b4, "foothold should have seeded 4b rows"
    served = b4[0]
    capsys.readouterr()                      # clear the foothold output
    rc = offensive.main(["--vault", str(vault), "--eng", str(eng), "next"])
    out = capsys.readouterr().out
    assert rc == 0
    assert served["id"] in out, out          # header names the 4b row id
    assert served["vuln class"] in out, out  # ... and its class
    assert "board exhausted" not in out
    # emits the row's Skill/tool action, not the closeout line
    assert served["tool"] in out or "Skill(" in out

    # close every 4b row -> next now reports closeout
    rows4b = offensive.read_board_4b(eng)
    for r in rows4b:
        r["status"] = "[x]"
    offensive.write_board_4b(eng, rows4b)
    offensive.main(["--vault", str(vault), "--eng", str(eng), "next"])
    out2 = capsys.readouterr().out
    assert "board exhausted" in out2


def test_linux_foothold_routes_linux(tmp_path):
    """A Linux (unknown-OS -> Linux default) foothold's privesc 4b row uses Linux
    tooling (linpeas/pspy) + a linux arsenal hint with NO hunt skill, and never
    references hunt-macos / macos-app-injection. Lateral still routes to hunt-ad."""
    vault, eng = _setup(tmp_path)            # box1 has no OS fingerprint -> Linux
    offensive.main(["--vault", str(vault), "--eng", str(eng),
                    "foothold", "box1", "--win", "1"])
    b4 = offensive.read_board_4b(eng)
    pv = [r for r in b4 if r["vuln class"].startswith("privesc")]
    assert pv, "expected a privesc 4b row"
    for r in pv:
        assert r["tool"] in ("linpeas", "pspy"), r
        assert "linux" in r["arsenal"].lower(), r
        assert not r["skill"], "linux privesc must have an empty skill cell: %r" % r
        blob = (r["skill"] + " " + r["arsenal"] + " " + r["tool"]).lower()
        assert "macos" not in blob and "hunt-mac" not in blob, r
    lat = [r for r in b4 if r["vuln class"] == "lateral"]
    assert lat and lat[0]["skill"] == "hunt-ad", lat
