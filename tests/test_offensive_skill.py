"""Shape test for the /offensive thin-driver skill."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "workflow" / "offensive" / "SKILL.md"


def test_skill_shape():
    assert SKILL.exists(), "SKILL.md missing"
    text = SKILL.read_text(encoding="utf-8")

    # frontmatter name
    fm = text.split("---", 2)
    assert len(fm) >= 3, "no frontmatter block"
    assert "name: offensive" in fm[1], "frontmatter name: offensive missing"

    # the three loop commands
    assert "offensive.py" in text and "next" in text
    assert "note" in text and "--arsenal" in text
    assert "done" in text

    # the replaced entry points must not appear
    for banned in ("bb-workflow", "ctf-workflow", "pt-workflow"):
        assert banned not in text, "banned string present: %s" % banned
