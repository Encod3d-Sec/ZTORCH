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


def _match(host, sc):
    """Minimal out_of_scope_match stand-in: exact or parent-domain suffix, mirroring
    _engagement.out_of_scope_match's strict-relevant arms without importing the hook module."""
    h = host.lower()
    for o in sc.get("out_of_scope", []):
        o = o.lower().strip()
        if h == o or h.endswith("." + o):
            return True
    return False


def test_out_of_scope_dot_local_host_not_treated_as_filename():
    """Regression: a genuine out-of-scope host ending in .local (the standard AD domain
    suffix) was silently skipped by the FILE_EXT filename heuristic before the scope check
    ever ran -- an out-of-scope-contact bypass on the most common AD host-naming pattern."""
    sc = {"out_of_scope": ["dc01.corp.local"]}
    cmd = "nxc smb dc01.corp.local -u user -p pass"
    assert scope_guard.host_out_of_scope(cmd, sc, _match) == {"dc01.corp.local"}


def test_real_filename_not_flagged_as_host():
    """The FILE_EXT heuristic still applies to a host/token that does NOT match
    out_of_scope -- app.py / config.yml are still correctly left alone."""
    sc = {"out_of_scope": ["dc01.corp.local"]}
    cmd = "cat config.yml app.py"
    assert scope_guard.host_out_of_scope(cmd, sc, _match) == set()


def test_bruteforce_named_tool_still_matches():
    assert scope_guard.BRUTEFORCE.search(scope_guard._strip_noise("hydra -L users -P pass.txt ssh://T"))


def test_bruteforce_nxc_wordlist_spray_matches():
    """Regression: nxc/netexec/crackmapexec were absent from BRUTEFORCE entirely, so a
    no_bruteforce RoE spray via nxc never denied. Fixed tool-agnostically (a wordlist-file
    -u/-p argument is the actual spray signal) rather than bare-naming nxc, which would
    over-block nxc's much more common single-cred enum/module use."""
    cmd = "nxc smb 10.0.0.0/24 -u users.txt -p 'Spring2026!'"
    assert scope_guard.BRUTEFORCE.search(scope_guard._strip_noise(cmd))


def test_bruteforce_nxc_single_cred_not_flagged():
    """A routine single-credential nxc call (no wordlist file) must NOT be treated as
    brute-force -- this is nxc's overwhelmingly common use case."""
    cmd = "nxc smb 10.10.10.5 -u administrator -p 'Password123!' --shares"
    assert not scope_guard.BRUTEFORCE.search(scope_guard._strip_noise(cmd))
