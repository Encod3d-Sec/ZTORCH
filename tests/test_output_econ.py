"""Output economy for the VM bridge (scripts/output_econ.py, wired into vm-ssh.sh).
Host-CLI pattern: under THRESH -> ANSI-stripped passthrough; over -> full output persisted
to the active engagement's ingest/ and replaced by a stub (byte counts + saved path +
newline-aligned preview). Empty -> marker. base64-headed commands BYPASS (the screenshot
pull pipes `vm-ssh.sh 'base64 -w0 f.png' | base64 -d` onward and needs exact bytes)."""
import os
import sys
import time
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                                "scripts"))
import output_econ as oe


def test_empty_becomes_marker():
    assert oe.econ(b"   \n", "whatever", None) == b"(no output)\n"


def test_small_passthrough_strips_ansi_and_blanks():
    out = oe.econ(b"\n\n\x1b[32mOK\x1b[0m\n\n\n", "cmd", None)
    assert out == b"OK\n"


def test_oversize_stub_names_saved_path_and_remaining():
    data = b"x" * (oe.THRESH + 5000) + b"\ntail line\n"
    stub = oe.econ(data, "feroxbuster -u http://t", "/ingest/feroxbuster-1.txt")
    assert len(stub) < 4000
    assert b"/ingest/feroxbuster-1.txt" in stub
    assert b"re-run narrow" in stub
    assert str(len(data)).encode() in stub


def test_base64_head_bypasses_even_oversize():
    big = b"QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVphYmNkZWZnaGlqa2xtbm9wcXJzdHV2d3h5eg==" * 2000
    assert oe.econ(big, "base64 -w0 /tmp/shot.png", None) is not None
    assert oe.econ(big, "base64 -w0 /tmp/shot.png", None) == big
    # env-prefixed wrapper form also bypasses
    assert oe.BYPASS_LEAD.match("env base64 -w0 f.png")


def test_preview_cut_is_newline_aligned():
    data = b"".join(b"line %04d %s\n" % (i, b"y" * 50) for i in range(2000))  # >> PREVIEW
    stub = oe.econ(data, "nmap -p- t", None)
    prev = stub.split(b"Preview (first ", 1)[1].split(b" bytes):\n", 1)[1]
    prev = prev.rsplit(b"\n[", 1)[0]
    assert not prev.endswith(b"y\n") or prev.endswith(b"\n")   # cut on a line boundary
    assert prev.endswith(b"\n") or len(prev) <= oe.PREVIEW


def test_low_context_stamp_tightens_cap(tmp_path, monkeypatch):
    """Fresh .ctx-low-stamp (tool-telemetry fired: window <=25% free) -> 10KB tier, so
    a 15KB dump stubs instead of passing through. Absent or stale stamp -> normal cap.
    The stub is lossless either way (full output still saved to ingest/)."""
    ing = tmp_path / "ingest"
    ing.mkdir()
    monkeypatch.setattr(oe, "_ingest_dir", lambda: str(ing))
    data = b"x" * 15_000
    assert oe.econ(data, "nmap t", None) == data + b"\n"      # no stamp: 30KB cap, passthrough
    stamp = tmp_path / ".ctx-low-stamp"
    stamp.write_text("")
    out = oe.econ(data, "nmap t", "/ingest/nmap-1.txt")       # fresh stamp: 10KB tier
    assert b"[output economy]" in out and b"/ingest/nmap-1.txt" in out
    assert b"10000" in out                                   # names the tightened cap
    old = time.time() - 1800
    os.utime(stamp, (old, old))
    assert oe.econ(data, "nmap t", None) == data + b"\n"      # stale: back to normal


# --- RC frame (pass 10): vm-ssh.sh appends `echo __ZT_RC=$?__` and pipes with ZT_FRAME=1.
# pipefail carries ssh 255, but a TRUNCATED stream still looks complete - the trailer
# is the completeness signal. Unframed callers (tests above) never send one.

def test_rc0_trailer_stripped_from_clean_output(monkeypatch):
    monkeypatch.setenv("ZT_FRAME", "1")
    assert oe.econ(b"ok\n__ZT_RC=0__\n", "cmd", None) == b"ok\n"


def test_nonzero_rc_prefixes_remote_exit(monkeypatch):
    monkeypatch.setenv("ZT_FRAME", "1")
    assert oe.econ(b"boom\n__ZT_RC=2__\n", "cmd", None) == b"[remote exit 2]\nboom\n"


def test_truncated_framed_stream_flagged(monkeypatch):
    monkeypatch.setenv("ZT_FRAME", "1")
    out = oe.econ(b"partial out\n", "cmd", None)   # framed, no trailer: transport died
    assert out.startswith(b"[bridge: truncated")
    assert b"partial out" in out


def test_empty_framed_no_trailer_is_bridge_failure(monkeypatch):
    monkeypatch.setenv("ZT_FRAME", "1")
    assert oe.econ(b"  \n", "cmd", None) == b"(bridge failed: no output and no exit trailer)\n"


def test_unframed_empty_still_plain_marker(monkeypatch):
    monkeypatch.delenv("ZT_FRAME", raising=False)
    assert oe.econ(b"  \n", "cmd", None) == b"(no output)\n"


def test_bypass_pipe_gets_clean_bytes_trailer_stripped(monkeypatch):
    monkeypatch.setenv("ZT_FRAME", "1")
    blob = b"iVBORw0KGgoAAAANSUhEUg\n"               # a base64 image pull
    assert oe.econ(blob + b"__ZT_RC=0__\n", "base64 -w0 /tmp/shot.png", None) == blob


def test_main_exits_1_on_dead_bridge(monkeypatch):
    """Framed + empty + no trailer -> SystemExit(1): vm-ssh.sh's pipefail reports
    the dead bridge instead of a clean-looking 0 with '(no output)'."""
    monkeypatch.setenv("ZT_FRAME", "1")
    monkeypatch.setattr(sys, "argv", ["output_econ.py", "nmap t"])
    # patch at the sys-module level: pytest's stdin/stdout replacement objects
    # expose .buffer as a read-only property
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(
        buffer=SimpleNamespace(read=lambda: b"")))
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(
        buffer=type("W", (), {"write": staticmethod(lambda d: None)})()))
    with pytest.raises(SystemExit) as ex:
        oe.main()
    assert ex.value.code == 1
