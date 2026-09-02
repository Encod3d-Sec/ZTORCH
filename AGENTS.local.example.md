# Machine-specific vault access (LOCAL, untracked) - EXAMPLE

Copy this file to `AGENTS.local.md` (which is git-ignored) and fill in your own
machines. The tracked `AGENTS.md` points here, so your real hostnames and user
paths stay out of the published repo. ZCode does not auto-import the file; the
agent reads it when a machine path is needed.

Bold names are hostnames. Run `hostname` to identify the active machine.

- **<HOSTNAME-A>:** vault at `C:\Users\<you>\Documents\ObisidianVaults\ZTorch\ZTorch`; WSL: `/mnt/c/Users/<you>/Documents/ObisidianVaults/ZTorch/ZTorch`.
- **<HOSTNAME-B>:** vault at `<another path>`; WSL: `<another /mnt path>`.

If you only use one machine, you can skip this entirely and just set
`ZTORCH_VAULT` (or `OBSIDIAN_VAULT` / `QMD_VAULT`) in your shell profile - the
path resolvers and hooks self-locate or read those env vars.

## Kali VM (target box)

- IP is DHCP-assigned and changes between boots/subnets; the live value lives in the seat's
  `/root/creds.txt` (parsed by `/root/vm.sh`). Record it here as you go, e.g.: `<IP>`,
  ssh user `<user>`. Run everything as root in a named tmux window.
- Reachability gotcha (WSL2 seat): the VM sits on a VMware VMnet the Windows host routes; if
  `bash /root/vm.sh whoami` times out from WSL, check the VM is powered on and the VMnet subnet
  still matches, from the Windows side.

## This seat (<HOSTNAME>, <seat kind - e.g. WSL Claude Code seat / Windows ZCode seat>)

- Hook registration: `~/.claude/settings.json` (global) calls `~/.claude/vault-hooks/*`;
  `~/.claude/vault-hooks` is a symlink -> this vault's `skills/hooks/`. Re-point the symlink to
  switch vaults; per-session vault choice is not possible (hooks self-locate via symlink realpath,
  `ZTORCH_VAULT`/`OBSIDIAN_VAULT` override).
- Skills: `bash setup/install-skills.sh` symlinks every SKILL.md dir into `~/.claude/skills`;
  re-run after adding a skill, restart to rescan.
- Kali VM access from here: `/root/vm.sh` (creds `/root/creds.txt`); vault wrappers
  `scripts/vm-ssh.sh` (delegates to vm.sh, `VM_SH` overridable) and `scripts/win-vm.sh`
  (WSL bridge for a Windows-seat caller).
