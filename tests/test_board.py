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
    for sub in ("skills", "wiki"):
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
    """Every emitted 4a row (implied + base-superset) resolves to a real
    skill AND arsenal against the real routing table, for all 3 types.
    Guards the finding that BASE_CLASSES drifted from the routing vocabulary."""
    vault, eng = _mk_eng(tmp_path, "wordpress, apache")
    index = offensive.build_index(eng, vault)

    for etype in ("pentest", "bb", "ctf"):
        rows = offensive.derive_rows(eng, index, etype)
        assert rows, "%s should derive rows" % etype
        # every base class for this type is in the routing vocabulary
        for cls in offensive.BASE_CLASSES[etype]:
            assert cls in offensive._class_info(index), \
                "%s base class %r not a routing class" % (etype, cls)
        for r in rows:
            assert r["skill"], "%s row %r has blank skill" % (etype, r)
            assert r["arsenal"], "%s row %r has blank arsenal" % (etype, r)
            assert r["tool"], "%s row %r has blank tool" % (etype, r)
