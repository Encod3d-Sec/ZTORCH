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
    for sub in ("skills", "wiki", "scripts"):
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
    src = vault / "scripts" / "routing.json"
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


# ---- serve accounting + G4 serve-path + walled board (driver audit, 2026-09-10) ----

def test_pass_increments_and_reServe_warns(tmp_path, capsys):
    """`pass` = serves (drift-guard arms at >= 5; it read 0 forever) and the 3rd
    unchanged serve of one row prints the RE-SERVE redirection."""
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1", **{"vuln class": "ssrf"},
                                     arsenal="x", skill="", tool="nuclei")])
    st_p = eng / ".offensive.json"
    for i in (1, 2, 3):
        rc, out = _next_out(capsys, vault, eng)
        st = json.loads(st_p.read_text())
        assert st["pass"] == i
        assert st["serve_count"]["4a:1"] == i
    assert i == 3 and "RE-SERVE 3x" in out and "Skill(redteamlead)" in out


def test_park_feeds_wallbreak_streak(tmp_path, capsys):
    """--park is a no-find outcome: it must bump dry_streak like --dead, else a
    park-everything loop never triggers redirection."""
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1", **{"vuln class": "ssrf"},
                                     skill="hunt-ssrf", tool="nuclei")])
    rc = offensive.main(["--vault", str(vault), "--eng", str(eng),
                         "done", "4a:1", "--park", "needs judgment"])
    assert rc == 0
    st = json.loads((eng / ".offensive.json").read_text())
    assert st["dry_streak"] == 1


def test_deadend_pair_suppresses_hand_revived_row(tmp_path, capsys):
    """G4 on the serve path: a [!] -> [ ] hand-edit must not resurrect a dead
    (asset, class); the suppression is named, not silent."""
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1", **{"vuln class": "ssrf"},
                                     status="[ ]", skill="", tool="nuclei")])
    (eng / "Deadends.md").write_text(
        "| asset | class | why | status | date | source |\n|---|---|---|---|---|---|\n"
        "| web1 | ssrf | burned | exhausted | 2026-09-10 | |\n", encoding="utf-8")
    rc, out = _next_out(capsys, vault, eng)
    assert rc == 0
    assert "G4: 1 open row(s) match a Deadends.md pair" in out
    assert "4a:1" in out
    assert "Skill(wiki-arsenal)" not in out   # suppressed row is not served


def test_walled_board_gets_redteamlead_not_closeout(tmp_path, capsys):
    """All parked/dead + zero finds must NOT print the closeout chain."""
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1", **{"vuln class": "ssrf"},
                                     status="[?]", skill="", tool="nuclei")])
    rc, out = _next_out(capsys, vault, eng)
    assert rc == 0
    assert "NO closed rows" in out and "redteamlead" in out
    assert "closeout is for a SOLVED board" in out
    assert "run the closeout chain" not in out


def test_note_restamps_row_opened_at(tmp_path, capsys):
    """A hand-revived row keeps its old stamp; the [ ] -> [~] flip re-stamps so a
    stale weeks-old Skill(x) fire cannot satisfy G2 for the reopened vector."""
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1", **{"vuln class": "ssrf"},
                                     skill="hunt-ssrf", tool="nuclei")])
    st_p = eng / ".offensive.json"
    st = json.loads(st_p.read_text())
    st["row_opened_at"] = {"web1|ssrf": "2020-01-01T00:00:00+00:00"}
    st_p.write_text(json.dumps(st))
    rc = offensive.main(["--vault", str(vault), "--eng", str(eng),
                         "note", "4a:1", "--arsenal", "s", "--force"])
    assert rc == 0
    st = json.loads(st_p.read_text())
    assert st["row_opened_at"]["web1|ssrf"] > "2020-01-01"


def test_read_board_ignores_table_above_4a(tmp_path):
    """An agent-added table higher in Approach.md must not become the board."""
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1", **{"vuln class": "ssrf"},
                                     status="[ ]", skill="", tool="nuclei")])
    p = eng / "Approach.md"
    decoy = "| id | note |\n|---|---|\n| 99 | decoy above the section |\n\n"
    p.write_text("# Approach\n\n" + decoy + p.read_text(), encoding="utf-8")
    rows = offensive.read_board(eng)
    assert len(rows) == 1 and rows[0].get("id") == "4a:1"


