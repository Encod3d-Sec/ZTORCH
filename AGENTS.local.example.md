# Machine-specific vault access (LOCAL, untracked) - EXAMPLE

Copy this file to `AGENTS.local.md` (which is git-ignored) and fill in your own
machines. The tracked `AGENTS.md` points here, so your real hostnames and user
paths stay out of the published repo. ZCode does not auto-import the file; the
agent reads it when a machine path is needed.

Bold names are hostnames. Run `hostname` to identify the active machine.

`- **<HOSTNAME-A>: ** vault at C:\Users\<you>\Documents\ObisidianVaults\ZTorch\ZTorch `
`- WSL: /mnt/c/Users/<you>/Documents/ObisidianVaults/ZTorch/ZTorch.`
`- **<HOSTNAME-B>:** vault at <another path>`; WSL: `<another /mnt path>`.`

If you only use one machine, you can skip this entirely and just set
`ZTORCH_VAULT` (or `OBSIDIAN_VAULT` / `QMD_VAULT`) in your shell profile - the
path resolvers and hooks self-locate or read those env vars.
