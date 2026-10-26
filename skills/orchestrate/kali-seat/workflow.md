# kali-seat workflow

1. Transport: `bash scripts/vm-ssh.sh '<cmd>'` direct; base64 block for long
   or quote-heavy commands (pattern in SKILL.md).
2. Scope shim: target-facing HTTP tools run under `/opt/scope-shim/bin/` on
   the VM. After `lists/inscope-hosts.md` gains a host: `bash
   scripts/scope-sync.sh`.
3. Scanner discipline: one scanner at a time, `-t 5`; CPU-bound VM.
4. Failures climb the recovery ladder (retry once -> fix args -> fallback
   seat), never skip straight to a different tool.

## N/A escapes

- `N/A: pure-seat task (no VM tooling needed)`