def _next_json(capsys, vault, eng):
    rc = offensive.main(["--vault", str(vault), "--eng", str(eng), "next", "--json"])
    # the buffer may carry earlier prints (init/banner); the payload is the last line
    return rc, json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_next_json_gates_in_walk_order(tmp_path, capsys):
    """`next --json` mirrors the gate walk: arsenal withheld -> skill withheld
    -> invocation served; same state writes (pass, serve_count, last_move)."""
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1", **{"vuln class": "sqli"},
                                     arsenal="", skill="hunt-sqli", tool="sqlmap")])
    rc, p = _next_json(capsys, vault, eng)
    assert rc == 0
    assert p["row"] == "4a:1" and p["class"] == "sqli" and p["tool"] == "sqlmap"
    assert p["gates_remaining"] == ["arsenal"] and p["terminal"] is None
    assert p["invocation"] is None and p["autonomy"] in ("L0", "L1", "L2", "L3")
    st = json.loads((eng / offensive.STATE_NAME).read_text())
    assert st["pass"] == 1 and st["last_move"]["row"] == "4a:1"
    # release G1, oracle present but skill unfired -> skill gate
    offensive.write_board(eng, [_row(id="4a:1", asset="web1", **{"vuln class": "sqli"},
                                     arsenal="payloads/sqli", skill="hunt-sqli",
                                     tool="sqlmap", status="[~]")])
    (eng / ".events.jsonl").write_text("")
    _, p = _next_json(capsys, vault, eng)
    assert p["gates_remaining"] == ["skill"] and p["invocation"] is None
    # fire the skill -> invocation served
    state = json.loads((eng / offensive.STATE_NAME).read_text())
    (eng / ".events.jsonl").write_text(json.dumps(
        {"tool": "Skill", "skill": "hunt-sqli", "ts": state["started_at"]}) + "\n")
    _, p = _next_json(capsys, vault, eng)
    assert p["gates_remaining"] == [] and "sqlmap" in (p["invocation"] or "")


def test_next_json_terminal_states(tmp_path, capsys):
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [])          # no rows at all -> empty-board
    _, p = _next_json(capsys, vault, eng)
    assert p["terminal"] == "empty-board" and p["row"] is None
    # walled: only parked/dead rows, zero closed
    offensive.write_board(eng, [_row(id="4a:1", asset="web1", status="[?]",
                                     **{"vuln class": "ssrf"})])
    _, p = _next_json(capsys, vault, eng)
    assert p["terminal"] == "walled" and p["skill"] == "redteamlead"


def test_autonomy_subcommand_rewrites_scope_and_logs(tmp_path, capsys):
    vault, eng = _setup(tmp_path)
    rc = offensive.main(["--vault", str(vault), "--eng", str(eng),
                         "autonomy", "L3", "--reason", "operator approved chained ops"])
    assert rc == 0
    lvl, note = offensive.autonomy_of(eng)
    assert lvl == "L3" and note == ""
    evs = [json.loads(l) for l in (eng / ".events.jsonl").read_text().splitlines()]
    assert any(e.get("event") == "autonomy_change" and e.get("to") == "L3"
               and e.get("from") in ("L0", "L1", "L2", "L3") for e in evs)
    with pytest.raises(SystemExit):             # unknown level refused
        offensive.main(["--vault", str(vault), "--eng", str(eng), "autonomy", "L9"])


def test_next_json_stale_index_exits_2(tmp_path, capsys):
    """The JSON path carries the text path's refusal semantics (G9): a wrapper
    branching on the exit code must not silently proceed on a broken index."""
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1", **{"vuln class": "ssrf"},
                                     arsenal="a", skill="hunt-ssrf", tool="nuclei")])
    fut = time.time() + 600
    os.utime(vault / "scripts" / "routing.json", (fut, fut))
    rc, payload = _next_json(capsys, vault, eng)
    assert rc == 2
    assert payload["terminal"] == "stale-index"
    assert payload["row"] is None and payload["invocation"] is None


def test_next_corrupt_state_names_checkpoint_restore(tmp_path, capsys):
    """A truncated .offensive.json (crash mid-write) used to surface as a raw
    JSONDecodeError traceback; now it names the shadow-git recovery path."""
    vault, eng = _setup(tmp_path)
    (eng / offensive.STATE_NAME).write_text('{"started_at": "2026-0', encoding="utf-8")
    rc = offensive.main(["--vault", str(vault), "--eng", str(eng), "next"])
    assert rc == 2
    out = capsys.readouterr().out
    assert "corrupt" in out and "git -C" in out and "checkout" in out
    assert "Traceback" not in out


def test_next_wrong_typed_state_refused(tmp_path, capsys):
    vault, eng = _setup(tmp_path)
    (eng / offensive.STATE_NAME).write_text('["not", "a", "map"]', encoding="utf-8")
    rc = offensive.main(["--vault", str(vault), "--eng", str(eng), "next"])
    assert rc == 2
    assert "expected a JSON object" in capsys.readouterr().out


