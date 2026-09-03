"""Tests for the vector-workflow pipeline: OSINT pre-pass, per-asset vector baseline+exception
rows, priority ordering (web > ad_windows > linux), all through the real hunt-core routing table."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import offensive  # noqa: E402


def _mk_eng(tmp_path, tech, deadends_rows=""):
    """Init an engagement, set one asset's tech tags + optional Deadends rows.
    Mirrors tests/test_board.py::_mk_eng exactly."""
    vault = tmp_path / "vault"
    (vault / "targets").mkdir(parents=True)
    # symlink (read-only for these tests); setup/ is never read via --vault
    for sub in ("skills", "wiki"):
        (vault / sub).symlink_to(ROOT / sub, target_is_directory=True)

    offensive.main(["--vault", str(vault), "init", "demo", "--type", "bb"])
    eng = vault / "targets" / "demo"

    state = eng / "state.md"
    row = "| web1 | http://t/ | / | | %s | recon | |" % tech
    lines = state.read_text().splitlines()
    sep = next(i for i, l in enumerate(lines)
               if l.startswith("|") and set(l.strip("| ")) <= set("-:| "))
    lines.insert(sep + 1, row)
    state.write_text("\n".join(lines) + "\n")
    if deadends_rows:
        de = eng / "Deadends.md"
        de.write_text(de.read_text() + deadends_rows)

    offensive.build_index(eng, vault)
    return vault, eng


def test_osint_rows_emitted_once_keyed_to_engagement_name(tmp_path):
    vault, eng = _mk_eng(tmp_path, "nginx")
    index = offensive.build_index(eng, vault)
    rows = offensive.derive_rows(eng, index, "bb")
    osint_rows = [r for r in rows if r["asset"] == "demo"]
    classes = {r["vuln class"] for r in osint_rows}
    assert classes == {"osint-subdomain", "osint-leaks"}
    for r in osint_rows:
        assert r["skill"], "OSINT rows must resolve a non-blank skill"


def test_web_vector_baseline_and_exception(tmp_path):
    vault, eng = _mk_eng(tmp_path, "nginx, wordpress")
    index = offensive.build_index(eng, vault)
    rows = offensive.derive_rows(eng, index, "bb")
    by = {(r["asset"], r["vuln class"]): r for r in rows}

    for cls in ("content-discovery", "js-extract", "recon-nuclei", "recon-nikto"):
        assert ("web1", cls) in by, "web baseline class %s missing" % cls
        assert by[("web1", cls)]["skill"], "%s must resolve a skill" % cls

    # narrow exception: wordpress fingerprint present -> wpscan-scan added
    assert ("web1", "wpscan-scan") in by
    assert by[("web1", "wpscan-scan")]["tool"] == "wpscan"


def test_ad_windows_vector_baseline(tmp_path):
    vault, eng = _mk_eng(tmp_path, "smb, kerberos, port 445")
    index = offensive.build_index(eng, vault)
    rows = offensive.derive_rows(eng, index, "bb")
    by = {(r["asset"], r["vuln class"]): r for r in rows}
    assert ("web1", "ad") in by
    assert ("web1", "windows") in by


def test_linux_vector_baseline(tmp_path):
    vault, eng = _mk_eng(tmp_path, "ssh, linux, port 22")
    index = offensive.build_index(eng, vault)
    rows = offensive.derive_rows(eng, index, "bb")
    by = {(r["asset"], r["vuln class"]): r for r in rows}
    assert ("web1", "linux-svc-enum") in by
    assert by[("web1", "linux-svc-enum")]["skill"]


def test_no_vector_row_has_blank_skill_across_all_types(tmp_path):
    """Every new pseudo-class resolves a real skill+arsenal against the real routing table,
    for all 3 engagement types -- mirrors test_board.py::test_no_base_row_has_blank_skill."""
    vault, eng = _mk_eng(tmp_path, "nginx, wordpress, smb, kerberos, ssh, linux")
    index = offensive.build_index(eng, vault)
    new_classes = {"osint-subdomain", "osint-leaks", "content-discovery", "js-extract",
                   "recon-nuclei", "recon-nikto", "wpscan-scan", "linux-svc-enum"}
    for etype in ("pentest", "bb", "ctf"):
        rows = offensive.derive_rows(eng, index, etype)
        by_class = {r["vuln class"]: r for r in rows}
        for cls in new_classes:
            assert cls in by_class, "%s missing for etype=%s" % (cls, etype)
            assert by_class[cls]["skill"], "%s has blank skill for etype=%s" % (cls, etype)
            assert by_class[cls]["arsenal"], "%s has blank arsenal for etype=%s" % (cls, etype)


def test_deadend_suppresses_vector_row(tmp_path):
    vault, eng = _mk_eng(tmp_path, "nginx, wordpress",
                          deadends_rows="| web1 | wpscan-scan | tried | n/a | 2026-01-01 | never |\n")
    index = offensive.build_index(eng, vault)
    rows = offensive.derive_rows(eng, index, "bb")
    by = {(r["asset"], r["vuln class"]): r for r in rows}
    assert ("web1", "wpscan-scan") not in by


def test_idempotent_no_duplicate_rows(tmp_path):
    vault, eng = _mk_eng(tmp_path, "nginx, wordpress, smb")
    index = offensive.build_index(eng, vault)
    rows = offensive.derive_rows(eng, index, "bb")
    keys = [(r["asset"], r["vuln class"]) for r in rows]
    assert len(keys) == len(set(keys)), "derive_rows must not emit duplicate (asset, class) rows"
