---
title: "accesschk"
type: tool
tags: [windows, privesc, services, postex]
date_created: 2026-09-10
date_updated: 2026-09-10
sources: []
phase: postex
---

## Purpose

**accesschk** (Sysinternals) is the Windows privilege-enumeration scalpel: which services, files, and registry keys a given principal can rewrite. The targeted follow-up once winpeas flags weak service or path permissions, and the proof that a service-hijack privesc is actually viable.

## Core usage

```bat
accesschk64.exe -uwcqv "Users" *                      
accesschk64.exe -uqv -w "C:\Program Files\Vendor" /accepteula
```

## Gotchas

- Always `/accepteula` (first run pops a GUI dialog that hangs a non-interactive shell) and use `accesschk64.exe` on x64 hosts.
- `-uwcqv Users *` is the writable-service sweep: writable (`-w`) services (`-c`) minus builtin principals (`-u`), verbose query (`-qv`). A hit plus a service restart right is a service-hijack privesc; verify the start type and binary path with `sc qc <name>` before writing anything.
- Binary path with spaces + unquoted = the classic unquoted-path hijack; accesschk confirms the writable directory, the path itself supplies the vector.
