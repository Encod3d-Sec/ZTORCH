"""vm-handler.sh port-selection tests (no VM; exercises the free-egress-port picker)."""
import os
import subprocess

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, "scripts", "vm-handler.sh")


def test_selftest_passes():
    # in-script --selftest asserts: 443 bound -> 80, 80+443 bound -> 53, all bound -> error
    p = subprocess.run(["bash", SCRIPT, "--selftest"], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    assert "selftest ok" in p.stdout


def test_picks_free_egress_port_with_mocked_vm(tmp_path):
    # Stub VM_SH so the "bound ports" list is 22,443,53 -> picker must skip 443/53, pick 80.
    fake_vm = tmp_path / "fake_vm.sh"
    fake_vm.write_text('#!/usr/bin/env bash\necho "22 53 443"\n')
    fake_vm.chmod(0o755)
    # Stub vm-scan.sh (called to launch the handler) so nothing real runs.
    scan_stub = tmp_path / "scripts"
    scan_stub.mkdir()
    (scan_stub / "vm-scan.sh").write_text('#!/usr/bin/env bash\nexit 0\n')
    (scan_stub / "vm-scan.sh").chmod(0o755)
    # Copy the real script next to the stubbed vm-scan.sh so its VAULT/scripts path resolves to the stub.
    real = open(SCRIPT).read()
    (scan_stub / "vm-handler.sh").write_text(real)
    (scan_stub / "vm-handler.sh").chmod(0o755)
    env = dict(os.environ, VM_SH=str(fake_vm))
    p = subprocess.run(["bash", str(scan_stub / "vm-handler.sh"), "eng1", "10.9.9.9"],
                       capture_output=True, text=True, env=env)
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip().splitlines()[-1] == "80"   # last line = chosen LPORT
    assert "LPORT=80" in p.stderr
