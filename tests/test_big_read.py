"""big-read.py: the >200KB full-Read advisory fires once per file per 15 min, stays
silent on narrow reads (offset/limit present) and small files, fail-opens."""
import importlib.util
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "big_read", ROOT / "skills" / "hooks" / "big-read.py")
br = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(br)

# a fake vault root so the stamp dir lands in tmp instead of the real session/
class _FakeEng:
    VAULT = os.environ.get("BIGREAD_TEST_VAULT", "/tmp")


def _fire(tmp_path, big, **over):
    """Run main() with a synthetic payload; returns captured stdout."""
    import io
    import contextlib
    p = tmp_path / ("big.bin" if big else "small.bin")
    p.write_bytes(b"x" * (250_000 if big else 1000))
    payload = {"tool_name": "Read", "tool_input": {"file_path": str(p)}}
    payload.update(over)
    buf = io.StringIO()
    old_stdin, old_stdout = sys.stdin, sys.stdout
    sys.stdin, sys.stdout = io.StringIO(json.dumps(payload)), buf
    try:
        br.main()
    finally:
        sys.stdin, sys.stdout = old_stdin, old_stdout
    return buf.getvalue()


def test_fires_on_big_full_read(tmp_path, monkeypatch):
    monkeypatch.setenv("BIGREAD_TEST_VAULT", str(tmp_path))
    _FakeEng.VAULT = str(tmp_path)
    out = _fire(tmp_path, big=True)
    assert "big-read advisory" in out and "244KB" in out
    assert "does not replace the read" in out


def test_silent_with_offset_or_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("BIGREAD_TEST_VAULT", str(tmp_path))
    _FakeEng.VAULT = str(tmp_path)
    assert _fire(tmp_path, big=True, tool_input={"file_path": str(
        tmp_path / "big.bin"), "offset": 10}) == ""
    assert _fire(tmp_path, big=True, tool_input={"file_path": str(
        tmp_path / "big.bin"), "limit": 50}) == ""


def test_silent_on_small_file_and_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("BIGREAD_TEST_VAULT", str(tmp_path))
    _FakeEng.VAULT = str(tmp_path)
    assert _fire(tmp_path, big=False) == ""
    assert _fire(tmp_path, big=True, tool_input={"file_path": str(
        tmp_path / "nope.bin")}) == ""


def test_dedupe_per_file_stamp(tmp_path, monkeypatch):
    monkeypatch.setenv("BIGREAD_TEST_VAULT", str(tmp_path))
    _FakeEng.VAULT = str(tmp_path)
    assert "big-read advisory" in _fire(tmp_path, big=True)   # first fires
    assert _fire(tmp_path, big=True) == ""                    # fresh stamp suppresses


def test_failopen_on_garbage_stdin(capsys):
    import io
    old = sys.stdin
    sys.stdin = io.StringIO("not json")
    try:
        br.main()
    finally:
        sys.stdin = old
    assert capsys.readouterr().out == ""
