"""W2-8: scope-guard.py's RoE tool regexes (BRUTEFORCE/DOS/ACTIVE) and its out-of-scope
host/IP regexes (HOST_RE/IP_RE/IP6_RE) were searched without blanking quoted spans first, so a
command merely MENTIONING a tool/host inside a string (echo, grep) got falsely DENIED."""
import importlib.util
import os

VAULT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "scope_guard", os.path.join(VAULT, "skills", "hooks", "scope-guard.py"))
scope_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scope_guard)


def test_real_bruteforce_invocation_still_matches():
    assert scope_guard.BRUTEFORCE.search(scope_guard._strip_noise("hydra -L users -P pass.txt ssh://T"))


def test_quoted_bruteforce_mention_not_matched():
    """The exact false-positive class W2-8 names."""
    cmd = 'echo "avoid hydra on this box"'
    assert not scope_guard.BRUTEFORCE.search(scope_guard._strip_noise(cmd))


def test_quoted_active_tool_mention_not_matched():
    cmd = 'grep -n "nmap" notes.txt'
    assert not scope_guard.ACTIVE.search(scope_guard._strip_noise(cmd))


def test_real_active_tool_invocation_still_matches():
    assert scope_guard.ACTIVE.search(scope_guard._strip_noise("nmap -sV 10.1.1.5"))


def test_quoted_out_of_scope_host_mention_not_flagged():
    sc = {"out_of_scope": ["10.0.0.5"]}
    cmd = 'echo "10.0.0.5 is explicitly out of scope"'
    assert scope_guard.ip_out_of_scope(cmd, sc) == []


def test_real_out_of_scope_host_still_flagged():
    sc = {"out_of_scope": ["10.0.0.5"]}
    cmd = "curl http://10.0.0.5/admin"
    assert scope_guard.ip_out_of_scope(cmd, sc) == ["10.0.0.5"]
