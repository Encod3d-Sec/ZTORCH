"""W2-8: scope-guard.py's RoE tool regexes (BRUTEFORCE/DOS/ACTIVE) and its out-of-scope
host/IP regexes (HOST_RE/IP_RE/IP6_RE) were searched without blanking quoted spans first, so a
command merely MENTIONING a tool/host inside a string (echo, grep) got falsely DENIED."""
import importlib.util
import json
import os
import subprocess
import sys

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


def test_bridge_inner_out_of_scope_ip_flagged():
    """Regression (host-internals pass 1): _QUOTED blanking hid everything inside a
    wrapper's quoted argument, so `bash vm.sh 'nmap <oos-ip>'` never matched. The scan
    is per-segment over unwrapped inner commands now (_cmdnorm.segments)."""
    sc = {"out_of_scope": ["10.0.0.5"]}
    assert scope_guard.ip_out_of_scope("bash /root/vm.sh 'nmap -sV 10.0.0.5'", sc) == ["10.0.0.5"]


def test_wrapper_peeled_target_still_flagged():
    """Env-var prefixes and sudo/env/timeout-style wrappers are transport, not command:
    the target underneath is still matched."""
    sc = {"out_of_scope": ["10.0.0.5"]}
    assert scope_guard.ip_out_of_scope(
        "FOO=bar sudo timeout 30 curl http://10.0.0.5/admin", sc) == ["10.0.0.5"]


def test_env_assignment_value_not_scanned():
    """`TOKEN=10.0.0.5 nmap localhost` targets localhost; the env VALUE is not a target
    (peeled as an assignment prefix before scanning)."""
    sc = {"out_of_scope": ["10.0.0.5"]}
    assert scope_guard.ip_out_of_scope("TOKEN=10.0.0.5 nmap localhost", sc) == []


def test_second_segment_target_flagged():
    sc = {"out_of_scope": ["10.0.0.5"]}
    assert scope_guard.ip_out_of_scope("echo ok && curl -s http://10.0.0.5/x", sc) == ["10.0.0.5"]


def test_bridge_inner_quoted_mention_still_exempt():
    """The W2-8 exemption survives the segment rewrite: an OOS IP that is only TEXT inside
    the bridged command's own quoted string stays exempt."""
    sc = {"out_of_scope": ["10.0.0.5"]}
    assert scope_guard.ip_out_of_scope(
        'bash /root/vm.sh \'echo "10.0.0.5 is oos"\'', sc) == []



def test_ip_in_dotted_hostname_not_matched():
    """Pass-2: the DNS-rebind-shaped token `10.5.0.9.evil.com` is a HOSTNAME, not the IP
    10.5.0.9. The old \\b-boundary regex matched the leading octets as an in-scope-looking
    IP (masking the real out-of-scope host). Boundary lookarounds close it."""
    assert scope_guard.IP_RE.search("dig axfr @10.5.0.9.evil.com corp.local") is None


def test_bare_ip_still_matched_everywhere():
    assert scope_guard.IP_RE.search("nmap -sV 10.5.0.9") is not None
    assert scope_guard.IP_RE.search("curl http://10.5.0.9:8080/x") is not None
    assert scope_guard.IP_RE.search("ssh root@10.5.0.9") is not None


def test_dotted_hostname_yields_no_ip_candidates():
    """Functional: the rebind token produces ZERO ip candidates, so the hostname arm owns it."""
    assert scope_guard.ip_out_of_scope("dig axfr @10.5.0.9.evil.com corp.local",
                                       {"out_of_scope": ["10.5.0.9.evil.com"]}) == []


# pass 12: quoting/underscore/path under-blocks + the path-IP over-block
def test_quoted_url_target_flagged():
    sc = {"out_of_scope": ["10.0.0.5"]}
    assert scope_guard.ip_out_of_scope("curl 'http://10.0.0.5/admin'", sc) == ["10.0.0.5"]


def test_quoted_single_host_target_flagged():
    sc = {"out_of_scope": ["dc01.corp.local"]}
    assert scope_guard.host_out_of_scope(
        "ssh 'dc01.corp.local'", sc,
        lambda h, s: h in s["out_of_scope"]) == {"dc01.corp.local"}


def test_underscore_host_label_matches():
    sc = {"out_of_scope": ["web_01.corp.local"]}
    assert scope_guard.host_out_of_scope(
        "nxc smb web_01.corp.local -u '' -p ''", sc,
        lambda h, s: h in s["out_of_scope"]) == {"web_01.corp.local"}


def test_oos_ip_in_url_path_of_inscope_host_not_flagged():
    sc = {"out_of_scope": ["10.0.0.5"]}
    assert scope_guard.ip_out_of_scope(
        "curl https://target.com/archive/10.0.0.5/backup.tar", sc) == []


def test_oos_ip_as_url_authority_still_flagged():
    sc = {"out_of_scope": ["10.0.0.5"]}
    assert scope_guard.ip_out_of_scope("curl http://10.0.0.5/", sc) == ["10.0.0.5"]


