"""session-start.py's hot.md rotation: entries beyond the newest 3 (by the date in each
'## ' heading) are archived VERBATIM to hot-archive.md; undated headings are always kept;
a file within budget is a no-op (no archive file created, bytes untouched)."""
from hookrunner import load_hook

HEADER = "# Hot Cache\n\nKeep ~3 newest entries.\n<!-- template -->\n"


def _entry(date, body="body text\n"):
    return "## %s title\n\n%s\n" % (date, body)


def _write(path, txt):
    path.write_text(txt, encoding="utf-8")
    return str(path)


def test_noop_within_budget(tmp_path):
    hot = tmp_path / "hot.md"
    orig = HEADER + _entry("2026-08-28") + _entry("2026-08-29") + _entry("2026-08-30")
    arch = tmp_path / "hot-archive.md"
    mod = load_hook("session-start")
    mod._rotate_hot(_write(hot, orig), str(arch))
    assert not arch.exists()
    assert hot.read_text(encoding="utf-8") == orig


def test_archives_oldest_beyond_three(tmp_path):
    hot = tmp_path / "hot.md"
    arch = tmp_path / "hot-archive.md"
    mod = load_hook("session-start")
    mod._rotate_hot(_write(hot, HEADER + "".join(_entry("2026-08-%02d" % d) for d in range(25, 30))), str(arch))
    txt = hot.read_text(encoding="utf-8")
    for d in ("27", "28", "29"):
        assert "2026-08-%s" % d in txt
    for d in ("25", "26"):
        assert "2026-08-%s" % d not in txt
    archived = arch.read_text(encoding="utf-8")
    assert "2026-08-25" in archived and "2026-08-26" in archived
    assert "archived from hot.md" in archived
    assert "2026-08-29" not in archived          # kept entry never leaks into the archive


def test_undated_entries_always_kept(tmp_path):
    hot = tmp_path / "hot.md"
    arch = tmp_path / "hot-archive.md"
    mod = load_hook("session-start")
    entries = (_entry("2026-08-25") + "## no date here\n\nundated body\n\n"
               + "".join(_entry("2026-08-%02d" % d) for d in (26, 27, 28)))
    mod._rotate_hot(_write(hot, HEADER + entries), str(arch))
    txt = hot.read_text(encoding="utf-8")
    assert "undated body" in txt
    assert "2026-08-28" in txt and "2026-08-25" not in txt
    assert "2026-08-25" in arch.read_text(encoding="utf-8")


def test_missing_file_noop(tmp_path):
    mod = load_hook("session-start")
    mod._rotate_hot(str(tmp_path / "absent.md"), str(tmp_path / "hot-archive.md"))  # must not raise
    assert not (tmp_path / "hot-archive.md").exists()
