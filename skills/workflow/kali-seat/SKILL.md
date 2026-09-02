---
name: kali-seat
description: Operating procedure for the WSL/Kali attack seat on this machine - the seat chain (Windows ZCode -> wsl.exe -> WSL kali -> SSH -> VMware Kali VM), which side runs what, vm.sh usage rules, tmux-on-VM convention, and the vault's three path forms. Use when working the VM, running target tooling, driving tmux/reverse shells on the VM, when the user says "work from WSL", "use vm.sh", "kali seat", "the VM", or before any offensive command against an in-scope target.
---

# Kali seat: Windows host -> WSL kali -> VMware Kali VM

## Seat map (this machine)

| Layer | Where | What lives there |
|---|---|---|
| ZCode agent | Windows desktop app, shell = Git Bash | AGENTS.md, hooks, wiki edits, offensive driver, scope-guard |
| WSL distro `kali-linux` | user `kali` (interactive) / `root` (tooling) | `/root/vm.sh` + `/root/creds.txt` (VM ip/user/password), sshpass, qmd |
| VMware Kali VM (hostname `TZ`) | `192.168.23.128` (from creds.txt) | VPN (tun0), ALL offensive tooling (nmap/ffuf/nuclei/nxc/linpeas), chromium, tmux sessions |

The vault is ONE working copy seen under three paths:

| Form | Path | Use |
|---|---|---|
| Windows | `C:\Users\Lenovo\Documents\ObisidianVaults\ZTorch\ZTorch` | ZCode workspace |
| WSL | `/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch` | native script runs in WSL |
| WSL short | `/opt/ztorch` (symlink -> the /mnt/c path) | `cd /opt/ztorch` and work |

## Which side runs what

- **Agent session (Windows):** everything cognitive - wiki-first, offensive driver, hooks. Hooks
  and skill links are already wired for this seat (`.zcode/config.json`, `.zcode/skills/`).
- **Target commands: ALWAYS on the VM through vm.sh.** Never scan or attack from WSL or
  Windows directly - they have no VPN route and would leak the host IP.
- **Harness scripts:** run from either side. Windows seat uses the bridge
  (`scripts/win-vm.sh`); inside WSL everything is direct
  (`bash /root/vm.sh '<cmd>'`, `qmd`).

## Invocation forms (pick by need)

0. **Fastest: direct ssh, Windows -> VM.** Key-based (`setup/vm-key.sh` arms it once), no WSL hop, fails fast:
   ```
   bash scripts/vm-ssh.sh '<remote command>'          # root@VM, VPN + tools + chromium live here
   VM_SH="$(pwd)/scripts/vm-ssh.sh" bash scripts/win-rsh.sh <session> '<ps cmd>'
   ```
   Use this for quick tool calls and driver runs. Fallbacks below cover WSL state and key loss.
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
- **The RoE gate crosses the bridge:** `scope-guard.py` parses vm.sh/ssh/wsl-wrapped commands,
  so out-of-scope hosts and forbidden tooling are denied no matter which form you use.
- Evidence still lands in the vault (`targets/<eng>/poc/` via `capture.sh` / `shot.py`) - the
  seat changes the transport, never the discipline.

## Setup / repair

- **ONE verdict, either seat:** `python3 scripts/offensive-doctor.py` (hooks + skills + seat wiring
  + VM reachability + offensive driver, in one run).
- Windows seat: `bash setup/bootstrap.sh` (bridge checks, skills, wiki-search MCP, `--index`).
- WSL side: `bash setup/install-hooks.sh` (re-creates the `/opt/ztorch` symlink, git
  safe.directory, verifies `/root/vm.sh` + creds + sshpass + qmd).
- Note: headless parallel lanes (the old `fleet-lane` concept) target a ZCode CLI that does not
  ship with the desktop app; dormant until a headless CLI exists. Use Agent-tool sub-agents for
  parallel work meanwhile.
