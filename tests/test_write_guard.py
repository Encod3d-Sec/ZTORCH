"""write-guard.py: PreToolUse(Write|Edit) binary-magic refusal. A text write onto an
existing PNG/ELF/SQLite/... asks; text and missing targets pass silently; .enforce-off
(ENFORCE_OFF_MARKER) downgrades ask to advisory; malformed input fails open."""
import importlib.util
import io
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("write_guard", ROOT / "skills" / "hooks" / "write-guard.py")
wg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wg)


def run_hook(tmp_path, magic, name, monkeypatch, ext=".bin"):
    # isolate from THIS machine's real skills/hooks/.enforce-off marker, if the
    # operator has enforcement downgraded right now
    monkeypatch.setattr(wg, "HERE", str(tmp_path / "hooks"))
    p = tmp_path / (name + ext)
    p.write_bytes(magic + b"\x00" * 8)
    payload = json.dumps({"tool_name": "Write",
                          "tool_input": {"file_path": str(p), "content": "text"}})
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    wg.main()


def test_binary_magic_targets_ask(tmp_path, capsys, monkeypatch):
    cases = [
        (b"\x89PNG\r\n\x1a\n", "PNG image", "shot", ".png"),
        (b"\xff\xd8\xff\xe0", "JPEG image", "pic", ".jpg"),
        (b"GIF89a", "GIF image", "anim", ".gif"),
        (b"%PDF-1.7", "PDF document", "doc", ".pdf"),
        (b"PK\x03\x04", "ZIP archive", "z", ".zip"),
        (b"\x7fELF\x02", "ELF binary", "bin", ".elf"),
        (b"SQLite format 3\x00", "SQLite database", "db", ".db"),
        (b"\xca\xfe\xba\xbe", "Java class", "c", ".class"),
    ]
    for magic, kind, name, ext in cases:
        run_hook(tmp_path, magic, name, monkeypatch, ext)
        out = json.loads(capsys.readouterr().out)
        decision = out["hookSpecificOutput"]
        assert decision["permissionDecision"] == "ask", (kind, out)
        assert kind in decision["permissionDecisionReason"]


def test_text_and_missing_targets_pass_silently(tmp_path, capsys, monkeypatch):
    textf = tmp_path / "notes.md"
    textf.write_text("# page\n", encoding="utf-8")
    for fp in (str(textf), str(tmp_path / "not-there.png")):
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
            {"tool_name": "Edit", "tool_input": {"file_path": fp, "new_string": "x"}})))
        wg.main()
    assert capsys.readouterr().out == ""


def test_empty_file_passes(tmp_path, capsys, monkeypatch):
    p = tmp_path / "empty.png"
    p.write_bytes(b"")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(
        {"tool_input": {"file_path": str(p), "content": "x"}})))
    wg.main()
    assert capsys.readouterr().out == ""


def test_enforce_off_downgrades_to_advisory(tmp_path, capsys, monkeypatch):
    marker = tmp_path / ".enforce-off"
    marker.write_text("", encoding="utf-8")
    monkeypatch.setenv("ENFORCE_OFF_MARKER", str(marker))
    run_hook(tmp_path, b"\x89PNG\r\n\x1a\n", "off", monkeypatch)
    out = json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    assert "permissionDecision" not in out and "advisory" in out["additionalContext"]


def test_malformed_stdin_fails_open(capsys, monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))
    wg.main()
    assert capsys.readouterr().out == ""


def test_helper_binary_kind():
    assert wg._binary_kind("/nonexistent/x") is None
