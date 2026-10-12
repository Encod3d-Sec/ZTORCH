"""Tests for the hermes-pattern offensive-doctor rework (Finding accumulator,
numbered manual summary, --ack suppression ledger, --fix scaffolding).

Same fixture shape as tests/test_doctor.py (a tempdir vault copy of what the
doctor actually reads) plus a synthetic engagement under targets/ that the
doctor is steered at with --eng.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _mk_vault(dest):
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    dest.mkdir(parents=True)
    for sub in ("scripts", "skills", "wiki"):
        shutil.copytree(ROOT / sub, dest / sub, ignore=ignore)
    fx = dest / "tests" / "fixtures"
    fx.mkdir(parents=True)
    shutil.copytree(ROOT / "tests" / "fixtures" / "offensive", fx / "offensive", ignore=ignore)
    shutil.copy(ROOT / "tests" / "fixtures" / "bench-manifest.json", fx / "bench-manifest.json")
    shutil.copytree(ROOT / "tests" / "fixtures" / "bench-eng", fx / "bench-eng", ignore=ignore)
    # setup/templates: offensive.py init needs setup/templates/offensive/ for its
    # smoke run, and ensure_optional_file scaffolds the optional files from here
    shutil.copytree(ROOT / "setup" / "templates", dest / "setup" / "templates",
                    ignore=ignore)


def _mk_eng(vault, name="demo"):
    """Synthetic bugbounty engagement (file names only, no client data)."""
    d = vault / "targets" / name
    d.mkdir(parents=True)
    (vault / "targets" / "active.md").write_text(name + "\n")
    for fn in ("scope.md", "loot.md", "Approach.md", "Killchain.md",
               "oob.md", "Vuln-index.md"):
        (d / fn).write_text("synthetic fixture\n")
    (d / "state.md").write_text(
        "---\nengagement_type: bugbounty\n---\n\nsynthetic fixture\n")
    return d


def _run(vault, *args):
    r = subprocess.run([sys.executable, str(vault / "scripts" / "offensive-doctor.py"),
                        "--eng", "demo", *args], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def test_issues_numbered_summary_and_nonzero_exit(tmp_path):
    vault = tmp_path / "vault"
    _mk_vault(vault)
    _mk_eng(vault)
    (vault / "scripts" / "routing.json").write_text("{}")   # empty routing table
    rc, out = _run(vault)
    assert rc != 0, "doctor should fail on a broken routing table:\n" + out
    assert "Manual items" in out, out
    assert "1. [FAIL]" in out, out
    assert "routing" in out.lower()


def test_ack_suppresses_advisory_and_gives_zero_exit(tmp_path):
    vault = tmp_path / "vault"
    _mk_vault(vault)
    eng = _mk_eng(vault)
    (eng / "oob.md").unlink()               # the one manual advisory
    rc, out = _run(vault)
    assert rc != 0, "missing optional file should gate the exit:\n" + out
    assert "1. [WARN]" in out, out

    rc, out = _run(vault, "--ack", "1")
    assert rc == 0, "--ack should exit 0 after persisting:\n" + out
    acks = json.loads((eng / ".doctor-acks.json").read_text())
    assert len(acks) == 1
    (aid, entry), = acks.items()
    assert aid and entry.get("acked_at"), acks

    rc, out = _run(vault)                   # plain rerun: rendered acked, exit clean
    assert rc == 0, "acked advisory must not count toward the exit:\n" + out
    assert "ACKED" in out and "0 FAIL" in out, out

    (eng / ".doctor-acks.json").unlink()    # removing the file un-acks
    rc, out = _run(vault)
    assert rc != 0, "deleting .doctor-acks.json must un-suppress the advisory:\n" + out


def test_fix_scaffolds_missing_optional_file(tmp_path):
    vault = tmp_path / "vault"
    _mk_vault(vault)
    eng = _mk_eng(vault)
    (eng / "oob.md").unlink()
    rc, out = _run(vault, "--fix")
    assert rc == 0, "--fix should clear the advisory it repaired:\n" + out
    assert (eng / "oob.md").is_file(), "--fix did not scaffold oob.md:\n" + out
    assert "demo" in (eng / "oob.md").read_text()   # {{ENGAGEMENT}} substituted
    assert "--fix applied 1 auto-repair(s)" in out, out
