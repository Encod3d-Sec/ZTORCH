"""Batch 6: finding-grade auto-capture. The late-evidence drift (~17x): a finding lands, the
curated card never gets made until the Stop-gate forces a backfill. Fix: capture-poc detects
high-precision finding signals in the just-captured pair and PERSISTS the pair as a poc/ card
automatically (no re-execution of attacker commands - the raw pair is already in hand), then
names the capture.sh card command. Deduped on the signal token."""
import glob
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOOK = ROOT / "skills" / "hooks" / "capture-poc.py"


def _load():
    import importlib.util
    spec = importlib.util.spec_from_file_location("capture_poc", HOOK)
    m = importlib.util.module_from_spec(spec)
    sys.modules["capture_poc"] = m
    spec.loader.exec_module(m)
    return m


def _run_hook(vault, cmd, out):
    env = dict(os.environ, ZTORCH_VAULT=str(vault))
    payload = json.dumps({"tool_name": "Bash",
                          "tool_input": {"command": cmd},
                          "tool_response": out})
    return subprocess.run([sys.executable, str(HOOK)], input=payload,
                          capture_output=True, text=True, timeout=30, env=env)


def _mk_vault(tmp_path):
    t = tmp_path / "targets" / "engz"
    (t / "poc").mkdir(parents=True, exist_ok=True)
    (t / "state.md").write_text("# State\n", encoding="utf-8")
    (tmp_path / "targets" / "active.md").write_text("engz\n", encoding="utf-8")
    return tmp_path


def test_signal_flag_in_output():
    m = _load()
    assert m._finding_signal("curl -s http://10.0.0.5/", "THM{f4k3_fl4g_here}") is not None
    assert m._finding_signal("curl -s http://10.0.0.5/", "use {'a': 1} dict") is None


def test_signal_root_shell_and_cracked_hash():
    m = _load()
    assert m._finding_signal("bash exp.sh", "uid=0(root) gid=0(root)") is not None
    assert m._finding_signal("psexec.py x", "NT AUTHORITY\\SYSTEM") is not None
    assert m._finding_signal("hashcat -m 0 h.txt", "Recovered........: 2/3 (66.67%)") is not None
    assert m._finding_signal("curl -s http://10.0.0.5/", "200 OK\nhello world") is None


def test_signal_quiet_on_ordinary_scan_output():
    m = _load()
    assert m._finding_signal("nmap -sV 10.0.0.5", "22/tcp open ssh OpenSSH 8.2") is None


def test_hook_persists_the_pair_as_a_card(tmp_path):
    v = _mk_vault(tmp_path)
    r = _run_hook(v, "bash /root/vm.sh 'curl -s http://10.0.0.5/flag'",
                  "THM{f4k3_fl4g_here}")
    assert r.returncode == 0
    cards = glob.glob(str(v / "targets" / "engz" / "poc" / "*auto*.md"))
    assert len(cards) == 1, "finding-grade pair must auto-persist as a poc card"
    txt = pathlib.Path(cards[0]).read_text(encoding="utf-8")
    assert "THM{f4k3_fl4g_here}" in txt and "curl -s http://10.0.0.5/flag" in txt
    assert "capture.sh" in r.stdout, "must name the card command for the operator-facing render"


def test_deduped_on_the_signal_token(tmp_path):
    v = _mk_vault(tmp_path)
    _run_hook(v, "bash /root/vm.sh 'curl -s http://10.0.0.5/flag'", "THM{f4k3_fl4g_here}")
    _run_hook(v, "bash /root/vm.sh 'curl -s http://10.0.0.5/flag'", "THM{f4k3_fl4g_here}")
    cards = glob.glob(str(v / "targets" / "engz" / "poc" / "*auto*.md"))
    assert len(cards) == 1


def test_no_card_on_ordinary_output(tmp_path):
    v = _mk_vault(tmp_path)
    _run_hook(v, "bash /root/vm.sh 'curl -s http://10.0.0.5/'", "200 OK homepage")
    assert glob.glob(str(v / "targets" / "engz" / "poc" / "*auto*.md")) == []
