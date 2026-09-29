"""Tests for offensive.py `board` (4a coverage matrix)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import offensive  # noqa: E402

VAULT = ROOT  # real vault (routing table + tool pages live here)


def _mk_eng(tmp_path, tech, deadends_rows=""):
    """Init an engagement, set one asset's tech tags + optional Deadends rows."""
    vault = tmp_path / "vault"
    (vault / "targets").mkdir(parents=True)
    # symlink the real routing/tool sources so build_index sees them (read-only for
    # these tests -- a copytree of skills/+wiki/'s 600+ small files costs seconds per
    # test on this filesystem; setup/ is never read via --vault, dropped entirely)
    for sub in ("skills", "wiki", "scripts"):
        (vault / sub).symlink_to(ROOT / sub, target_is_directory=True)

    offensive.main(["--vault", str(vault), "init", "demo", "--type", "bb"])
    eng = vault / "targets" / "demo"

    state = eng / "state.md"
    row = "| web1 | http://t/ | / | | %s | recon | |" % tech
    lines = state.read_text().splitlines()
    sep = next(i for i, l in enumerate(lines)
               if l.startswith("|") and set(l.strip("| ")) <= set("-:| "))
    lines.insert(sep + 1, row)  # into the table, before the trailing blank
    state.write_text("\n".join(lines) + "\n")
    if deadends_rows:
        de = eng / "Deadends.md"
        de.write_text(de.read_text() + deadends_rows)

    offensive.build_index(eng, vault)
    return vault, eng


def test_board_rows_from_fingerprints(tmp_path):
    vault, eng = _mk_eng(tmp_path, "wordpress, jenkins",
                         deadends_rows="| web1 | sqli | tried | n/a | 2026-01-01 | never |\n")

    rc = offensive.main(["--vault", str(vault), "--eng", str(eng), "board"])
    assert rc == 0

    rows = offensive.read_board(eng)
    assert rows, "board should have rows"
    by = {(r["asset"], r["vuln class"]): r for r in rows}

    # wordpress+jenkins both fingerprint -> class rce, deduped to one row
    assert ("web1", "rce") in by
    rce = by[("web1", "rce")]
    assert rce["skill"] == "hunt-rce"
    assert rce["tool"] == "metasploit"
    assert rce["arsenal"]  # non-empty, from routing
    assert rce["status"] == "[ ]"

    # G4: (web1, sqli) is in Deadends.md -> suppressed even though sqli is a bb base class
    assert ("web1", "sqli") not in by

    # bb base classes still present (xss is a base class)
    assert ("web1", "xss") in by

    # ids are unique + 4a-tagged
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids))
    assert all(i.startswith("4a:") for i in ids)

    # idempotent: re-run does not duplicate
    n1 = len(rows)
    offensive.main(["--vault", str(vault), "--eng", str(eng), "board"])
    rows2 = offensive.read_board(eng)
    assert len(rows2) == n1


def test_no_base_row_has_blank_skill(tmp_path):
    """Every BASE_CLASSES-sourced row resolves to a real skill AND arsenal
    against the real routing table, for all 3 types. Guards the finding that
    BASE_CLASSES drifted from the routing vocabulary. Vector-baseline rows
    (content-discovery-baseline etc.) may legally carry an empty skill: they
    have no doctrine match and next/done G2-skip an empty skill cell."""
    vault, eng = _mk_eng(tmp_path, "wordpress, apache")
    index = offensive.build_index(eng, vault)

    for etype in ("pentest", "bb", "ctf"):
        rows = offensive.derive_rows(eng, index, etype)
        assert rows, "%s should derive rows" % etype
        # every base class resolves to a non-empty skill+arsenal routing entry
        info = offensive._class_info(index)
        for cls in offensive.BASE_CLASSES[etype]:
            assert cls in info, "%s base class %r not a routing class" % (etype, cls)
            assert info[cls][0], "%s base class %r has blank skill" % (etype, cls)
        for r in rows:
            if r["vuln class"] in offensive.BASE_CLASSES[etype]:
                assert r["skill"], "%s row %r has blank skill" % (etype, r)
            assert r["arsenal"], "%s row %r has blank arsenal" % (etype, r)
            assert r["tool"], "%s row %r has blank tool" % (etype, r)


def test_base_class_fingerprint_gate_and_oos_filter(tmp_path):
    """llm/mcp/cicd base-fallback rows need a fingerprint hint; OOS scope.md hosts
    seed nothing (the 2026-09-29 gis.vplanas/186-boilerplate re-seed bug)."""
    vault, eng = _mk_eng(tmp_path, "nginx")           # plain web asset, no llm/mcp/cicd hints
    rows = offensive.derive_rows(eng, offensive.build_index(eng, vault), "bb")
    classes = {(r["asset"], r["vuln class"]) for r in rows}
    assert not any(c in ("llm", "mcp", "cicd") for _a, c in classes)

    # a hinted asset DOES get the row
    state = eng / "state.md"
    lines = state.read_text().splitlines()
    sep = next(i for i, l in enumerate(lines)
               if l.startswith("|") and set(l.strip("| ")) <= set("-:| "))
    lines.insert(sep + 1, "| ai1 | http://t/ | / | | jenkins copilot | recon | |")
    state.write_text("\n".join(lines) + "\n")
    rows = offensive.derive_rows(eng, offensive.build_index(eng, vault), "bb")
    classes = {(r["asset"], r["vuln class"]) for r in rows}
    assert ("ai1", "cicd") in classes and ("ai1", "llm") in classes

    # OOS frontmatter filter: subdomain + exact match skip ALL rows
    scope = eng / "scope.md"
    scope.write_text(scope.read_text().replace(
        "---\n", "---\nout_of_scope_hosts: [\"vplanas.lt\", \"ai1\"]\n", 1))
    rows = offensive.derive_rows(eng, offensive.build_index(eng, vault), "bb")
    assets = {r["asset"] for r in rows}
    assert "ai1" not in assets
    lines = state.read_text().splitlines()
    sep = next(i for i, l in enumerate(lines)
               if l.startswith("|") and set(l.strip("| ")) <= set("-:| "))
    lines.insert(sep + 1, "| gis.vplanas.lt | http://t/ | / | | nginx | recon | |")
    state.write_text("\n".join(lines) + "\n")
    rows = offensive.derive_rows(eng, offensive.build_index(eng, vault), "bb")
    assert "gis.vplanas.lt" not in {r["asset"] for r in rows}
