import os
import subprocess

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SH = os.path.join(VAULT, "scripts", "wiki-section.sh")

PAGE = "# T\n\n## Alpha one\n\nalpha body\n\n## Beta two\n\nbeta body\n"


def _run(tmp_path, *args):
    p = tmp_path / "page.md"
    p.write_text(PAGE, encoding="utf-8")
    return subprocess.run(["bash", SH, str(p)] + list(args),
                          capture_output=True, text=True)


def test_list(tmp_path):
    r = _run(tmp_path, "--list")
    assert r.returncode == 0
    assert "alpha-one" in r.stdout and "beta-two" in r.stdout


def test_section_body(tmp_path):
    r = _run(tmp_path, "alpha-one")
    assert "alpha body" in r.stdout and "beta body" not in r.stdout


def test_missing_slug_is_error(tmp_path):
    r = _run(tmp_path, "nope")
    assert r.returncode != 0
