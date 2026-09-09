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
