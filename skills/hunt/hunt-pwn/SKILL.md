---
name: hunt-pwn
description: Binary exploitation hunting - stack/heap memory corruption, format string read/write, ROP, one_gadget, seccomp/jail escapes on CTF pwn services. checksec-first, gdb-gef classification, wiki arsenal before hand-rolled exploits.
---

# Hunt: Binary Exploitation (pwn)

**Assumes `hunt-core`** for the scope gate, two-account rule, confirmation gate, enumeration limits, stop conditions, wiki protocol, FIND output, and Deadends. Do not re-derive any of that here.

This is the BINARY exploitation class (memory corruption in compiled targets reached over a socket or a handed-out binary). Web-shaped code execution (command injection, SSTI, deser) belongs to `hunt-rce`; if the row routed here but the target is a web app, say so in one line and re-route.

## Wiki

Hub: [[exploit-dev-moc]] · Primary page: [[binary-exploitation]] · Arsenal: [[binary-exploitation]] (cheatsheet)
Anchors: [[heap-exploitation]], [[format-string]], [[rop-techniques]], [[crash-analysis]], [[ctf-jail-escapes]], [[memory-safety-bugs]]
**REFS:** [[binary-exploitation]], [[heap-exploitation]], [[format-string]], [[rop-techniques]], [[crash-analysis]], [[ctf-jail-escapes]], [[memory-safety-bugs]]

qmd_query "binary exploitation heap format string ROP one_gadget seccomp glibc tcache" via wiki-search MCP — ONLY for a specific signal the map above doesn't cover (a glibc version's allocator behavior, an unusual mitigation combo, an architecture quirk); not a blanket first step.

## Tooling

checksec/file/ldd BEFORE anything else (mitigations choose the technique); pwntools as the harness ([[pwntools]]), gdb-gef to classify every crash ([[gdb-gef]]), ghidra when source is absent ([[ghidra]]). The cheatsheet carries the per-mitigation decision table: [[binary-exploitation]] (cheatsheet).

## Attack surface signals

**APPROACH:** checksec/file/ldd first and let the mitigations choose the technique; classify the crash in gdb-gef before writing exploit code; format string means leak first then `%hn/%hhn` writes; heap technique follows the glibc era (tcache/safe-linking/hook removal per [[heap-exploitation]]); verify one_gadget constraints at the real call site; seccomp present means ORW, not a shell.
**AVOID:** A segfault under a cyclic pattern is a crash, not a bug class; a one_gadget that ignores its constraints, and blind offsets fired without reading the binary's own mitigations, are not attempts.

Rank before exploiting:

- **Handed-out binary + Dockerfile/libc** - the intended path is usually in the provided libc version and mitigations; diff them against the service's live behavior first.
- **A service that echoes input then crashes** - format string / overflow in the echo path; test `%p` leaks and cyclic patterns before assuming heap.
- **Heap-shape menus (add/edit/delete/show)** - UAF/double-free/tcache poisoning per [[heap-exploitation]]; the delete path is usually the bug.
- **seccomp/landlock announced in the challenge text** - target ORW chains from the start ([[rop-techniques]]).
- **No mitigations at all (No PIE, No canary, NX off)** - simplest ret2win/ret2shellcode; do not over-engineer.

## Methodology

1. Recon the service: `nc` protocol map (prompts, sizes, menu options), file type, checksec, ldd, provided libc/ld versions. Record mitigations in state.md.
2. Reproduce and CLASSIFY the crash in gdb-gef (offset via cyclic, register control, heap chunk layout) per [[crash-analysis]] before writing any exploit.
3. Pick the technique from the classification + mitigations (leak-then-write for format strings; allocator-era technique for heap; ROP chain layout for stack). Pull payloads/arithmetic helpers from the cheatsheet, not memory.
4. Build with pwntools incrementally: leak primitive verified first, then the write, then control flow - each stage proven against the LOCAL binary before firing at the remote service.
5. Stabilize the result per ctf-box (the shell is non-tty; upgrade before enumerating).

## Confirmation gate

**NOT confirmation:** a segfault, a corrupted menu, a hang, or a leak that only prints on the local copy. **IS confirmation:** the staged primitive demonstrated against the REMOTE service (leak echoed back, controlled instruction pointer at a chosen address, or a shell/command output), reproduced in a clean connection. Capture the winning request/session per hunt-core evidence rules (`--kind cli`).

## Chaining

Foothold via pwn usually IS the flag path: loot creds from the shell per hunt-core reuse rules; container root still means checking `/home/*/flag*`, SUID, and mounted secrets before closing. seccomp-jailed shells chain to file-read primitives for the flag ([[ctf-jail-escapes]]).

## Severity

| Outcome | Severity |
|---|---|
| Remote code execution / flag read on the service | CRITICAL |
| Local-only crash or leak (no remote primitive) | MEDIUM |
| Crash without control over instruction pointer | LOW |

Rate on the demonstrated remote primitive, not the theoretical corruption.
