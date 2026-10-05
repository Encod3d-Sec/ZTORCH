"""capture.sh pkg assembles card + referenced captures into one package file."""
import shutil
import subprocess
from pathlib import Path

VT = Path(__file__).resolve().parents[1]
ENG = VT / "targets" / "testpkg"


def _setup():
    shutil.rmtree(ENG, ignore_errors=True)
    (ENG / "Vulns").mkdir(parents=True)
    (ENG / "poc").mkdir()
    card = ENG / "Vulns" / "FIND-01-HIGH-pkg.md"
    card.write_text(
        "# FIND-01\n\n## Proof of Concept\n\n"
        "Dump confirmed, capture at poc/01-a.txt; second at poc/02-missing.txt\n",
        encoding="utf-8",
    )
    (ENG / "poc" / "01-a.txt").write_text("RAW-A\n", encoding="utf-8")


def test_pkg_assembles_card_and_captures():
    _setup()
    try:
        r = subprocess.run(
            ["bash", "scripts/capture.sh", "pkg", "FIND-01"],
            capture_output=True, text=True, cwd=VT,
        )
        pkgs = sorted((ENG / "poc").glob("*-pkg.md"))
        assert r.returncode == 0, r.stderr
        assert len(pkgs) == 1, r.stdout + r.stderr
        body = pkgs[0].read_text(encoding="utf-8")
        assert "FIND-01" in body
        assert "RAW-A" in body
        assert "MISSING capture" in body and "02-missing.txt" in body
    finally:
        shutil.rmtree(ENG, ignore_errors=True)
