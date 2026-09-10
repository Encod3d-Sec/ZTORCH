"""pass 11 (L6 background-task residuals), functional tests through the REAL scripts:

- vm-scan.sh: same-name window reuse is PROMPT-GATED. The old script sent keystrokes into
  whatever window carried the target name (a live ferox scan was clobbered by a nuclei
  launch once). New: pane back at a shell prompt -> reuse; live pane -> a -N suffixed NEW
  window; all suffixes live -> refuse, zero keys sent.
- autocard.sh: un-carded tabs age in .open-tabs (first-seen epoch); older than 45m with no
  prompt prints one RUNNING line; a died vm-scan carded by the AUTOCARD_ALL sweep keeps its
  -x<rc> slug (the rc capture is no longer trapped inside the finished-prompt gate).

Both run against PATH-shimmed tmux / VM_SH / CAPTURE_SH fakes, so the heredoc escaping and
the window plumbing are exercised for real, not re-implemented."""
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

VAULT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
SCRIPTS = os.path.join(VAULT, "scripts")

FAKE_TMUX = r'''#!/usr/bin/env bash
D="${TMUX_FAKE_DIR:?}"
case "$1" in
  has-session|set-option|resize-window) exit 0 ;;
  list-windows) cat "$D/windows" 2>/dev/null ;;
  capture-pane)
    w=""; prev=""
    for a in "$@"; do [ "$prev" = "-t" ] && w="$a"; prev="$a"; done
    cat "$D/pane-$w" 2>/dev/null ;;
  new-window)
    n=""; prev=""
    for a in "$@"; do [ "$prev" = "-n" ] && n="$a"; prev="$a"; done
    id="$( [ -f "$D/windows" ] && wc -l < "$D/windows" || echo 0)"
    id="@$((${id%% *} + 1))"
    echo "$id $n" >> "$D/windows"; echo "$id" ;;
  send-keys)
    w=""; prev=""
    for a in "$@"; do [ "$prev" = "-t" ] && w="$a"; prev="$a"; done
    echo "$w | $*" >> "$D/sent" ;;
esac
exit 0
'''


def _shim(tmp_path):
    """bin/ with a fake tmux; returns (bindir, statedir)."""
    d = tmp_path / "state"
    d.mkdir()
    b = tmp_path / "bin"
    b.mkdir()
    (b / "tmux").write_text(FAKE_TMUX)
    os.chmod(b / "tmux", 0o755)
    return b, d


def _env(b, d):
    return {**os.environ, "PATH": str(b) + os.pathsep + os.environ["PATH"],
            "TMUX_FAKE_DIR": str(d)}


# ---------------------------------------------------------------- vm-scan.sh

def _run_remote(b, d, *scan):
    """Generate the remote script via --dry-run, then execute it against the fake tmux."""
    dry = subprocess.run(["bash", os.path.join(SCRIPTS, "vm-scan.sh"), "--dry-run"] + list(scan),
                         capture_output=True, text=True, check=True)
    return subprocess.run(["bash", "-c", dry.stdout], capture_output=True, text=True,
                          env=_env(b, d))


def test_vm_scan_live_pane_gets_suffixed_window(tmp_path):
    b, d = _shim(tmp_path)
    (d / "windows").write_text("@1 10-1-1-5\n")
    (d / "pane-@1").write_text("301 Get 200\n302 Get 200\n303 Get 200\n")   # live ferox, no prompt
    r = _run_remote(b, d, "eng1", "10.1.1.5", "nmap -sV 10.1.1.5")
    assert r.stdout.strip().endswith("name=10-1-1-5-2 session=eng1 reused=0")
    sent = (d / "sent").read_text()
    assert sent.startswith("@2 |")                       # keys went to the NEW window
    assert "@1 |" not in sent                            # the live pane was untouched


def test_vm_scan_idle_pane_is_reused(tmp_path):
    b, d = _shim(tmp_path)
    (d / "windows").write_text("@1 10-1-1-5\n")
    (d / "pane-@1").write_text("scan finished\n__ZT_RC=0__\n└─# \n")
    r = _run_remote(b, d, "eng1", "10.1.1.5", "nmap -sV 10.1.1.5")
    assert r.stdout.strip().endswith("name=10-1-1-5 session=eng1 reused=1")
    assert (d / "windows").read_text().count("\n") == 1   # no new window
    assert (d / "sent").read_text().startswith("@1 |")


def test_vm_scan_all_suffixes_live_refuses(tmp_path):
    b, d = _shim(tmp_path)
    (d / "windows").write_text(
        "".join("@%d 10-1-1-5%s\n" % (i, "" if i == 1 else "-%d" % i) for i in range(1, 6)))
    for i in range(1, 6):
        (d / ("pane-@%d" % i)).write_text("still scanning %d\n" % i)
    r = _run_remote(b, d, "eng1", "10.1.1.5", "nmap -sV 10.1.1.5")
    assert r.returncode == 1
    assert "vm-scan: refuse" in r.stdout
    assert not (d / "sent").exists()                     # zero keystrokes sent


