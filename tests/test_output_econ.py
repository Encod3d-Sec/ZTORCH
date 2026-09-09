"""Output economy for the VM bridge (scripts/output_econ.py, wired into vm-ssh.sh).
Host-CLI pattern: under THRESH -> ANSI-stripped passthrough; over -> full output persisted
to the active engagement's ingest/ and replaced by a stub (byte counts + saved path +
newline-aligned preview). Empty -> marker. base64-headed commands BYPASS (the screenshot
pull pipes `vm-ssh.sh 'base64 -w0 f.png' | base64 -d` onward and needs exact bytes)."""
import os
import sys

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
