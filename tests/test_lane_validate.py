"""lane_validate.py: returned-lane claims verified against their captures (delegate
contract: verdict above the claim; an observable absent from the capture = over-claim)."""
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("lane_validate", ROOT / "scripts" / "lane_validate.py")
lv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lv)

LINE = ("- lane %s in flight: SUCCESS = %s | tmux win w1 | capture poc/%s%s\n")


def test_in_flight_line_without_closure_is_skipped():
    text = LINE % ("a", "uid=33(www-data)", "a", "")
    assert lv.lanes_from_text(text) == []          # status, not guess


def test_closed_line_is_parsed_and_validated(tmp_path, capsys):
    log = tmp_path / "log.md"
    log.write_text(LINE % ("a", "uid=33(www-data)", "a", " -> VERIFIED: shell"), encoding="utf-8")
    cap = tmp_path / "poc" / "a"
    cap.mkdir(parents=True)
    (cap / "shell.txt").write_text("id\nuid=33(www-data)\n", encoding="utf-8")
    lv.main([str(tmp_path)])
    out = capsys.readouterr().out
    assert "lane a: VERIFIED" in out


def test_claim_absent_from_capture_is_not_verified(tmp_path, capsys):
    log = tmp_path / "log.md"
    log.write_text(LINE % ("b", "THM{zzz}", "b", " -> claim: rooted"), encoding="utf-8")
    cap = tmp_path / "poc" / "b"
    cap.mkdir(parents=True)
    (cap / "out.txt").write_text("no flag in here\n", encoding="utf-8")
    lv.main([str(tmp_path)])
    out = capsys.readouterr().out
    assert "lane b: NOT VERIFIED" in out and "hypothesis" in out


def test_missing_capture_dir_is_not_verified(tmp_path, capsys):
    log = tmp_path / "log.md"
    log.write_text(LINE % ("c", "x", "c", " -> claim"), encoding="utf-8")
    lv.main([str(tmp_path)])                       # poc/c never created
    assert "lane c: NOT VERIFIED" in capsys.readouterr().out


# --- open_lanes_from_text (status.py's open-lane printer) -------------------------------

NEWLINE = ("- lane %s (%s) in flight @21:40: SUCCESS = %s | tmux win w1 | capture poc/%s%s\n")


def test_open_lane_listed_with_tail_cells():
    text = NEWLINE % ("d", "10.10.10.9", "uid=33", "d", "")
    opens = lv.open_lanes_from_text(text)
    assert len(opens) == 1 and opens[0][0] == "d" and "10.10.10.9" in opens[0][1]
    assert "@21:40" in opens[0][1]


def test_closed_lane_not_listed_open():
    text = (NEWLINE % ("e", "10.10.10.9", "uid=33", "e", " -> VERIFIED: shell")
            + NEWLINE % ("f", "10.10.10.9", "uid=33", "f", ""))
    assert [n for n, _ in lv.open_lanes_from_text(text)] == ["f"]


def test_status_lane_lines_ages_and_flags_stale(tmp_path):
    import importlib.util
    from datetime import datetime, timedelta
    _spec2 = importlib.util.spec_from_file_location("status", ROOT / "scripts" / "status.py")
    st = importlib.util.module_from_spec(_spec2)
    _spec2.loader.exec_module(st)
    stale = (datetime.now() - timedelta(minutes=90)).strftime("%H:%M")
    fresh = (datetime.now() - timedelta(minutes=2)).strftime("%H:%M")
    old_ln = (NEWLINE % ("old", "10.10.10.9", "uid=33", "old", "")).replace("@21:40", "@" + stale)
    new_ln = (NEWLINE % ("new", "10.10.10.9", "uid=33", "new", "")).replace("@21:40", "@" + fresh)
    (tmp_path / "log.md").write_text(old_ln + new_ln, encoding="utf-8")
    lines = st.lane_lines(str(tmp_path))
    joined = "\n".join(lines)
    assert len(lines) == 2
    assert "STALE" in joined.split("new")[0]        # the 90min-old lane is flagged
    assert "lane new" in joined and "STALE" not in joined.split("lane new")[1]
