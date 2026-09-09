"""close-out.py inflight_signals(): the Stop-time in-flight surface (open lanes, the
driver's last-served row never dispositioned, pending ingest, waiting OOB sinks) -
the first two have no other surface anywhere in the harness."""
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "close_out", ROOT / "skills" / "hooks" / "close-out.py")
close_out = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(close_out)

# dispatch-format open lane (delegate SKILL.md): ends at the handle cell
LANE = ("- lane web01 (10.0.0.5) in flight @21:40: SUCCESS = uid=33 | "
        "tmux win 3 | capture poc/web01 | handle ag-1\n")


def _mk(tmp_path, *, lane=True, move_open=True, ingest=True, oob=True):
    if lane:
        (tmp_path / "log.md").write_text(LANE, encoding="utf-8")
    if move_open:
        (tmp_path / ".offensive.json").write_text(json.dumps(
            {"last_move": {"row": "4a:2", "ts": "12:03"}}), encoding="utf-8")
        (tmp_path / "Approach.md").write_text(
            "| id | asset | vuln class | status | arsenal | skill | tool |\n"
            "|---|---|---|---|---|---|---|\n"
            "| 4a:2 | 10.0.0.5 | ssrf | [~] | payloads/ssrf | hunt-ssrf | curl |\n",
            encoding="utf-8")
    if ingest:
        d = tmp_path / "ingest"
        d.mkdir(exist_ok=True)
        (d / "nmap-1.txt").write_text("x", encoding="utf-8")
        (d / "_archived.txt").write_text("x", encoding="utf-8")   # skipped: _-prefix
    if oob:
        (tmp_path / "oob.md").write_text(
            "| token | sink | class | planted | status | source |\n"
            "|---|---|---|---|---|---|\n"
            "| abc123 | http://t/?u= | ssrf | 2026-09-10 | waiting | |\n"
            "| def456 | http://t/?c= | ssrf | 2026-09-10 | hit | |\n",
            encoding="utf-8")


def test_all_four_signals_surface(tmp_path):
    _mk(tmp_path)
    joined = " | ".join(close_out.inflight_signals(str(tmp_path)))
    assert "lane web01" in joined
    assert "served 4a:2 @12:03 not disposed" in joined
    assert "1 ingest file" in joined                  # _-prefixed file not counted
    assert "1 OOB sink" in joined                     # only the waiting row


def test_dispositioned_and_closed_state_is_silent(tmp_path):
    _mk(tmp_path, move_open=False)
    # row closed -> .offensive.json present but the served row is [x]: no serve signal
    (tmp_path / ".offensive.json").write_text(json.dumps(
        {"last_move": {"row": "4a:2", "ts": "12:03"}}), encoding="utf-8")
    (tmp_path / "Approach.md").write_text(
        "| id | asset | vuln class | status | arsenal | skill | tool |\n"
        "|---|---|---|---|---|---|---|\n"
        "| 4a:2 | 10.0.0.5 | ssrf | [x] | payloads/ssrf | hunt-ssrf | curl |\n",
        encoding="utf-8")
    parts = close_out.inflight_signals(str(tmp_path))
    assert not any("not disposed" in p for p in parts)


def test_missing_everything_is_empty(tmp_path):
    assert close_out.inflight_signals(str(tmp_path)) == []
