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


def test_vm_scan_quoted_scan_survives_transport(tmp_path):
    """pass 12: a SCAN holding single quotes must arrive in the pane VERBATIM (base64
    transport wrap). Pre-wrap, one bad quote aborted the whole remote script and the
    local tail still exited 0 (silent no-scan)."""
    b, d = _shim(tmp_path)
    r = _run_remote(b, d, "x", "T", "awk '{print $1}' /f")
    sent = (d / "sent").read_text()
    assert "awk '{print $1}' /f; echo __ZT_RC=" in sent


def test_vm_scan_dead_bridge_exits_nonzero(tmp_path):
    """pass 12: VM down / remote abort -> the local caller must SEE the failure (no
    window= line -> exit 1), not a silent exit-0 tip."""
    vmsh = tmp_path / "vmsh-dead"
    vmsh.write_text("#!/usr/bin/env bash\necho 'ssh: connect refused'\nexit 255\n")
    os.chmod(vmsh, 0o755)
    r = subprocess.run(["bash", os.path.join(SCRIPTS, "vm-scan.sh"), "x", "T", "nmap T"],
                       capture_output=True, text=True,
                       env={**os.environ, "VM_SH": str(vmsh)})
    assert r.returncode == 1 and "bridge failed" in r.stderr


def test_autocard_prunes_ledgers_after_session_loss(tmp_path):
    """pass 12: a VM reboot wipes the tabs but not the ledgers. Entries whose name is absent
    from the live window list are dropped from BOTH ledgers (a dead .carded-tabs name must
    stop suppressing a relaunched same-named tab); a LIVE name keeps its .open-tabs epoch
    (the aging clock must survive the sweep, not reset every turn)."""
    eng = Path(tempfile.mkdtemp(prefix=".acprune-", dir=os.path.join(VAULT, "targets")))
    try:
        (eng / ".carded-tabs").write_text("ferox-1\noldtab\n", encoding="utf-8")
        (eng / ".open-tabs").write_text("ferox-1=100\ngone-tab=200\n", encoding="utf-8")
        _autocard(tmp_path, eng, {}, ["main", "ferox-1"])  # oldtab / gone-tab not live
        carded = (eng / ".carded-tabs").read_text().split()
        assert "oldtab" not in carded            # dead name pruned
        assert "ferox-1" in carded               # live name kept (still skip-carded)
        open_tabs = (eng / ".open-tabs").read_text()
        assert "gone-tab" not in open_tabs       # dead name pruned
        assert "ferox-1=100" in open_tabs        # live name KEEPS its first-seen epoch
    finally:
        shutil.rmtree(eng, ignore_errors=True)


# ---------------------------------------------------------------- vm-bg delta/idle

def test_vm_bg_delta_offset_and_idle_hint(tmp_path):
    """pass 16: --delta is a byte-offset incremental read (1st call = full log, 2nd =
    only new bytes), and --status judges silence by the LAUNCH-TIME per-tool idle hint
    ($LOG.idle: pspy 60s, not one global 180s): a log silent 120s reads hung?, and a
    .done marker flips the verdict to done exit=. FAKE_TMUX + a sed-rewriting fake
    vm.sh execute the REAL remote scripts with /dev/shm pointed at tmp."""
    b, d = _shim(tmp_path)
    shm = tmp_path / "shm"
    shm.mkdir()
    vm = b / "vm.sh"
    vm.write_text('#!/usr/bin/env bash\n'
                  'eval "$(sed "s#/dev/shm#%s#g" <<<"$1")"\n' % shm)
    os.chmod(vm, 0o755)
    env = _env(b, d)
    env["VM_SH"] = str(vm)

    def run(*args):
        return subprocess.run(["bash", os.path.join(SCRIPTS, "vm-bg.sh")] + list(args),
                              capture_output=True, text=True, env=env, timeout=30)

    log = shm / "eng1-pspy.log"
    r = run("eng1", "pspy", "pspy64 -f 2>/dev/null")
    assert "launched" in r.stdout
    assert (shm / "eng1-pspy.log.idle").read_text().strip() == "60"   # per-tool hint

    log.write_text("line1\n")
    r1 = run("--delta", "eng1", "pspy")
    assert "line1" in r1.stdout and "(no new output" not in r1.stdout
    r2 = run("--delta", "eng1", "pspy")
    assert "(no new output; 6 bytes total)" in r2.stdout
    log.write_text("line1\nline2\n")
    r3 = run("--delta", "eng1", "pspy")
    assert "line2" in r3.stdout and "line1" not in r3.stdout       # only NEW bytes

    import time as _t
    old = _t.time() - 120
    os.utime(log, (old, old))
    assert "hung?" in run("--status", "eng1", "pspy").stdout       # 120s >= 60s hint
    os.utime(log, None)
    assert "running (" in run("--status", "eng1", "pspy").stdout
    (shm / "eng1-pspy.log.done").write_text("exit=0\n")
    assert "done exit=0" in run("--status", "eng1", "pspy").stdout


