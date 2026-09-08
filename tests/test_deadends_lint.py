"""Deadends placeholder-row lint: rows like `why exhausted: exhausted` or a bare `tried X -- no`
pass the anti-loop gate on shape but carry no signal, and duplicate asset x class rows bloat the
G4 suppression lookup. The lint counts them; the Stop hook nudges once to fill/dedupe."""
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "hooks"))
_spec = importlib.util.spec_from_file_location(
    "_engagement", ROOT / "skills" / "hooks" / "_engagement.py")
_engagement = importlib.util.module_from_spec(_spec)
sys.modules["_engagement"] = _engagement
_spec.loader.exec_module(_engagement)

HDR = ("| asset | class | what was tried | why exhausted | date | reopen-if |\n"
       "|-------|-------|----------------|---------------|------|-----------|\n")


def _mk(tmp_path, rows):
    d = tmp_path / "eng"
    d.mkdir(exist_ok=True)
    (d / "Deadends.md").write_text(HDR + "".join(r + "\n" for r in rows), encoding="utf-8")
    return str(d)


def test_placeholder_why_cells_counted(tmp_path):
    d = _mk(tmp_path, [
        "| web1 | sqli | sqlmap dump | exhausted | 2026-09-01 | - |",
        "| web1 | xss | reflected probe | failed | 2026-09-01 | - |",
        "| web1 | ssrf | gopher sweep |  | 2026-09-01 | - |",
    ])
    assert _engagement.deadends_placeholder_rows(d) == 3


def test_real_why_rows_are_clean(tmp_path):
    d = _mk(tmp_path, [
        "| web1 | sqli | sqlmap dump | parameterized; no error oracle in any quote context | 2026-09-01 | new param |",
    ])
    assert _engagement.deadends_placeholder_rows(d) == 0


def test_duplicate_asset_class_pairs_counted(tmp_path):
    d = _mk(tmp_path, [
        "| web1 | sqli | sqlmap dump | parameterized everywhere | 2026-09-01 | - |",
        "| web1 | sqli | sqlmap dump | parameterized everywhere | 2026-09-01 | - |",
    ])
    assert _engagement.deadends_placeholder_rows(d) == 1   # the duplicate only


def test_empty_template_is_clean(tmp_path):
    d = _mk(tmp_path, [])
    assert _engagement.deadends_placeholder_rows(d) == 0


def test_missing_file_clean(tmp_path):
    assert _engagement.deadends_placeholder_rows(str(tmp_path / "none")) == 0


def test_closeout_nudges_on_placeholders():
    src = (ROOT / "skills" / "hooks" / "close-out.py").read_text(encoding="utf-8")
    assert "deadends_placeholder_rows" in src
