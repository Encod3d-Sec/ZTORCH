#!/usr/bin/env python3
"""Output economy for the VM bridge (scripts/vm-ssh.sh pipes through this).

Big tool output is the recurring context killer (nmap/ferox/linpeas dumps).
Host-CLI pattern, adapted: under THRESH bytes -> pass through (ANSI stripped);
over -> persist the FULL output to the active engagement's ingest/ and return a
stub (newline-aligned preview + byte counts + the saved path). Empty -> marker.

Bypass: OUTPUT_ECON=0 env, or a command whose first real token is `base64`
(the screenshot/image pull pipes `vm-ssh.sh 'base64 -w0 f.png' | base64 -d`
onward and must receive exact bytes; any other known pipe-consumer gets the
same treatment when noticed).
"""
import os
import re
import sys
import time

THRESH = int(os.environ.get("OUTPUT_ECON_BYTES", "30000"))
PREVIEW = 2048
HOT_LINES = 60
ANSI = re.compile(rb"\x1b\[[0-9;]*[a-zA-Z]")
BYPASS_LEAD = re.compile(r"^\s*(?:sudo |env |nohup |nice |time )*base64\d?\b")

LOW_CTX_THRESH = 10_000          # context was <=25% free in the last 15 min: tighten hard

RC_FRAME = re.compile(rb"__ZT_RC=(\d+)__[ \t]*\n?\s*$")   # bridge exit trailer (last line)


def split_frame(data):
    """(payload, rc). vm-ssh.sh appends `echo __ZT_RC=$?__` to every framed
    command; econ strips it here so pipe consumers (base64 pulls included)
    never see it. rc None = no trailer: on a framed stream (ZT_FRAME=1) that
    means the transport died mid-stream, not 'empty output'."""
    m = RC_FRAME.search(data)
    if not m:
        return data, None
    return data[:m.start()].rstrip(b"\n") + b"\n", int(m.group(1))


# ponytail: single-engagement active.md; multi-file active sets are not a thing yet
def _ingest_dir():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        eng = open(os.path.join(root, "targets", "active.md"), encoding="utf-8").read().split()[0]
        d = os.path.join(root, "targets", eng, "ingest")
        os.makedirs(d, exist_ok=True)
        return d
    except Exception:
        return None


def _thresh():
    """Context-aware cap, single source of truth the .ctx-low-stamp tool-telemetry
    writes when the window hits <=25% free. A fresh stamp (15 min) -> tighten to
    LOW_CTX_THRESH so a big passthrough cannot land while context is scarce; the
    stub is lossless either way (full output still saved to ingest/)."""
    d = _ingest_dir()
    if d:
        try:
            if time.time() - os.path.getmtime(
                    os.path.join(os.path.dirname(d), ".ctx-low-stamp")) < 900:
                return min(THRESH, LOW_CTX_THRESH)
        except OSError:
            pass
    return THRESH


def stub(data, path, thresh):
    prev = ANSI.sub(b"", data[:PREVIEW])
    nl = prev.rfind(b"\n")
    if nl > PREVIEW // 2:
        prev = prev[:nl]
    saved = (" Full output saved to: %s" % path) if path else ""
    head = (b"[output economy] %d bytes exceeded %d cap.%s\n"
            b"Preview (first %d bytes):\n" % (len(data), thresh, saved.encode(), len(prev)))
    tail = (b"\n[%d more bytes] re-run narrow: grep/head the saved file, or re-run the "
            b"command with a server-side filter.\n" % (len(data) - len(prev)))
    return head + prev + tail


def econ(data, cmd, path, thresh=None):
    framed = os.environ.get("ZT_FRAME") == "1"
    data, rc = split_frame(data)             # unframed callers never send a trailer
    if not data.strip():
        if framed and rc is None:
            return b"(bridge failed: no output and no exit trailer)\n"
        return b"(no output)\n"
    bypass = BYPASS_LEAD.match(cmd or "")
    if bypass:
        return data                          # byte-exact for pipe consumers (trailer stripped above)
    if framed and rc is None:
        data = b"[bridge: truncated - no exit trailer, transport died mid-stream]\n" + data
    elif rc not in (None, 0):
        data = b"[remote exit %d]\n" % rc + data
    data = ANSI.sub(b"", data) if ANSI.search(data) else data
    if thresh is None:
        thresh = _thresh()
    if len(data) <= thresh:
        # squeeze leading blank runs; trim tail (host pattern, keeps signal lines first)
        return re.sub(rb"^(?:\s*\n)+", b"", data).rstrip(b"\n") + b"\n"
    return stub(data, path, thresh)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    data = sys.stdin.buffer.read()
    if os.environ.get("OUTPUT_ECON") == "0":
        sys.stdout.buffer.write(data)
        return
    t = _thresh()
    framed = os.environ.get("ZT_FRAME") == "1"
    payload, rc = split_frame(data)
    path = None
    if len(payload) > t and not BYPASS_LEAD.match(cmd or ""):
        d = _ingest_dir()
        if d:
            path = os.path.join(d, "%s-%d.txt" % (
                re.sub(r"[^a-z0-9]+", "-", (cmd.split() or ["out"])[0].split("/")[-1])[:24].strip("-"),
                int(time.time())))
    out = econ(data, cmd, path, t)
    sys.stdout.buffer.write(out)
    # a framed stream with no trailer = the bridge itself died (ssh drop mid-stream);
    # exit 1 so `set -o pipefail` in vm-ssh.sh reports it instead of a clean-looking 0
    if framed and rc is None and not data.strip():
        sys.exit(1)


if __name__ == "__main__":
    main()