def test_data_flag_payload_with_url_still_exempt():
    sc = {"out_of_scope": ["10.0.0.5"]}
    assert scope_guard.ip_out_of_scope("curl --data 'http://10.0.0.5/' http://ok.com/", sc) == []


# ---- RoE tooling = OPERATOR DECISION gate (operator directive 2026-10-05):
# ---- only out-of-scope host/IP denies; RoE-gated tooling asks the operator instead.
ROE_CMD = "hydra -L users.txt -P pass.txt ssh://10.10.10.5"


def _roe_vault(tmp_path, flags="no_bruteforce: true", oos=(), roe_ok=False):
    t = tmp_path / "targets" / "engr"
    t.mkdir(parents=True, exist_ok=True)
    oos_lines = "\n".join("- " + x for x in oos)
    (t / "scope.md").write_text(
        "---\n%s\n---\n\n## Out of scope\n%s\n" % (flags, oos_lines), encoding="utf-8")
    (tmp_path / "targets" / "active.md").write_text("engr\n", encoding="utf-8")
    if roe_ok:
        (t / ".roe-ok").write_text("", encoding="utf-8")
    return tmp_path


def _fire(vault, cmd, enforce_off=False):
    env = dict(os.environ, ZTORCH_VAULT=str(vault),
               ENFORCE_OFF_MARKER=str(vault / ".enforce-off"))
    if enforce_off:
        (vault / ".enforce-off").write_text("", encoding="utf-8")
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
    r = subprocess.run([sys.executable, os.path.join(VAULT, "skills", "hooks",
                                                    "scope-guard.py")],
                       input=payload, capture_output=True, text=True, timeout=30, env=env)
    return json.loads(r.stdout) if r.stdout.strip() else {}


def test_roe_tooling_asks_operator_instead_of_denying(tmp_path):
    out = _fire(_roe_vault(tmp_path), ROE_CMD)["hookSpecificOutput"]
    assert out.get("permissionDecision") == "ask"          # operator gate, not a deny
    assert "OPERATOR DECISION" in out.get("permissionDecisionReason", "")
    assert "no_bruteforce" in out.get("permissionDecisionReason", "")


def test_roe_ok_env_prefix_preapproves_command(tmp_path):
    assert _fire(_roe_vault(tmp_path), "ZT_ROE_OK=1 " + ROE_CMD) == {}


def test_roe_ok_marker_preapproves_engagement(tmp_path):
    assert _fire(_roe_vault(tmp_path, roe_ok=True), ROE_CMD) == {}


def test_out_of_scope_still_denies_even_with_roe_ok(tmp_path):
    """Scope is the one hard guard: an out-of-scope target denies regardless of RoE
    pre-approval."""
    v = _roe_vault(tmp_path, oos=("10.0.0.5",))
    out = _fire(v, "ZT_ROE_OK=1 nmap -sV 10.0.0.5")["hookSpecificOutput"]
    assert out.get("permissionDecision") == "deny"
    assert "out-of-scope" in out.get("permissionDecisionReason", "")


def test_roe_ask_downgrades_to_advisory_under_enforce_off(tmp_path):
    out = _fire(_roe_vault(tmp_path), ROE_CMD, enforce_off=True)["hookSpecificOutput"]
    assert out.get("permissionDecision") is None
    assert "no_bruteforce" in out.get("additionalContext", "")


def test_enforce_off_write_advisory_and_drift_event(tmp_path):
    """Finding B: a Bash command writing skills/hooks/.enforce-off must surface an
    operator-visible ADVISORY (never a deny) and record a drift event in the engagement's
    .events.jsonl - the marker write is an enforcement downgrade happening un-narrated.
    The detector stays narrow: reads, removals, and bare mentions stay silent."""
    hook = os.path.join(VAULT, "skills", "hooks", "scope-guard.py")
    t = tmp_path / "targets" / "engs"
    t.mkdir(parents=True)
    (tmp_path / "targets" / "active.md").write_text("engs\n", encoding="utf-8")
    env = dict(os.environ, ZTORCH_VAULT=str(tmp_path))
    payload = json.dumps({"tool_name": "Bash",
                          "tool_input": {"command": "touch skills/hooks/.enforce-off"}})
    r = subprocess.run([sys.executable, hook], input=payload,
                       capture_output=True, text=True, timeout=30, env=env)
    out = json.loads(r.stdout) if r.stdout.strip() else {}
    hso = out.get("hookSpecificOutput", {})
    assert hso.get("permissionDecision") is None            # advisory only, never a deny
    assert "enforcement downgrade requested via Bash" in hso.get("additionalContext", "")
    ev = (t / ".events.jsonl").read_text(encoding="utf-8")
    assert '"source": "scope-guard"' in ev
    assert ".enforce-off" in ev
    for quiet in ("cat skills/hooks/.enforce-off",
                  "rm -f skills/hooks/.enforce-off",
                  "echo touch .enforce-off > /tmp/note.txt"):
        rq = subprocess.run([sys.executable, hook],
                            input=json.dumps({"tool_name": "Bash",
                                              "tool_input": {"command": quiet}}),
                            capture_output=True, text=True, timeout=30, env=env)
        assert rq.stdout.strip() == "", quiet
