---
name: kali-seat
description: Kali attack-seat procedure - Windows-to-WSL-to-VMware VM chain, direct-ssh and vm.sh rules, tmux-on-VM convention. Use for "kali seat", "the VM", "work from WSL", or before any offensive command against an in-scope target (Hermes seat).
metadata:
  hermes:
    tags: [seat, kali, vm, transport]
    related_skills: [offensive, hunt-core]
---

# Kali seat: Windows host -> WSL kali -> VMware Kali VM

## Wiki

Hub: [[methodology-moc]] - Primary page: [[safe-probing-and-controls]]
Anchors: [[network-discovery]]
**REFS:** [[safe-probing-and-controls]]

## Seat map (this machine)

> **Port note (2026-10-17):** the ACTIVE seat is now the **wsl claude cli** on the
> ZTorch repo (`/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch`). Rows
> labelled "Hermes seat" describe the legacy Windows desktop-app seat and are kept
> for reference; run cognitive work from WSL and convert any Windows path to its
> `/mnt/c/Users/Lenovo/...` equivalent. Kali VM aliases (`kali-vm`, `vm-ssh.sh`,
> `tz@192.168.23.128`) are unchanged.

| Layer | Where | What lives there |
|---|---|---|
| Hermes seat | Windows desktop app, shell = Git Bash | AGENTS.md, hooks, wiki edits, offensive driver, scope-guard |
| WSL distro `kali-linux` | user `kali` (interactive) / `root` (tooling) | `/root/vm.sh` + `/root/creds.txt` (VM ip/user/password), sshpass, qmd |
| VMware Kali VM (hostname `TZ`) | `192.168.23.128` (also via `ssh kali-vm`) | VPN (tun0), ALL offensive tooling (nmap/ffuf/nuclei/nxc/linpeas), chromium, tmux sessions |

The vault is ONE working copy seen under three paths:

| Form | Path | Use |
|---|---|---|
| Windows (Hermes GUI, legacy) | `C:\Users\Lenovo\Documents\ObisidianVaults\HermesTORCH` | legacy desktop-app seat tree - reference only (pre-2026-10-17 primary) |
| WSL (ACTIVE seat) | `/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch` | PRIMARY workspace - wsl claude cli repo (hunt skills + wiki + scripts); native script runs in WSL (vm-ssh.sh transport) |
| Donor | `/mnt/c/Users/Lenovo/Documents/ObisidianVaults/HermesTORCH` | FROZEN upstream/history reference only - legacy skills source; never edited |

## Which side runs what

- **Agent session (Windows):** everything cognitive - wiki-first, offensive driver, hooks. Hooks
  and skill links are already wired for this seat (`~/.hermes/skills/`, profile-scoped).
- **Target commands: ALWAYS on the VM.** Hermes seat: `ssh kali-vm '<cmd>'` (form 0). Legacy seats:
  through vm.sh. Never scan or attack from WSL or Windows directly - they have no VPN route
  and would leak the host IP.
- **Harness scripts:** run from either side. Hermes seat: plain `ssh kali-vm`. Inside WSL
  everything is direct (`bash /root/vm.sh '<cmd>'`, `qmd`). The `scripts/win-vm.sh` bridge is
  fallback only (OUTPUT_ECON=0) - prefer form 0.
- **GitHub push for the vault: run git from WSL, not Windows.** The vault's GitHub identity key
  (`ed_ed25519_github_encod3`, account Encod3d-Sec) lives in WSL root's `~/.ssh`; the Windows-side
  keys are not registered with GitHub, so a Windows `git push` dies with `Permission denied
  (publickey)` after you have already fixed host-key verification. Working form (commit on
  Windows, push over /mnt/c - same working copy, no re-clone):
  `MSYS_NO_PATHCONV=1 wsl.exe -d kali-linux -u root -- bash -lc "git -C /mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch push origin main 2>&1"`
  Before fighting SSH flags on any side, locate where auth actually lives: probe
  `ssh -o BatchMode=yes -T git@github.com` on Windows, WSL, and the VM in one batched pass and
  push from the layer that answers `successfully authenticated`. A first-time
  `Host key verification failed` on Windows is fixed once with
  `ssh-keyscan -t ed25519,rsa github.com >> ~/.ssh/known_hosts`.

