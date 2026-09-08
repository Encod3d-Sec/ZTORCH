"""tmux-nudge matcher tests (pure _should_nudge; main() is covered by the
zg-nudge pattern it copies)."""
import importlib.util
import os

VAULT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "tmux_nudge", os.path.join(VAULT, "skills", "hooks", "tmux-nudge.py"))
tmux_nudge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tmux_nudge)


def test_fires_on_bare_heavy_tool():
    assert tmux_nudge._should_nudge("nmap -sV -sC 10.10.10.5")


def test_fires_inside_vmsh_wrapper():
    assert tmux_nudge._should_nudge("bash /root/vm.sh 'nmap -sV 10.10.10.5'")


def test_fires_inside_vm_ssh_wrapper():
    assert tmux_nudge._should_nudge("bash scripts/vm-ssh.sh 'sqlmap -u http://x --batch'")


def test_fires_on_listener():
    assert tmux_nudge._should_nudge("nc -lvnp 4444")


def test_silent_when_tmux_present():
    assert not tmux_nudge._should_nudge(
        "bash /root/vm.sh \"tmux new-window -t eng -n nm 'nmap -sV 10.10.10.5'\"")


def test_silent_on_tmux_aware_drivers():
    assert not tmux_nudge._should_nudge(
        "bash scripts/vm-scan.sh --win nmap eng 10.10.10.5 'nmap -sV 10.10.10.5'")
    assert not tmux_nudge._should_nudge(
        "bash scripts/vm-bg.sh eng sqlmap-x 'sqlmap -u http://x --batch'")
    assert not tmux_nudge._should_nudge(
        "bash scripts/vm-rsh.sh --create --win nm eng 'nmap -sV 10.10.10.5'")


def test_silent_on_readback_and_help():
    assert not tmux_nudge._should_nudge(
        "bash /root/vm.sh 'tmux capture-pane -p -t eng:nm | tail'")
    assert not tmux_nudge._should_nudge("nmap --version")


def test_silent_on_output_reads_and_light_cmds():
    assert not tmux_nudge._should_nudge("cat nmap-out.txt | head")
    assert not tmux_nudge._should_nudge("curl -s http://10.10.10.5/")
