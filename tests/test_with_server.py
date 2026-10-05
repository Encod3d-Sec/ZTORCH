"""with_server: port-poll readiness + guaranteed teardown."""
import socket
import subprocess
import sys
import time
from pathlib import Path

VT = Path(__file__).resolve().parents[1]
SCRIPT = VT / "scripts" / "with_server.py"


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _open(port):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def test_ready_runs_and_reaps():
    port = _free_port()
    r = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--serve", "%s -m http.server %d --bind 127.0.0.1" % (sys.executable, port),
            "--port", str(port), "--timeout", "20",
            "--", sys.executable, "-c", "print('ran-marker')",
        ],
        capture_output=True, text=True, timeout=60,
    )
    assert r.returncode == 0, r.stderr
    assert "ran-marker" in r.stdout
    deadline = time.time() + 5
    while _open(port) and time.time() < deadline:
        time.sleep(0.5)
    assert not _open(port), "server not torn down"


def test_timeout_unready_port_fails_clean():
    port = _free_port()
    r = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--serve", "%s -c 'import time; time.sleep(30)'" % sys.executable,
            "--port", str(port), "--timeout", "2",
            "--", "true",
        ],
        capture_output=True, text=True, timeout=60,
    )
    assert r.returncode != 0
    assert "not ready" in (r.stdout + r.stderr)
