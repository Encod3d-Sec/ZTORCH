"""Tests for scripts/offensive-doctor.py (subsystem health check).

The doctor self-locates its vault (VAULT = dir above scripts/), like ClaudeBrain's
campaign-doctor.py. So the healthy test runs the REPO's doctor; the broken test
runs a COPY of the repo whose routing table has been corrupted.
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCTOR = ROOT / "scripts" / "offensive-doctor.py"


def _run(doctor_path, *args):
    r = subprocess.run([sys.executable, str(doctor_path), *args],
                       capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def test_doctor_passes_on_healthy_vault():
    rc, out = _run(DOCTOR)
    assert rc == 0, "doctor failed on the healthy repo:\n" + out
    assert "0 FAIL" in out, out


def test_doctor_flags_missing_routing_table(tmp_path):
    vault = tmp_path / "vault"
    shutil.copytree(ROOT, vault,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
    # corrupt the routing table: overwrite hunt-core with a stub that has no
    # `## Routing table (machine-readable)` section.
    core = vault / "skills" / "hunt" / "hunt-core" / "SKILL.md"
    core.write_text("---\nname: hunt-core\n---\n# hunt-core\n\nno routing table here\n")
    rc, out = _run(vault / "scripts" / "offensive-doctor.py")
    assert rc != 0, "doctor should fail when the routing table is broken:\n" + out
    assert "routing" in out.lower()


def test_phase_check_is_frontmatter_scoped(tmp_path):
    """A body `phase: exploit` line with no frontmatter `phase:` key must FAIL,
    not false-pass a whole-file regex."""
    vault = tmp_path / "vault"
    shutil.copytree(ROOT, vault,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
    bogus = vault / "wiki" / "tools" / "zz-bogus-tool.md"
    bogus.write_text(
        "---\n"
        "title: \"Bogus Tool\"\n"
        "type: tool\n"
        "---\n\n"
        "## Purpose\n\n"
        "Body text that happens to mention phase: exploit but is not frontmatter.\n\n"
        "## Core usage\n\n"
        "```bash\nbogus-tool --run\n```\n"
    )
    rc, out = _run(vault / "scripts" / "offensive-doctor.py")
    assert rc != 0, "doctor should fail on a page with no frontmatter phase key:\n" + out
    assert "phase" in out.lower()
    assert "zz-bogus-tool" in out


def test_4b_hollow_only_warns_if_all_rows_blank(tmp_path):
    """Blanking the FIRST windows routing row's arsenal must not warn as long
    as another windows row still carries an arsenal."""
    vault = tmp_path / "vault"
    shutil.copytree(ROOT, vault,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
    core = vault / "skills" / "hunt" / "hunt-core" / "SKILL.md"
    text = core.read_text()
    old_row = "| windows | windows | hunt-windows | windows-privesc | privesc-exploit-arsenal |"
    new_row = "| windows | windows | hunt-windows | windows-privesc |  |"
    assert old_row in text, "fixture row not found - hunt-core routing table changed"
    core.write_text(text.replace(old_row, new_row, 1))
    rc, out = _run(vault / "scripts" / "offensive-doctor.py", "--verbose")
    assert "WARN  4b OS route not hollow: windows" not in out, (
        "doctor warned on windows even though another windows row still has an arsenal:\n" + out)
    assert "4b OS route not hollow: windows" in out, "check should still run and print (verbose)"