# ---------------------------------------------------------------- autocard.sh

def _autocard(tmp_path, eng_dir, panes, windows, all_mode=False):
    """Run the real autocard.sh against fakes; panes = {tab: pane_text}. The engagement
    arg must equal the basename of the real dir under targets/ (autocard resolves
    $VAULT/targets/<name> and exits 0 silently when it is absent)."""
    name = os.path.basename(str(eng_dir).rstrip("/"))
    b = tmp_path / "bin"
    b.mkdir(exist_ok=True)
    d = tmp_path / "state"
    d.mkdir(exist_ok=True)
    vm = b / "vmsh"
    vm.write_text('#!/usr/bin/env bash\neval "$1"\n')
    os.chmod(vm, 0o755)
    cap = b / "capsh"
    cap.write_text('#!/usr/bin/env bash\necho "$*" >> "%s"\n'
                   % os.path.join(eng_dir, "cards"))
    os.chmod(cap, 0o755)
    (b / "tmux").write_text(FAKE_TMUX)
    os.chmod(b / "tmux", 0o755)
    (d / "windows").write_text("".join(w + "\n" for w in windows))
    for tab, text in panes.items():
        (d / ("pane-%s:%s" % (name, tab))).write_text(text)
    env = {**os.environ, "PATH": str(b) + os.pathsep + os.environ["PATH"],
           "TMUX_FAKE_DIR": str(d), "VM_SH": str(vm), "CAPTURE_SH": str(cap)}
    if all_mode:
        env["AUTOCARD_ALL"] = "1"
    return subprocess.run(["bash", os.path.join(SCRIPTS, "autocard.sh"), name],
                          capture_output=True, text=True, env=env)


def test_autocard_ledger_and_running_line(tmp_path):
    eng = Path(tempfile.mkdtemp(prefix=".actest-", dir=os.path.join(VAULT, "targets")))
    try:
        live = "301 Get 200\n302 Get 200\n"
        r = _autocard(tmp_path, eng, {"ferox-1": live}, ["ferox-1"])
        assert r.returncode == 0
        assert not (eng / "cards").exists()              # live tab, not carded
        ledger = (eng / ".open-tabs").read_text()
        assert ledger.startswith("ferox-1=")             # first-seen epoch recorded
        # age it past 45m -> the surfaced in-flight line appears, still no card
        (eng / ".open-tabs").write_text("ferox-1=%d\n" % (time.time() - 3600))
        r = _autocard(tmp_path, eng, {"ferox-1": live}, ["ferox-1"])
        assert "RUNNING >45m" in r.stdout
        assert not (eng / "cards").exists()
    finally:
        shutil.rmtree(eng, ignore_errors=True)


def test_autocard_cards_finished_tab_and_prunes_ledger(tmp_path):
    eng = Path(tempfile.mkdtemp(prefix=".actest-", dir=os.path.join(VAULT, "targets")))
    try:
        done = "scan done\n__ZT_RC=0__\n└─# \n"
        (eng / ".open-tabs").write_text("ferox-1=%d\n" % (time.time() - 3600))
        r = _autocard(tmp_path, eng, {"ferox-1": done}, ["ferox-1"])
        cards = (eng / "cards").read_text()
        assert "auto-ferox-1 ferox-1" in cards and "-x" not in cards
        assert "ferox-1" in (eng / ".carded-tabs").read_text()
        assert "ferox-1" not in (eng / ".open-tabs").read_text()   # ledger pruned
        assert "RUNNING >45m" not in r.stdout           # finished -> silent, not flagged
    finally:
        shutil.rmtree(eng, ignore_errors=True)


def test_autocard_all_sweep_keeps_died_rc_slug(tmp_path):
    eng = Path(tempfile.mkdtemp(prefix=".actest-", dir=os.path.join(VAULT, "targets")))
    try:
        # a LISTENER tab (never shows a prompt) whose sibling vm-scan died with rc=7: the
        # AUTOCARD_ALL sweep must card it, and the rc capture - now outside the gate -
        # must land in the slug so the card reads as died, not clean.
        dead = "Segmentation fault (core dumped)\n__ZT_RC=7__\nstill holding\n"
        r = _autocard(tmp_path, eng, {"ferox-1": dead}, ["ferox-1"], all_mode=True)
        cards = (eng / "cards").read_text()
        assert "auto-ferox-1-x7 ferox-1" in cards
        assert "ferox-1" in (eng / ".carded-tabs").read_text()
    finally:
        shutil.rmtree(eng, ignore_errors=True)