## Setup the key path (done once per Windows seat)

`~/.ssh/ztorch_vm` (ed25519, no passphrase) authorized in the VM's `/home/tz/.ssh/authorized_keys`;
`~/.ssh/config` carries the `kali-vm` alias (HostName 192.168.23.128, User tz, the key, accept-new).
Regenerating or re-authorizing: create the key locally, then inject the `.pub` through ANY working
channel - `bash scripts/win-vm.sh "mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo '<pub>' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"`
(bridge logs in as `tz`, so `~/.ssh` is tz's, NOT `/root/.ssh` - the old `/root/.ssh/ztorch_vm`
key path never existed). Then verify `ssh -o BatchMode=yes kali-vm whoami` returns `tz`.

## Invocation forms (pick by need)

0. **Fastest: direct ssh, Windows -> VM (Hermes seat).** `ssh kali-vm '<remote command>'` -
   alias in Windows `~/.ssh/config` (host 192.168.23.128, user `tz`, key `~/.ssh/ztorch_vm`).
   No WSL hop, key auth, fails fast. Health-check the channel with
   `ssh -o BatchMode=yes kali-vm 'whoami'` (expect `tz`; BatchMode so a key
   failure errors instead of hanging on a password prompt). Use for quick tool calls and driver runs; long/live work
   still goes in tmux ON the VM (form 3, via ssh + tmux send-keys/capture-pane).
   - Login user is `tz` (sudo group): sudo prompts for a password, so root-level commands are
     unavailable over this path unless SUDO_PASSWORD is set in the agent's .env.
   - `scripts/vm-ssh.sh` claims key auth as root via `/root/.ssh/ztorch_vm` on the WSL side;
     that key does not exist. Without it the script silently falls back to the creds.txt
     password path (user `tz`, not root). Do not trust its "root@VM" comment.
   Fallbacks below cover WSL state and key loss.
1. **One-shot via WSL.** The agent reaches WSL as root directly - no sudo needed, run vm.sh straight:
   ```
   bash scripts/win-vm.sh '<remote command>'                                  # Windows seat bridge
   wsl.exe -d kali-linux -u root -- bash -lc 'cd /opt/ztorch && <cmd>'       # native WSL one-shot
   wsl.exe -d kali-linux -u root -- /root/vm.sh '<remote command>'           # VM, direct
   ```
2. **Persistent seat session (stateful, ALIVE across passes).** A root bash in /opt/ztorch inside
   a WSL tmux session named `seat`; env, cd, functions and background jobs persist between calls.
   Drive it directly with tmux over the WSL bridge (no dedicated script needed):
   ```
   bash scripts/win-vm.sh "tmux has-session -t seat 2>/dev/null || tmux new-session -d -s seat -c /opt/ztorch bash"
   bash scripts/win-vm.sh "tmux send-keys -t seat '<cmd>' Enter; sleep 2; tmux capture-pane -p -S -20 -t seat"
   ```
   The operator attaches to the SAME live session:
   `powershell.exe` -> `wsl.exe` (login kali:kali) -> `sudo -s` -> `tmux attach -t seat`
   (fresh seats for the operator: after `sudo -s`, `cd /opt/ztorch` and /root/vm.sh is `~`).
3. **On the VM.** vm.sh always runs ONE command (docs/shell-interaction.md). Long/live work goes
   in a tmux window ON THE VM (`vm.sh 'tmux new-session -d -s <name>'`), driven with send-keys /
   capture-pane; PowerShell reverse shells via `scripts/win-rsh.sh`.

## Rules

