"""offensive.py plan: dry-run of next (numbered candidates, gate made explicit,
zero state writes)."""
import os
import re
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import offensive  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "offensive"


def _setup(tmp_path):
    vault = tmp_path / "vault"
    (vault / "targets").mkdir(parents=True)
    for sub in ("skills", "wiki", "scripts"):
        shutil.copytree(FIX / sub, vault / sub)
    offensive.main(["--vault", str(vault), "init", "demo", "--type", "bb"])
    eng = vault / "targets" / "demo"
    offensive.build_index(eng, vault)
    (vault / "targets" / "active.md").write_text("demo\n", encoding="utf-8")
    return vault, eng


def test_plan_prints_numbered_candidates_no_writes(tmp_path, capsys, monkeypatch):
    vault, eng = _setup(tmp_path)
    monkeypatch.setenv("ZTORCH_VAULT", str(vault))
    before = {p.name: p.read_text(encoding="utf-8") for p in eng.glob("*.md")}
    rc = offensive.main(["--vault", str(vault), "--eng", str(eng), "plan"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "dry-run" in out
    lines = [ln for ln in out.splitlines() if re.match(r"^\s*\d+\.", ln)]
    assert 0 < len(lines) <= 5
    assert all(ln.rstrip().endswith(("gate: none", "gate: oob")) for ln in lines)
    after = {p.name: p.read_text(encoding="utf-8") for p in eng.glob("*.md")}
    assert before == after
