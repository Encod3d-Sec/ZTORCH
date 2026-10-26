---
name: kali-seat
description: Canonical Kali VM seat. All target-facing commands run on the VM
  over SSH; the Windows/WSL seat only orchestrates.
metadata:
  ztorch:
    tags: [seat, kali, vm, transport]
    related_skills: [offensive, hunt-core]
---

# kali-seat

Canonical transport to the Kali VM. The vault seat orchestrates; tools touch
targets only from the VM.

## Transport (only path)

- Direct, key-based, fastest: `bash scripts/vm-ssh.sh '<command>'`
- WSL bridge fallback: `bash scripts/win-vm.sh '<command>'` (execs /root/vm.sh
  inside WSL kali, which reaches the VMware VM)
- Details: `docs/virtual-machine.md`

## Long or quote-heavy commands

Wrap the command in a base64 block so quoting survives two hops:

```bash
CMD='nmap -sV -p 80,443 sub.internet.com'
B64=$(printf '%s' "$CMD" | base64 -w0)
bash scripts/vm-ssh.sh "echo $B64 | base64 -d | bash"
```

## Scope shim

Target-facing HTTP tools (curl, ffuf, nuclei, httpx, feroxbuster, katana, gau)
run with the `/opt/scope-shim/bin/` PATH prefix on the VM so every request
passes the scope filter. Whenever `targets/<eng>/lists/inscope-hosts.md` gains
a verified in-scope host, re-run `bash scripts/scope-sync.sh` to push the list
to the VM shim.

## Rules

- One command per call, clean output, no marker strings (docs/shell-interaction.md).
- VM is CPU-bound: one scanner at a time, `-t 5` on ffuf/feroxbuster.
- Never kill standing tmux sessions; only the named engagement session.
