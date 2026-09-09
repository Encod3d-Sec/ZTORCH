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
    if not data.strip():
        return b"(no output)\n"
    if BYPASS_LEAD.match(cmd or ""):
        return data
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
    path = None
    if len(data) > t and not BYPASS_LEAD.match(cmd or ""):
        d = _ingest_dir()
        if d:
            path = os.path.join(d, "%s-%d.txt" % (
                re.sub(r"[^a-z0-9]+", "-", (cmd.split() or ["out"])[0].split("/")[-1])[:24].strip("-"),
                int(time.time())))
    sys.stdout.buffer.write(econ(data, cmd, path, t))


if __name__ == "__main__":
    main()
