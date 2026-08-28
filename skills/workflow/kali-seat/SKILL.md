---
name: kali-seat
description: Operating procedure for the WSL/Kali attack seat on this machine - the seat chain (Windows ZCode -> wsl.exe -> WSL kali -> SSH -> VMware Kali VM), which side runs what, vm.sh usage rules, tmux-on-VM convention, and the vault's three path forms. Use when working the VM, running target tooling, driving tmux/reverse shells on the VM, when the user says "work from WSL", "use vm.sh", "kali seat", "the VM", or before any offensive command against an in-scope target.
---

# Kali seat: Windows host -> WSL kali -> VMware Kali VM

## Seat map (this machine)

| Layer | Where | What lives there |
|---|---|---|
| ZCode agent | Windows desktop app, shell = Git Bash | AGENTS.md, hooks, wiki edits, campaign driver, scope-guard |
| WSL distro `kali-linux` | user `kali` (interactive) / `root` (tooling) | `/root/vm.sh` + `/root/creds.txt` (VM ip/user/password), sshpass, qmd |
| VMware Kali VM (hostname `TZ`) | `192.168.23.128` (from creds.txt) | VPN (tun0), ALL offensive tooling (nmap/ffuf/nuclei/nxc/linpeas), chromium, tmux sessions |

The vault is ONE working copy seen under three paths:

| Form | Path | Use |
|---|---|---|
| Windows | `C:\Users\Lenovo\Documents\ObisidianVaults\ZTorch\ZTorch` | ZCode workspace |
| WSL | `/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch` | native script runs in WSL |
| WSL short | `/opt/ztorch` (symlink -> the /mnt/c path) | `cd /opt/ztorch` and work |

## Which side runs what

- **Agent session (Windows):** everything cognitive - wiki-first, campaign driver, hooks. Hooks
  and skill links are already wired for this seat (`.zcode/config.json`, `.zcode/skills/`).
- **Target commands: ALWAYS on the VM through vm.sh.** Never scan or attack from WSL or
  Windows directly - they have no VPN route and would leak the host IP.
- **Harness scripts:** run from either side. Windows seat uses the bridges
  (`scripts/win-vm.sh`, `scripts/win-qmd.sh`); inside WSL everything is direct
  (`bash /root/vm.sh '<cmd>'`, `qmd`).

## Invocation forms (same effect, pick by seat)

```
Agent (Windows seat):   bash scripts/win-vm.sh '<remote command>'
WSL interactive (root): sudo -s && cd ~ && ./vm.sh '<remote command>'     # /root IS ~
WSL (any dir):          bash /root/vm.sh '<remote command>'
Driver environment:     VM_SH="$(pwd)/scripts/win-vm.sh" bash scripts/win-rsh.sh <session> '<ps cmd>'
```

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

- Windows seat: `bash setup/win-seat.sh` (bridge checks, skills, wiki-search MCP, `--index`).
- WSL side: `bash /opt/ztorch/setup/wsl-seat.sh` (re-creates the `/opt/ztorch` symlink, git
  safe.directory, verifies `/root/vm.sh` + creds + sshpass + qmd).
