---
title: "strace"
type: tool
tags: [binary, linux, forensics]
date_created: 2026-09-09
date_updated: 2026-09-09
sources: []
phase: exploit
---

## Fork-tree forensics: diagnosing "the exploit fired but no shell"

When a memory-corruption exploit fires (service crashes, or a child spawns and instantly dies) and the output channel is silent, strace the WHOLE service tree instead of guessing. Run the service under strace in front of its socket listener (a local socat mirror of the target works):

```sh
strace -f -e trace=execve,clone,clone3,fork,vfork -o /tmp/trace.txt \
  socat tcp-l:9004,reuseaddr,fork EXEC:./challenge
```

Then read `/tmp/trace.txt` after firing the exploit. What the trace answers in one read:

- `clone3(CLONE_VM|CLONE_VFORK)` followed by child `execve("/bin/sh", ...) = 0` = the gadget DID reach spawn; the problem is delivery, not the chain.
- `execve(...) = -1 EFAULT` = the spawned argv/envp tail is garbage pointers. A posix_spawn-shaped one_gadget builds argv from stack residue at the spawn moment, so argv[1..] is ENVIRONMENT-DEPENDENT: a fat local env (many vars via socat/ssh) leaves garbage where a lean container env leaves NULL. If the local mirror EFAULTs, fire remotely before re-engineering the chain; if a re-deploy stops working, suspect changed env/stack layout first.
- Parent SIGSEGV right after a successful child spawn, under a socket-wrapper service: the wrapper's waitpid only tracks its DIRECT child, so it tears the socket down within ms while the grandchild shell is still alive. Consequence: commands must be PRE-SENT (buffered in the socket before the corrupting write fires) and must call back out on their own channel (reverse shell), never rely on the dying socket for I/O.

Gotchas that make the trace itself lie:

- The syscall filter MUST include plain `clone`: glibc `fork()`/`posix_spawn` use `clone`/`clone3` on modern kernels, and a `clone3`-only filter attaches to none of the children (you see only the wrapper's own execve and conclude wrongly that nothing spawned).
- Never `rm` the `-o` trace file while strace runs: rm unlinks the inode and strace keeps writing to the deleted file (grep finds nothing, looks like "no syscalls captured"). Wait for exit, or truncate in place with `>file`.
- `-f` is load-bearing: without it, children are not traced at all even when the filter matches their syscalls.

<!-- promoted-slug: strace-fork-forensics -->