- **ONE command per vm.sh call**, no sentinel/marker strings; output comes back complete and
  echo-stripped. Full discipline: `docs/shell-interaction.md`. Probe a dead channel with a bare
  `whoami` (non-username answer = the shell fell back to the ATTACKER box: false-RCE trap).
- **Long or live work runs in tmux ON THE VM** (creds.txt convention: everything as root, in a
  tmux window). Start: `vm.sh 'tmux new-session -d -s <name>'`; drive: `vm.sh 'tmux send-keys -t <name> ...'`;
  read: `vm.sh 'tmux capture-pane -p -t <name>'`. PowerShell reverse shells: `scripts/win-rsh.sh`.
- **MSYS gotcha (hand-typed wsl.exe only):** Git Bash rewrites leading-slash args into Windows
  paths. The repo wrappers already set `MSYS_NO_PATHCONV=1`; if you type raw
  `wsl.exe ... ls /root/x` yourself, prefix it.
- **WSL quoting law (any payload through wsl.exe):** wsl.exe re-parses its command line through
  the WSL default shell as root, so EVERY `$` construct in a raw payload (variables, `$(...)`,
  escaped `\$`) expands on the WSL side before vm.sh/ssh ever sees it - multi-line remote scripts
  silently run mangled against wrong paths/sockets. Base64-wrap the payload
 (`echo <b64> | base64 -d | bash` as the remote command) the way `scripts/vm-ssh.sh` and
 `scripts/vm-bridge.sh` do; verify a suspect channel with `echo VMUID=$(id -u)` (1000 = VM,
 0 = the expansion happened in WSL). `vm-scan.sh` now prefers its sibling `scripts/win-vm.sh`
 as VM_SH default (seat-aware); `capture.sh` and anything else with a `/root/vm.sh` default
 still needs an explicit `VM_SH=<repo>/scripts/vm-bridge.sh` on a Windows seat.
 - **win-vm.sh invocation shape:** call it with the REPO-RELATIVE path from the
 repo root (`bash scripts/win-vm.sh ...`) - an absolute `C:/...` path to the
 script makes its output-economy step resolve python3 against a mangled
 `C:\c\...` MSYS path and every call fails. When win-vm.sh is unusable,
 drive the VM directly with `scripts/vm-bridge.sh '<cmd>'` (same base64 law).
 - **vm-scan stale-window refuse:** when the VM tmux SERVER is down
 (`no server running on /tmp/tmux-0/default`), vm-scan's liveness probe
 cannot enumerate windows and treats every name as LIVE - it refuses with
 "windows ... all hold LIVE panes" forever. Root cause on the bridge path: win-vm/vm.sh
 lands as ROOT (server `/tmp/tmux-0`) while engagement tmux sessions live under user
 `tz` (server `/tmp/tmux-1000`). Launch scan windows from a tz-landing channel instead
 (`ssh kali-vm` / `scripts/vm-ssh.sh` via WSL) with `tmux new-window -d -t <eng-session> -n <win> '<cmd>'`,
 or bring the server up first, then retry vm-scan.
- **wsl.exe argv ceiling (~32k chars):** a base64-in-command payload beyond it dies with
  `Argument list too long` (screenshot/PNG pulls hit this first). Pull big artifacts in chunks:
  write the file to /tmp on the VM, `base64 -w0` it there, and fetch the b64 in slices - never
  inline the whole blob in one transport call.
- **Seat-port hygiene for VM browser tunnels:** before binding any WSL/ssh
  forward on a seat loopback port, check `netstat -ano | grep :<port>` for an
  existing LISTENING owner - a seat browser may already hold that port as its
  debug listener, and the collision silently points your CDP client at the
  OPERATOR's personal browser instead of the VM one. Prefer driving VM-browser
  CDP from scripts ON the VM (no tunnel at all); when a tunnel is unavoidable,
  use a dedicated high port nobody else claims and verify the forward's target
  answers `/json/version` with the VM's browser, not a seat one.
