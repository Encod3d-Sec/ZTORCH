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


import importlib.util

sys.path.insert(0, os.path.join(VAULT, "scripts"))    # focused run: offensive.py imports offensive_index
_spec = importlib.util.spec_from_file_location(
    "off", os.path.join(VAULT, "scripts", "offensive.py"))
off = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(off)

_ec_spec = importlib.util.spec_from_file_location(
    "ec", os.path.join(VAULT, "scripts", "eng-close.py"))
ec = importlib.util.module_from_spec(_ec_spec)
_ec_spec.loader.exec_module(ec)

_ROWS = """# Changelog - x

| # | time | host | type | location | content | rollback | verified |
|---|------|------|------|----------|---------|----------|----------|
| 1 | 10:00 | web01 | account | web01 | added u1 | `userdel u1` | yes |
| 2 | 10:05 | web01 | config | /etc/x | edited | `cp /etc/x.bak /etc/x` |  |
"""


def _eng_with_changelog(tmp_path, text=_ROWS):
    eng = tmp_path / "demo"
    eng.mkdir(parents=True)
    (eng / "changelog.md").write_text(text, encoding="utf-8")
    (eng / "state.md").write_text("# State\n", encoding="utf-8")
    return eng


def test_changelog_pending_counts_unverified(tmp_path):
    n, rows = off.changelog_pending(str(_eng_with_changelog(tmp_path)))
    assert n == 1 and any("config" in r for r in rows)


def test_changelog_pending_zero_when_no_file(tmp_path):
    eng = tmp_path / "empty"
    eng.mkdir()
    assert off.changelog_pending(str(eng)) == (0, [])


def test_rollback_script_reverse_order(tmp_path):
    eng = _eng_with_changelog(tmp_path)
    rb = ec._rollback_script(str(eng))
    assert rb.startswith("#!/bin/sh") and "set -x" in rb
    assert rb.index("userdel") > rb.index("cp /etc/x.bak")   # reverse order: row 2 undone first


def test_walkthrough_template_has_cleanup_section():
    t = open(os.path.join(VAULT, "setup", "templates", "_walkthrough.md"),
             encoding="utf-8").read()
    assert "## Cleanup" in t
    assert "config" in t and "accounts" in t
