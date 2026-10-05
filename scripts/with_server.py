#!/usr/bin/env python3
"""Start one or more servers, wait for their TCP ports, run a command, tear down.

The compliant alternative to blind sleeps: readiness is a poll on the port, and the
finally block guarantees teardown (no zombie servers on a fragile VM).

Usage:
    python3 scripts/with_server.py --serve 'python3 -m http.server 8777' --port 8777 \
        -- python3 tests/smoke.py
Each --serve pairs with one --port (same order). --timeout caps the readiness wait.
"""
import argparse
import shlex
import socket
import subprocess
import sys
import time


def port_open(port, host="127.0.0.1"):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def wait_ports(ports, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if all(port_open(p) for p in ports):
            return True
        time.sleep(0.5)
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--serve", action="append", required=True,
                    help="command that starts a server (repeatable)")
    ap.add_argument("--port", type=int, action="append", required=True,
                    help="TCP port the matching --serve listens on (repeatable)")
    ap.add_argument("--timeout", type=float, default=30.0,
                    help="seconds to wait for readiness (default 30)")
    ap.add_argument("cmd", nargs=argparse.REMAINDER,
                    help="command after -- ; run once all ports answer")
    args = ap.parse_args()
    if len(args.serve) != len(args.port):
        sys.exit("each --serve needs exactly one --port")
    cmd = args.cmd[1:] if args.cmd and args.cmd[0] == "--" else args.cmd
    if not cmd:
        sys.exit("no command given after --")

    procs = [subprocess.Popen(shlex.split(c)) for c in args.serve]
    try:
        if not wait_ports(args.port, args.timeout):
            sys.exit("with_server: ports not ready after %ss: %s"
                     % (args.timeout, args.port))
        return subprocess.call(cmd)
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()


if __name__ == "__main__":
    sys.exit(main())
