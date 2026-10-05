"""skill-lint: advisory frontmatter + body checks over SKILL.md files."""
import importlib.util
from pathlib import Path

# scripts/skill-lint.py has a hyphen in its filename, so it can't be `import`ed directly.
ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "skill_lint", str(ROOT / "scripts" / "skill-lint.py"))
skill_lint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(skill_lint)


def _skill(tmp_path, name="good-skill", desc="Routes X hunts. Use when an X surface appears."):
    d = tmp_path / name
    d.mkdir()
    p = d / "SKILL.md"
    p.write_text(
        "---\nname: %s\ndescription: %s\n---\n\n# %s\n\nBody.\n" % (name, desc, name),
        encoding="utf-8",
    )
    return p


def test_clean_skill_passes(tmp_path):
    assert skill_lint.lint_skill(_skill(tmp_path)) == []


def test_bad_name_fires(tmp_path):
    assert skill_lint.lint_skill(_skill(tmp_path, name="Bad_Name"))


def test_long_description_fires(tmp_path):
    assert skill_lint.lint_skill(_skill(tmp_path, desc="x" * 1025))


def test_angle_bracket_description_fires(tmp_path):
    assert skill_lint.lint_skill(_skill(tmp_path, desc="Use when <cond> appears."))


def test_folded_scalar_description_does_not_fire(tmp_path):
    p = _skill(tmp_path)
    p.write_text(
        "---\nname: good-skill\ndescription: >\n  Folded text, no brackets.\n---\n\n# good-skill\n\nBody.\n",
        encoding="utf-8")
    assert skill_lint.lint_skill(p) == []


def test_unknown_key_fires(tmp_path):
    p = _skill(tmp_path)
    p.write_text(p.read_text(encoding="utf-8").replace(
        "---\nname:", "---\nbogus-key: 1\nname:", 1), encoding="utf-8")
    assert any("bogus-key" in i for i in skill_lint.lint_skill(p))


def test_unbalanced_fences_fire(tmp_path):
    p = _skill(tmp_path)
    p.write_text(p.read_text(encoding="utf-8") + "\n```\nopen fence\n",
                 encoding="utf-8")
    assert any("fence" in i for i in skill_lint.lint_skill(p))


def test_missing_bash_prefix_fires(tmp_path):
    p = _skill(tmp_path)
    p.write_text(p.read_text(encoding="utf-8").replace(
        "Body.", "Run `scripts/capture.sh req` to capture.", 1), encoding="utf-8")
    assert any("bash scripts/" in i for i in skill_lint.lint_skill(p))


def test_house_template_is_clean():
    p = Path(__file__).resolve().parents[1] / "setup" / "templates" / "_skill.md"
    assert skill_lint.lint_skill(p) == []
