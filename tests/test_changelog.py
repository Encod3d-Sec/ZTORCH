import os
import sys

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_changelog_template_carries_columns():
    t = open(os.path.join(VAULT, "setup", "templates", "_changelog.md"),
             encoding="utf-8").read()
    for col in ("| # |", "time", "host", "type", "location", "content",
                "rollback", "verified"):
        assert col in t, col
    assert "Never auto-cleaned" in t


def test_changelog_wired_into_new_engagement_sh():
    t = open(os.path.join(VAULT, "setup", "new-engagement.sh"),
             encoding="utf-8").read()
    assert t.count("changelog") >= 2    # both branches: pentest/bb loop + ctf loop


def test_ensure_optional_file_backfills_changelog(tmp_path):
    sys.path.insert(0, os.path.join(VAULT, "skills", "hooks"))
    import _engagement
    d = tmp_path / "eng"
    d.mkdir()
    _engagement.ensure_optional_file("changelog", str(d))
    p = d / "changelog.md"
    assert p.is_file()
    assert "rollback" in p.read_text(encoding="utf-8")
    _engagement.ensure_optional_file("changelog", str(d))    # idempotent
    assert len(list(d.iterdir())) == 1
