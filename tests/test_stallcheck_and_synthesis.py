"""Batch 3+4: mechanical stall signals (stallcheck.py over cmdlog) + state auto-synthesis
(append_draft_chain_rows). The prose forms of both rules sat in skills/hunt and were ignored
under momentum on every engagement to date; these make them fire from data."""
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT / "scripts"))
_spec = importlib.util.spec_from_file_location("stallcheck", ROOT / "scripts" / "stallcheck.py")
stallcheck = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(stallcheck)

sys.path.insert(0, str(ROOT / "skills" / "hooks"))
_espec = importlib.util.spec_from_file_location(
    "_engagement", ROOT / "skills" / "hooks" / "_engagement.py")
_engagement = importlib.util.module_from_spec(_espec)
sys.modules["_engagement"] = _engagement
_espec.loader.exec_module(_engagement)


def _entry(cmd, out):
    return "\n## 2026-09-08 12:00:00\n\n```\n%s\n```\n\n```\n%s\n```\n" % (cmd, out)


def _write_cmdlog(tmp_path, name, entries):
    cdir = tmp_path / "poc" / "cmdlog"
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / name).write_text("".join(entries), encoding="utf-8")
    return str(tmp_path)


FAIL_OUT = "curl: (28) Connection timed out"
OK_OUT = "HTTP/1.1 200 OK\ncode=200"


def test_starvation_fires_on_six_consecutive_failures(tmp_path):
    d = _write_cmdlog(tmp_path, "curl.md", [_entry("curl -s http://10.10.10.5/x", FAIL_OUT)] * 6)
    assert any("starvation" in v.lower() and "10.10.10.5" in v
               for v in stallcheck.check(d))


def test_starvation_quiet_below_threshold_or_reset(tmp_path):
    d = _write_cmdlog(tmp_path, "curl.md", [_entry("curl -s http://10.10.10.5/x", FAIL_OUT)] * 5)
    assert not stallcheck.check(d)                                   # only 5 failures
    d2 = _write_cmdlog(tmp_path, "curl2.md",
                       [_entry("curl -s http://10.10.10.5/x", FAIL_OUT)] * 6
                       + [_entry("curl -s http://10.10.10.5/ok", OK_OUT)])
    assert not stallcheck.check(d2)                                  # tail is a success


def test_hash_rule_fires_on_two_zero_crack_exhausted_runs(tmp_path):
    e = _entry("hashcat -m 1000 hashes.txt rockyou.txt",
               "Status.........: Exhausted\nRecovered......: 0/1 (0.00%) Digests")
    d = _write_cmdlog(tmp_path, "hashcat.md", [e] * 2)
    assert any("hash" in v.lower() for v in stallcheck.check(d))


def test_hash_rule_quiet_when_something_cracked(tmp_path):
    e = _entry("hashcat -m 1000 hashes.txt rockyou.txt",
               "Status.........: Exhausted\nRecovered......: 1/2 (50.00%) Digests")
    d = _write_cmdlog(tmp_path, "hashcat.md", [e] * 2)
    assert not stallcheck.check(d)


def test_capture_poc_wires_stallcheck():
    src = (ROOT / "skills" / "hooks" / "capture-poc.py").read_text(encoding="utf-8")
    assert "stallcheck" in src and ".stall-nudged" in src


# ---- generalized rules (pass 7: per-tool starvation, scanner zero-yield, frozen bg log) ----

def test_starvation_fires_for_ssh_and_names_the_tool(tmp_path):
    d = _write_cmdlog(tmp_path, "ssh.md",
                      [_entry("ssh root@10.10.10.7 id", "ssh: connect to host 10.10.10.7 "
                              "port 22: Connection refused")] * 6)
    vs = stallcheck.check(d)
    assert any("starvation" in v.lower() and "10.10.10.7" in v and "ssh" in v for v in vs)


def test_scan_zero_fires_on_four_empty_nmaps_one_host(tmp_path):
    e = _entry("nmap -p- 10.10.10.9", "All 1000 scanned ports on 10.10.10.9 are closed")
    d = _write_cmdlog(tmp_path, "nmap.md", [e] * 4)
    assert any("zero-yield" in v and "10.10.10.9" in v for v in stallcheck.check(d))


def test_scan_zero_quiet_when_nmap_finds_ports(tmp_path):
    e = _entry("nmap -p- 10.10.10.9", "22/tcp open ssh")
    d = _write_cmdlog(tmp_path, "nmap.md", [e] * 4)
    assert not stallcheck.check(d)


def test_scan_zero_fires_on_nuclei_runs_without_hits(tmp_path):
    e = _entry("nuclei -u http://10.10.10.9", "[INF] No results found")
    d = _write_cmdlog(tmp_path, "nuclei.md", [e] * 4)
    assert any("zero-yield" in v for v in stallcheck.check(d))


def test_scan_zero_quiet_on_nuclei_error_not_a_zero_result(tmp_path):
    # an errored run is NOT evidence the surface is empty
    e = _entry("nuclei -u http://10.10.10.9", "[FTL] no templates found")
    d = _write_cmdlog(tmp_path, "nuclei.md", [e] * 4)
    assert not stallcheck.check(d)


def test_bg_read_stalled_on_two_identical_reads(tmp_path):
    d = _write_cmdlog(tmp_path, "vm-bg.md", [
        _entry("vm-bg.sh --read eng win", "[*] 40% ..."),
        _entry("vm-bg.sh --read eng win", "[*] 40% ...")])
    assert any("frozen" in v.lower() for v in stallcheck.check(d))


def test_bg_read_quiet_when_log_growing(tmp_path):
    d = _write_cmdlog(tmp_path, "vm-bg.md", [
        _entry("vm-bg.sh --read eng win", "[*] 40% ..."),
        _entry("vm-bg.sh --read eng win", "[*] 55% ...")])
    assert not stallcheck.check(d)


def test_capture_poc_wires_empty_streak_and_auto_dead():
    src = (ROOT / "skills" / "hooks" / "capture-poc.py").read_text(encoding="utf-8")
    assert ".empty-streak" in src and "whoami" in src       # empty-output advisory
    assert "auto-stall" in src and "last_move" in src       # doom-loop auto-close


def test_append_draft_chain_rows_synthesizes_and_dedupes(tmp_path):
    d = tmp_path
    (d / "loot.md").write_text(
        "# Loot\n\n| type | value | source | notes |\n|------|-------|--------|-------|\n"
        "| cred | admin:hunter2 | ssh | reuse everywhere |\n"
        "| token | eyJabc.def.ghi | web | jwt |\n", encoding="utf-8")
    (d / "Killchain.md").write_text(
        "# Attack Paths\n\n| path | stage | status | blocker | next-move |\n"
        "|------|-------|--------|---------|-----------|\n", encoding="utf-8")
    assert _engagement.append_draft_chain_rows(str(d)) == 2
    chain = (d / "Killchain.md").read_text(encoding="utf-8")
    assert "admin:hunter2" in chain and "draft (auto)" in chain
    assert _engagement.append_draft_chain_rows(str(d)) == 0      # idempotent


def test_closeout_wires_synthesis():
    src = (ROOT / "skills" / "hooks" / "close-out.py").read_text(encoding="utf-8")
    assert "append_draft_chain_rows" in src and "AUTO-APPENDED" in src