- **Trust process argv over tmux pane echo:** `tmux send-keys` of a long command leaves a garbled
  typing echo in the pane/pipe-log (interleaved redraws, stray backspaces) while the process runs
  the CORRECT arguments. Confirm what is actually running with `pgrep -af '<tool>'`, never by
  re-reading the echoed command line.
- **Scope-shim post-sync transient:** the first shim call right after a scope-sync stamp refresh
  can print a one-off `ADVISE: unknown to scope` for an in-scope host (cold cache); re-run the
  same call before treating it as scope drift - the verdict clears to rc 0.
- **Run scope-sync BEFORE the first target-touching lane after any engagement switch** - the
  shim's vault keeps the PREVIOUS engagement's active.md/scope.md until pushed, so a fresh
  engagement's lanes eat zero-packet denies against a stale scope (24h-staleness deny fires
  too). After `offensive.py init` (it repoints targets/active.md), push
  `bash scripts/scope-sync.sh` (or the documented vm-ssh + sudo -S route when direct root ssh
  is rejected) and only then dispatch lanes that send target traffic. In-scope bullets must
  carry machine tokens in the parseable shapes (bare host, `host -- comment`, backticked) -
  comment styles the parser does not know leave the hard deny parsing NOTHING and every host
  comes back ADVISE.
- **Injecting keys/files through win-vm.sh: the command runs INSIDE WSL, so `$PUB` and other
  variables must be expanded on the Windows side before the call (double-quoted string, not
  single-quoted), and `python3` inside WSL is fine there - the WindowsApps python3 breakage
  only affects scripts executed by Git Bash, not the WSL child.**
- **Windows seat: run the bridge as `OUTPUT_ECON=0 bash scripts/win-vm.sh ...`** - the script's
  output-economy step resolves `python3` to the WindowsApps store alias, which cannot read the
  MSYS path and fails every call. The WSL-side `vm.sh` path is unaffected. The general fix for
  ANY repo script that hands a path to the seat's Windows python3: resolve script-relative
  dirs Windows-style - `HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && { pwd -W 2>/dev/null || pwd; })"`
  - because `readlink -f`/plain `pwd` in Git Bash yield `/c/...` MSYS paths Windows python3
  cannot open (hit wl-pick.sh's wordlist-map lookup and win-vm.sh's ECON resolution the same way).
- **The RoE gate is live on BOTH seats now.** On Hermes, scope-guard runs as a native
  pre_tool_call shell hook (adapter: Torchv2 `hermes/agent-hooks/torch-hook-adapter.py`,
  registered in `%LOCALAPPDATA%/hermes/config.yaml` (legacy Hermes GUI seat; under
  the wsl claude cli seat hooks register in the repo/claude settings and this file
  does not exist): out-of-scope terminal commands are REALLY
  blocked, RoE-gated tooling raises the human-approval gate, and it is all driven by the active
  engagement's scope.md. Advisory nudges arrive one turn late (sidecar drain). The
  `skills/hooks/.enforce-off` marker still downgrades enforcement to advisory when a false block
  is in the way.
- Evidence still lands in the vault (`targets/<eng>/poc/` via `capture.sh` / `shot.py`) - the
  seat changes the transport, never the discipline.

## Setup / repair

- **ONE verdict, either seat:** `python3 scripts/offensive-doctor.py` (driver routing table + tool index + SKILL.md + hooks + 4b coverage, plus a live init->board->next smoke test).
- Windows seat: `bash setup/bootstrap.sh` (registers hooks + links skills into `~/.claude/skills/`,
  installs qmd, registers the wiki-search MCP server).
- WSL side: `bash setup/install-hooks.sh` (re-links ~/.claude/vault-hooks -> skills/hooks, registers this machine's hooks in settings.json).
- Note: headless parallel lanes (the old `fleet-lane` concept) target a legacy CLI that does not
  ship with the desktop app; dormant until a headless CLI exists. Use Agent-tool sub-agents for
  parallel work meanwhile.
