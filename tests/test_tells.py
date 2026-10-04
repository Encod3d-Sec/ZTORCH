"""Tests for tells.py (small-indicator battery over source/response files)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import tells  # noqa: E402


def test_real_table_compiles_and_fires_on_sink(tmp_path, capsys):
    src = tmp_path / "index.js"
    src.write_text("var a = 1;\ndiv.innerHTML = obj.message;\nvar b = 2;\n", encoding="utf-8")
    table = tells.compile_tells(tells.load_tells(ROOT / "scripts" / "tells.json"))
    rc = tells.main([str(src)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "index.js:2" in out and "xss" in out and "hunt-xss" in out


def test_secrets_and_comment_tells(tmp_path, capsys):
    src = tmp_path / "config.txt"
    src.write_text("aws_key = AKIAIOSFODNN7EXAMPLE\n<!-- TODO: remove admin backdoor before prod -->\n",
                   encoding="utf-8")
    table = tells.compile_tells(tells.load_tells(ROOT / "scripts" / "tells.json"))
    tells.scan([str(src)], table, out=print)
    # smoke via main: secrets class must surface for both shapes
    rc = tells.main([str(src)])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.count("secrets") >= 2


def test_dir_walk_skips_binary_and_bad_regex(tmp_path, capsys):
    d = tmp_path / "src"
    d.mkdir()
    (d / "app.py").write_text("data = pickle.loads(blob)\n", encoding="utf-8")
    (d / "blob.bin").write_bytes(b"\x00\x01\x02\x03")
    rows = tells.load_tells(ROOT / "scripts" / "tells.json") + [
        {"re": "([unclosed", "class": "x", "skill": "y", "note": "bad"},
    ]
    table = tells.compile_tells(rows)
    assert len(table) == len(rows) - 1          # bad row dropped, rest kept
    rc = tells.main([str(d)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "app.py:1" in out and "deserialization" in out
    assert "blob.bin" not in out               # binary skipped


def test_list_flag_dumps_table(capsys):
    rc = tells.main(["--list"])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.count("->") >= 10


def test_test_flag_dry_run_no_files(capsys):
    rc = tells.main(["--test", "document.write('<img src=x onerror=alert(1>)')"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "rule 1:" in out and "hunt-xss" in out


def test_message_placeholders():
    row = {"re": "onerror=", "class": "xss", "skill": "hunt-xss",
           "note": "n", "message": "saw {match} under rule {rule}"}
    msg = tells.render_message(row, "onerror=", "", 3)
    assert msg == "saw onerror= under rule 3"
    assert tells.render_message({"note": "plain"}, "x", "", 1) == "plain"


def test_filename_rows_hit_path_not_content(tmp_path, capsys):
    d = tmp_path / "mirror"
    d.mkdir()
    env = d / ".env"
    env.write_text("nothing matching content rows here\n", encoding="utf-8")
    key = d / "id_rsa"
    key.write_text("zzz\n", encoding="utf-8")
    rc = tells.main([str(d)])
    out = capsys.readouterr().out
    assert rc == 0
    assert ".env" in out and "FILENAME" in out
    assert "id_rsa" in out
