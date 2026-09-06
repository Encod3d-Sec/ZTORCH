---
title: "Linux Disk Artefact Triage"
type: technique
tags: [forensics, linux, dfir, wtmp, auth-log, timestomp, usb-timeline]
phase: post-exploitation
date_created: 2026-09-06
date_updated: 2026-09-06
sources: []
---

## Linux disk artefact triage (mounted image)

Answering user-activity and intrusion-timeline questions from a mounted Linux disk (or image loop-mounted read-only). Linux counterpart to [[windows-artefacts]]; general carving/memory work stays on [[digital-forensics]].

Artefact map, highest yield first:

| question | artefact |
|---|---|
| what commands ran | `~/.bash_history` (read it in FULL, grep only to locate) |
| what did an alias/sudo-alias do | tail of `~/.bashrc` / `~/.zshrc`; a bare word like `transferfiles` is NOT in history |
| timezone of the device | `/etc/timezone` |
| domain-to-IP the box used | `/etc/hosts` (static map survives even when DNS would NXDOMAIN) |
| persistence | `/var/spool/cron/crontabs/<user>`, `/etc/cron.d/` |
| ransom/payment notes | root-owned odd files in `$HOME` (`mth`-style singletons) |
| logins | `var/log/auth.log` + `last -f var/log/wtmp -F` |
| USB insert/remove + serial | `var/log/syslog` + `var/log/kern.log` |
| file tampering | `stat` (mtime vs ctime vs Birth) |

Logs are often binary-contaminated; use `grep -a` or grep refuses with "binary file matches".

## Login event classes and timezone renders

Two records disagree by design, and graders want exactly one:

- `auth.log` lines carry the WRITING host's offset inline (`2025-02-28T14:06:13-05:00`).
- `wtmp` via `last` renders in the READING host's TZ (a UTC analysis box shows UTC, whatever the victim's `/etc/timezone` says).

So one login event yields three candidate strings (victim-local, UTC, reader-local). Before submitting any "when did the user last log in" question, enumerate the event CLASSES first: graphical login (`tty2`, `gone - no logout`), SSH (`pts/N`, paired `Accepted password` in auth.log), `su`/sudo. Question wording like "logged into the system" usually means the graphical login, not the newest SSH session; check for a `ttyN` line before assuming the pts line is the answer.

## Decoys and relative paths

History entries record relative paths (`sudo ls -ld .hidden/`) whose cwd you cannot recover reliably. Ground-truth with find and check EVERY hit's contents, not just the first:

```sh
find /mnt/disk -name ".hidden" -type d
ls -la --time-style=full-iso /mnt/disk/<each hit>
```

Planted decoys are typically empty twins sitting at the obvious path while the populated copy lives one level deeper (e.g. under `$HOME/Public/`). An empty first hit is a signal to keep walking hits, not a conclusion.

## Timestomp signature (ext4)

`touch -t` sets mtime only; ctime and Birth resist:

```sh
stat /mnt/disk/path/file.txt   # compare all three timestamps
```

Tells: mtime years before ctime/Birth, and mtime nanoseconds exactly `.000000000` (kernel-generated stamps carry real sub-second noise). In a directory of siblings sharing one true creation time, the one or two files with old flat mtimes are the tampered set.

## Imaging contamination window

Post-incident events land in the same logs: a much-later re-inserted USB with a different serial is the imaging/dd pass, and root-hub lines (`usb usb1`, `usb usb2`) carry PCI-path serials, not real devices. Anchor on the `usb X-Y: new high-speed USB device` + `SerialNumber:` pair whose timestamp sits inside the incident window, and the matching `USB disconnect, device number X` for removal time.

<!-- promoted-slug: linux-disk-artefacts -->

## Time-answer tie-breaker: submit the victim-local render

When a graded time question accepts only one of the candidate strings, the convention is the VICTIM-LOCAL render: take the event, convert it into the timezone recorded in the disk's `/etc/timezone`, and submit that. A reader-TZ (UTC) render of the same event is rejected even when the event class is right. Corroborate the chosen instant against adjacent incident events (a login 18s before a USB insert reads true; the same instant 5h off does not) before spending a submission.

<!-- promoted-slug: linux-disk-artefacts-login-tz -->
