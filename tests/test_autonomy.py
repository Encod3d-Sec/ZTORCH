"""Tests for the scope.md autonomy envelope (CAI L0-L3) in offensive.py.

Standalone: plain `python3 tests/test_autonomy.py` (no pytest fixtures; each
test_* is a plain callable, failures raise). Also collects clean under pytest.
"""
import contextlib
import io
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import offensive  # noqa: E402


def _vault(tmp):
    """Fresh bb engagement in a temp vault (skills/wiki symlinked to the real
    ones, like test_board; setup/ is never read via --vault)."""
    vault = Path(tmp) / "vault"
    (vault / "targets").mkdir(parents=True)
    for sub in ("skills", "wiki"):
        (vault / sub).symlink_to(ROOT / sub, target_is_directory=True)
    offensive.main(["--vault", str(vault), "init", "demo", "--type", "bb"])
    eng = vault / "targets" / "demo"
    offensive.build_index(eng, vault)
    return vault, eng


def _set_autonomy(eng, value):
    """Rewrite the scaffolded scope.md's autonomy line (None strips it)."""
    p = eng / "scope.md"
    lines = [l for l in p.read_text().splitlines()
             if not l.strip().startswith("autonomy:")]
    if value is not None:
        lines.append("autonomy: %s" % value)
    p.write_text("\n".join(lines) + "\n")


def _next(vault, eng, **kw):
    row = {"id": "4a:1", "asset": "web1", "vuln class": "sqli", "arsenal": "payloads/sqli",
           "skill": "hunt-sqli", "tool": "sqlmap", "status": "[ ]", "poc": "", "poc_kind": ""}
    row.update(kw)
    offensive.write_board(eng, [row])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = offensive.main(["--vault", str(vault), "--eng", str(eng), "next"])
    return rc, buf.getvalue()


def test_parse_present():
    with tempfile.TemporaryDirectory() as tmp:
        vault, eng = _vault(tmp)
        _set_autonomy(eng, "L1")
        assert offensive.autonomy_of(eng) == ("L1", "")
        _set_autonomy(eng, "l0")            # case-insensitive
        assert offensive.autonomy_of(eng)[0] == "L0"
        _set_autonomy(eng, "full")          # legacy pre-L-scale value
        assert offensive.autonomy_of(eng)[0] == "L3"


def test_parse_absent_defaults_l2():
    with tempfile.TemporaryDirectory() as tmp:
        vault, eng = _vault(tmp)
        _set_autonomy(eng, None)            # back-compat: old engagements
        lvl, note = offensive.autonomy_of(eng)
        assert lvl == "L2"
        assert "no autonomy" in note


def test_parse_invalid_defaults_l2():
    with tempfile.TemporaryDirectory() as tmp:
        vault, eng = _vault(tmp)
        _set_autonomy(eng, "banana")
        lvl, note = offensive.autonomy_of(eng)
        assert lvl == "L2"
        assert "unknown" in note


def test_banner_carries_level():
    with tempfile.TemporaryDirectory() as tmp:
        vault, eng = _vault(tmp)
        _set_autonomy(eng, "L1")
        rc, out = _next(vault, eng)
        assert rc == 0
        assert "AUTONOMY L1" in out         # PASS banner line


def test_l0_advisory_fires_on_exploit_row():
    with tempfile.TemporaryDirectory() as tmp:
        vault, eng = _vault(tmp)
        _set_autonomy(eng, "L0")
        rc, out = _next(vault, eng)         # sqli is an EXPLOIT_CLASS
        assert rc == 0
        assert "AUTONOMY L0 advisory" in out


def test_l2_no_advisory():
    with tempfile.TemporaryDirectory() as tmp:
        vault, eng = _vault(tmp)
        _set_autonomy(eng, "L2")
        rc, out = _next(vault, eng)
        assert rc == 0
        assert "AUTONOMY L2" in out                     # banner still there
        assert "AUTONOMY L2 advisory" not in out        # but no advisory line


def test_l0_no_advisory_on_non_exploit_row():
    with tempfile.TemporaryDirectory() as tmp:
        vault, eng = _vault(tmp)
        _set_autonomy(eng, "L0")
        rc, out = _next(vault, eng, **{"vuln class": "recon", "arsenal": "wiki/recon",
                                       "skill": "", "tool": "nmap"})
        assert rc == 0
        assert "AUTONOMY L0 advisory" not in out


if __name__ == "__main__":
    fns = [(n, f) for n, f in sorted(globals().items())
           if n.startswith("test_") and callable(f)]
    for name, fn in fns:
        fn()
        print("ok: %s" % name)
    print("all %d autonomy tests passed" % len(fns))