def test_board_malformed_rows_warned_best_effort(tmp_path, capsys):
    """A hand-edited [X] status cell (invisible to open/closed accounting, once
    printed a false 'board exhausted') and an over-long row (pipe in a cell,
    shifting later cells) must be ANNOUNCED on both the text and JSON paths,
    never silently mis-accounted - the clone's coerce+warn pattern."""
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1", **{"vuln class": "ssrf"},
                                     arsenal="a", skill="hunt-ssrf", tool="nuclei")])
    ap = eng / "Approach.md"
    ap.write_text(ap.read_text(encoding="utf-8") +
                  "| 4a:7 | web1 | ssrf | a | s | t | [X] |  |  |\n"          # uppercase status
                  "| 4a:8 | web1 | ssrf | a | s | t | [ ] |  |  | oops |\n",   # extra cell
                  encoding="utf-8")
    rc, out = _next_out(capsys, vault, eng)
    assert rc == 0                                        # parse stays best-effort
    assert "BOARD (parsed best-effort)" in out
    assert "status cell '[X]' not recognized" in out
    assert "10 cells vs 9 header columns" in out
    _, payload = _next_json(capsys, vault, eng)           # re-read regenerates them
    assert any("status cell" in w for w in payload["warnings"])
    assert any("shifted" in w for w in payload["warnings"])


def test_next_json_runner_and_gate_actions(tmp_path, capsys):
    """pass 12: the payload carries what a programmatic consumer needs to ACT,
    not just to look: gate_action (the directive), runner/cmd/read_cmd (the G8
    dispatch split), evidence_cmd, posture, and the closeout chain on an
    exhausted board."""
    vault, eng = _setup(tmp_path)
    offensive.write_board(eng, [_row(id="4a:1", asset="web1", **{"vuln class": "sqli"},
                                     arsenal="", skill="hunt-sqli", tool="sqlmap")])
    _, p = _next_json(capsys, vault, eng)
    assert p["gate_action"] == "Skill(wiki-arsenal) sqli"
    assert p["runner"] is None and p["cmd"] is None and p["chain"] is None
    # release G1, skill unfired -> skill gate names the skill
    offensive.write_board(eng, [_row(id="4a:1", asset="web1", **{"vuln class": "sqli"},
                                     arsenal="payloads/sqli", skill="hunt-sqli",
                                     tool="sqlmap", status="[~]")])
    (eng / ".events.jsonl").write_text("")
    _, p = _next_json(capsys, vault, eng)
    assert p["gate_action"] == "Skill(hunt-sqli)"
    # sqlmap is OUTPUT_CLASS -> vm-bg runner + a read command + evidence line
    state = json.loads((eng / offensive.STATE_NAME).read_text())
    (eng / ".events.jsonl").write_text(json.dumps(
        {"tool": "Skill", "skill": "hunt-sqli", "ts": state["started_at"]}) + "\n")
    _, p = _next_json(capsys, vault, eng)
    assert p["gates_remaining"] == []
    assert p["runner"] == "vm-bg" and "vm-bg.sh" in p["cmd"] and "--read" in (p["read_cmd"] or "")
    assert "capture.sh" in p["evidence_cmd"] and "4a:1" in p["evidence_cmd"]
    assert p["posture"] == "serial"          # one open asset
    # a second open asset flips posture; close everything -> chain is served
    offensive.write_board(eng, [
        _row(id="4a:1", asset="web1", **{"vuln class": "sqli"}, status="[x]"),
        _row(id="4a:2", asset="web2", **{"vuln class": "xss"}, status="[!]")])
    _, p = _next_json(capsys, vault, eng)
    assert p["terminal"] == "exhausted" and p["chain"] == offensive.CLOSEOUT_CHAINS["bb"]


def test_next_json_corrupt_state_keeps_stdout_clean(tmp_path, capsys):
    """pass 12: under --json a corrupt .offensive.json must report on STDERR and
    exit 2 - stdout stays parseable (empty of diagnostics), so a wrapper's
    json.loads never trips over an error line."""
    vault, eng = _setup(tmp_path)
    (eng / offensive.STATE_NAME).write_text('{"truncated": ')
    rc = offensive.main(["--vault", str(vault), "--eng", str(eng), "next", "--json"])
    captured = capsys.readouterr()
    assert rc == 2
    assert "corrupt" in captured.err and "checkpoint" in captured.err
    assert ".offensive.json corrupt" not in captured.out   # path chars aside, no diagnostic
