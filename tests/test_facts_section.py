import importlib.util
import os

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_spec = importlib.util.spec_from_file_location("st", os.path.join(VAULT, "scripts", "status.py"))
st = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(st)

FACTS = """# State

| host | ip | notes |
|---|---|---|

## Facts

One line per fact.

| key | conf | summary |
|---|---|---|
| `target/web01` | confirmed | `10.0.0.5 nginx; verify: curl -I http://10.0.0.5` |
| `auth/creds` | tentative | `admin:admin on 8100` |
| `negative/smb-null` | confirmed | `tested X, no exploitable vuln` |
| ~~exploit/old~~ (deprecated 2026-09-01) | deprecated | superseded |
"""


def test_facts_line_counts(tmp_path):
    d = tmp_path / "eng"
    d.mkdir()
    (d / "state.md").write_text(FACTS, encoding="utf-8")
    line = st.facts_line(str(d))
    assert line == "facts: 3 (2 confirmed, 1 tentative, 1 neg)"


def test_facts_line_none_without_section(tmp_path):
    d = tmp_path / "eng"
    d.mkdir()
    (d / "state.md").write_text("# State\n", encoding="utf-8")
    assert st.facts_line(str(d)) is None


def test_state_templates_carry_facts_section():
    for et in ("pentest", "ctf", "bugbounty"):
        t = open(os.path.join(VAULT, "setup", "templates", et, "state.md"),
                 encoding="utf-8").read()
        assert "## Facts" in t and "| key | conf | summary |" in t, et


def test_selfheal_appends_facts_header(tmp_path):
    d = tmp_path / "eng"
    d.mkdir()
    (d / "state.md").write_text("# State\n\n| host | ip |\n|---|---|\n", encoding="utf-8")
    # ponytail: brief said `import engagement_init`, but the file is dash-named
    # (engagement-init.py) and is not importable under that name; use the repo's
    # canonical importlib pattern (test_engagement_init_board_heal.py).
    _ei = importlib.util.spec_from_file_location(
        "engagement_init", os.path.join(VAULT, "skills", "hooks", "engagement-init.py"))
    engagement_init = importlib.util.module_from_spec(_ei)
    _ei.loader.exec_module(engagement_init)
    engagement_init.self_heal_facts(str(d))
    assert "## Facts" in (d / "state.md").read_text(encoding="utf-8")
    engagement_init.self_heal_facts(str(d))    # idempotent
    assert (d / "state.md").read_text(encoding="utf-8").count("## Facts") == 1
