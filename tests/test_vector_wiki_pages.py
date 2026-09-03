"""New wiki/tools/ pages for the vector-workflow baselines must satisfy offensive_index.py's
tool-page lint contract: frontmatter + a runnable ## Core usage command."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import offensive_index  # noqa: E402

NEW_PAGES = ["mimikatz", "gtfobins", "linux-exploit-suggester", "linkfinder"]


def test_new_tool_pages_exist():
    for slug in NEW_PAGES:
        assert (ROOT / "wiki" / "tools" / (slug + ".md")).is_file(), "%s.md missing" % slug


def test_new_tool_pages_pass_lint():
    # _lint_tool_index dies loud (SystemExit) on any malformed page under wiki/tools/;
    # a clean run over the real vault root means every page, including the 4 new ones, passes.
    try:
        offensive_index._lint_tool_index(ROOT)
    except SystemExit:
        raise AssertionError("a wiki/tools/ page failed _lint_tool_index")


def test_new_tool_pages_have_frontmatter_phase():
    for slug in NEW_PAGES:
        text = (ROOT / "wiki" / "tools" / (slug + ".md")).read_text(encoding="utf-8")
        fm = offensive_index._frontmatter(text)
        assert fm.get("phase"), "%s.md missing frontmatter phase:" % slug