def test_vm_bg_delta_vanished_log_resets_offset(tmp_path):
    """SSH-bridge hardening: --delta with the log GONE but a stale .off left over (VM
    reboot / /dev/shm wipe) must print one diagnostic and drop the offset; the old code
    answered '(no new output; 0 bytes total)' with the .off intact forever."""
    b, d = _shim(tmp_path)
    shm = tmp_path / "shm"
    shm.mkdir()
    vm = b / "vm.sh"
    vm.write_text('#!/usr/bin/env bash\n'
                  'eval "$(sed "s#/dev/shm#%s#g" <<<"$1")"\n' % shm)
    os.chmod(vm, 0o755)
    env = _env(b, d)
    env["VM_SH"] = str(vm)

    def run(*args):
        return subprocess.run(["bash", os.path.join(SCRIPTS, "vm-bg.sh")] + list(args),
                              capture_output=True, text=True, env=env, timeout=30)

    log = shm / "eng1-crack.log"
    off = shm / "eng1-crack.log.off"
    log.write_text("line1\n")
    run("--delta", "eng1", "crack")                    # consume the log, .off = 6
    assert off.exists()
    log.unlink()                                       # /dev/shm wiped
    r = run("--delta", "eng1", "crack")
    assert "vanished" in r.stdout and "offset reset" in r.stdout
    assert not off.exists()                            # next --delta starts from 0


def test_vm_rsh_timeout_partial_output_grew_vs_hung(tmp_path):
    """SSH-bridge hardening: on timeout the partial output (sliced after the LAST start
    marker) prints and exit is 2; the stderr verdict splits pane GROWTH (still running,
    stalled output) from zero new bytes across the window (hung) instead of discarding
    everything. A growing vm.sh fake stands in for a hashcat mid-run: no prompt, no end
    marker, output landing on every poll."""
    b, d = _shim(tmp_path)
    env = _env(b, d)
    pane = d / "pane-eng1:shell"

    def rsh(vm, grow):
        body = '#!/usr/bin/env bash\n'
        if grow:
            body += 'case "$1" in *capture-pane*) echo "more hashcat output" >> "%s";; esac\n' % pane
        vm.write_text(body + 'eval "$1"\n')
        os.chmod(vm, 0o755)
        pane.write_text("__RSH_START_9f3a__\nhashcat status line\n")
        return subprocess.run(["bash", os.path.join(SCRIPTS, "vm-rsh.sh"),
                               "--timeout", "3", "eng1", "sleep 60"],
                              capture_output=True, text=True, env={**env, "VM_SH": str(vm)},
                              timeout=30)

    r = rsh(b / "vm_grow", grow=True)                  # pane grows on every capture
    assert r.returncode == 2
    assert "hashcat status line" in r.stdout and "more hashcat output" in r.stdout
    assert "running" in r.stderr and "hung" not in r.stderr

    r = rsh(b / "vm_plain", grow=False)                # pane frozen: zero new bytes
    assert r.returncode == 2
    assert "hashcat status line" in r.stdout
    assert "hung" in r.stderr
