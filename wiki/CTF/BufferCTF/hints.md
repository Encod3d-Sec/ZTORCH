---
title: "BSides 2026 BOF CTF — Hints and Challenge Description"
status: active
type: technique
tags: [ctf, bof, ctfd, hints]
date_created: 2026-05-23
date_updated: 2026-05-23
sources: []
---

# BSides 2026 BOF CTF — Hints and Challenge Description

---

## CTFd Challenge Description

> **Auth Gateway**
>
> Our security team deployed an authentication gateway on port 8443. They say it's locked down tight — "even a portscan won't reach it."
>
> Prove them wrong. Four flags hidden inside. Start from the outside.
>
> **Target:** `<IP>:8443`
> **Binary:** attached (`adminpanel`)
> **Flag format:** `BSIDES{...}`

---

## Suggested Flag Point Values

| Flag | Location                               | Points |
| ---- | -------------------------------------- | ------ |
| 1    | `/home/ctf/bof.txt` (inside container) | 150    |
| 2    | `/root/docker.txt` (container root)    | 100    |
| 3    | `/home/ubuntu/user.txt` (host)         | 150    |
| 4    | `/root/root_flag` binary (host root)   | 100    |

---

## Hints

Hints are subtracted from the flag score when purchased. Each flag has two hints: a nudge (cheap) and a near-spoiler (expensive). Enter into CTFd under the corresponding challenge.

### Flag 1 — BOF (`bof.txt`)

| # | Cost | Text |
|---|---|---|
| 1 | 50 | Port scans show the port filtered — that is expected. Think about what source port DNS servers always use when making outbound queries. |
| 2 | 100 | The binary reads up to 256 bytes into a 64-byte buffer. Check protections with `checksec`. ASLR is on but PIE is off — look for a gadget at a fixed address that jumps somewhere you control. Not all bad characters are `\x00`. |

### Flag 2 — GDB Cap (`docker.txt`)

| # | Cost | Text |
|---|---|---|
| 1 | 75 | You have a shell inside the container as a low-privilege user. Some binaries have more than just SUID — enumerate what Linux capabilities are set on installed binaries. |
| 2 | 150 | `gdb` can run Python directly with `-ex 'python ...'`. Python's `os` module can change the process UID and GID before spawning a shell. |

### Flag 3 — Docker Escape (`user.txt`)

| # | Cost | Text |
|---|---|---|
| 1 | 75 | You are root inside the container. Look at what is mounted — specifically, what socket is available that is normally only accessible to the host. |
| 2 | 150 | The Docker socket lets you spawn a new container. Mount the host root filesystem into it as a volume. Then you can read anything on the host that the new container's root can access. |

### Flag 4 — Host Root (`root_flag`)

| # | Cost | Text |
|---|---|---|
| 1 | 100 | The flag is not in a file — it is inside a binary at `/root/root_flag` (mode 700, root only). You need an actual host root shell to run it. Reading the binary or running it inside a container will not work. |
| 2 | 200 | The host has `gcc` installed. Check the kernel version with `uname -r`. There is a public LPE exploit for this kernel from 2026. Once you have a root shell on the host, run `/root/root_flag`. |

---

## CTFd Setup Checklist

- [ ] Create challenge "Auth Gateway" — category: pwn (or binary exploitation)
- [ ] Set point values per table above (static or dynamic scoring)
- [ ] Upload `adminpanel` binary as file attachment
- [ ] Paste challenge description (update `<IP>` placeholder)
- [ ] Add hints above to each flag — set point costs as listed
- [ ] Set flag answers: `BSIDES{A1b2C3d4E5f6G7h8I9jK}` / `BSIDES{L9m8N7o6P5q4R3s2T1uV}` / `BSIDES{Q1w2E3r4T5y6U7i8O9pA}` / `BSIDES{Z9x8C7v6B5n4M3k2J1hG}`
- [ ] Test: submit each flag manually to confirm CTFd accepts them

---

## Notes

- Flag 1 and 2 are one challenge or two — organizer's choice. Splitting them keeps difficulty curve cleaner.
- Hint 2 for flag 4 intentionally omits the exploit name. Players must still identify CVE and find the repo.
- Point costs are calibrated so buying both hints for a flag costs 25–35% of the flag value — still worth solving.
