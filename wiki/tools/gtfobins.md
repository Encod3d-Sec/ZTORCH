---
title: "GTFOBins"
type: tool
tags: [linux, privesc, gtfobins, sudo, suid, lookup-table]
date_created: 2026-09-03
date_updated: 2026-09-03
sources: []
phase: postex
---

# GTFOBins

## Purpose

GTFOBins is not a binary to run but a curated lookup site (`https://gtfobins.github.io/`) cataloging
standard Unix binaries that can be abused to bypass local security restrictions: spawning a shell,
reading/writing arbitrary files, or escalating privileges. Each binary's page lists per-context abuse
primitives (`sudo`, SUID, file capabilities, restricted-shell escape, and more), so once you find a
binary a low-priv user can reach in an unusual way, GTFOBins tells you exactly how to weaponize it.

## Installation

Nothing to install -- it's a static site. For offline/air-gapped use, clone the source data and
render it locally, or grep the raw JSON:

```bash
git clone https://github.com/GTFOBins/GTFOBins.github.io
```

The full per-binary command data also exists as machine-readable YAML under
`GTFOBins.github.io/_gtfobins/`, useful for scripting a match against a target's binary list without
a browser.

## Core usage

```bash
find / -perm -4000 2>/dev/null
```

The workflow is always: enumerate which binaries are reachable in an unusual way on the target, then
look each one up.

### Step 1: find abusable binaries on the target

```bash
# sudo rights (no password needed to check)
sudo -l

# SUID-bit binaries
find / -perm -4000 -type f 2>/dev/null

# SGID-bit binaries
find / -perm -2000 -type f 2>/dev/null

# Linux file capabilities (e.g. cap_setuid on a binary)
getcap -r / 2>/dev/null
```

### Step 2: look each binary up by exact context

```
https://gtfobins.github.io/gtfobins/<binary>/
```

Example: `sudo -l` shows the current user can run `vim` as root with no password
(`(root) NOPASSWD: /usr/bin/vim`). The `vim` page's **Sudo** section gives the exact escape:

```bash
sudo vim -c ':!/bin/sh'
```

That single line is a root shell.

## Common use cases

- **`sudo -l` returns a binary you don't recognize as dangerous.** Never assume a binary is safe
  because it "isn't a shell" -- editors (`vim`, `nano`), pagers (`less`, `more`), interpreters
  (`python`, `perl`, `awk`), and even `find`/`nmap` (in interactive script mode) all have documented
  `sudo` escapes on GTFOBins. Always look up the exact binary before ruling it out.

```bash
sudo -l
# (ALL) NOPASSWD: /usr/bin/find
sudo find . -exec /bin/sh \; -quit
```

- **SUID sweep turns up an unfamiliar binary.** A `find / -perm -4000` sweep on CTF/misconfigured
  boxes regularly turns up a SUID-bit copy of something like `cp`, `python3`, or a vendor binary with
  no sudo entry at all -- the SUID bit alone is enough for the file-owner (often root) primitive
  listed on that binary's **SUID** tab, which is a different abuse than its **Sudo** tab.

```bash
find / -perm -4000 -type f 2>/dev/null
# turns up /usr/bin/python3.9 with SUID set
/usr/bin/python3.9 -c 'import os; os.setuid(0); os.system("/bin/sh")'
```

- **Escaping a restricted shell (rbash, a menu, a jump host).** GTFOBins' **Shell** tab lists which
  binaries, if reachable at all from inside a restricted environment, spawn a normal shell -- useful
  the moment a foothold lands you in a limited menu/rbash rather than a full TTY.

- **File read/write primitive instead of a shell.** Not every finding needs a shell: the **File
  read**/**File write** tabs (e.g. `sudo tar` to read `/etc/shadow` via an archive trick, or `sudo
  ln` to overwrite a root-owned file) matter when the goal is a specific file, not code execution.

## Tips and gotchas

- **Match the context exactly.** A binary's GTFOBins page lists different primitives depending on
  whether it's runnable via `sudo`, has the SUID bit, has a Linux capability set, or is only
  reachable inside a restricted shell -- the `sudo` primitive for a binary is often not the same
  command as its SUID primitive (SUID has no `sudo` in front and runs as the file owner, not
  necessarily root). Always cross-reference the exact form you found the binary in.

- **`sudo -l` may need a password you don't have.** If the current account requires a password for
  `sudo -l` and you don't have it, check `/etc/sudoers`/`/etc/sudoers.d/` directly if readable, or
  fall back to the SUID/capability sweep instead.

- **Not every listed binary is present or exploitable as documented.** GTFOBins entries assume a
  fairly standard binary build; a distro-patched or heavily cut-down version (Alpine's busybox `vi`,
  for instance) may not support the exact flag/escape sequence documented. Test it.

- **Capabilities are the sneaky one.** `getcap -r /` is easy to forget versus the more habitual
  `sudo -l` and SUID sweep, but a binary with `cap_setuid+ep` (e.g. `python3`) is just as much a
  root primitive as a SUID bit, and GTFOBins documents the **Capabilities** tab for it too.

- **Pairs with a full enumeration script, not instead of one.** [[linpeas]] and
  linux-exploit-suggester (see `[[linux-exploit-suggester]]`) already surface `sudo -l`/SUID/capability
  findings automatically; use GTFOBins as the reference for *what to do* with whatever they flag,
  not as your primary enumeration step.

## Related

- [[linux-privesc]]: full Linux privilege-escalation methodology GTFOBins slots into
- [[linpeas]]: automated enumeration that surfaces the sudo/SUID/capability findings to look up
- [[linux-exploit-suggester]]: the kernel-CVE complement when no misconfiguration primitive applies

## Sources

- GTFOBins: https://gtfobins.github.io/
