---
name: kali-seat
description: Kali attack-seat procedure - Windows-to-WSL-to-VMware VM chain, direct-ssh and vm.sh rules, tmux-on-VM convention. Use for "kali seat", "the VM", "work from WSL", or before any offensive command against an in-scope target (Hermes or ZCode seat).
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
  and skill links are already wired for this seat (`.zcode/config.json`, `~/.claude/skills/`).
- **Target commands: ALWAYS on the VM.** Hermes seat: `ssh kali-vm '<cmd>'` (form 0). ZCode seat:
  through vm.sh. Never scan or attack from WSL or Windows directly - they have no VPN route
  and would leak the host IP.
- **Harness scripts:** run from either side. Windows seat uses the bridge
  (`scripts/win-vm.sh`); inside WSL everything is direct
  (`bash /root/vm.sh '<cmd>'`, `qmd`).

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
- **Windows seat: run the bridge as `OUTPUT_ECON=0 bash scripts/win-vm.sh ...`** - the script's
  output-economy step resolves `python3` to the WindowsApps store alias, which cannot read the
  MSYS path and fails every call. The WSL-side `vm.sh` path is unaffected.
- **The RoE gate is live on BOTH seats now.** On Hermes, scope-guard runs as a native
  pre_tool_call shell hook (adapter: Torchv2 `hermes/agent-hooks/torch-hook-adapter.py`,
  registered in `%LOCALAPPDATA%/hermes/config.yaml`): out-of-scope terminal commands are REALLY
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
- Note: headless parallel lanes (the old `fleet-lane` concept) target a ZCode CLI that does not
  ship with the desktop app; dormant until a headless CLI exists. Use Agent-tool sub-agents for
  parallel work meanwhile.
