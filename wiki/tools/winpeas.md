---
title: "winPEAS"
type: tool
tags: [windows, privesc, enumerate, postex]
date_created: 2026-09-10
date_updated: 2026-09-10
sources: []
phase: postex
---

## Purpose

**winPEAS** is the Windows privilege-escalation enumerator (PEASS suite sibling of linpeas): services, scheduled tasks, always-install-elevated, cred files, token privileges, hijackable DLLs. The auto 4b post-foothold row for Windows assets.

## Core usage

```bat
winPEASx64.exe
winPEASx64.exe -quiet                       
```

## Gotchas

- First fence is the Windows invocation (its sibling page keeps the Linux one): PEASS family overview and linpeas live on the peass page.
- Output is huge; run `-quiet`, save to a file, then triage the red/yellow sections rather than reading raw scrollback. Cross-check every hit mechanically (accesschk for services, `systeminfo` for patches) before claiming a privesc.
- AMSI/AV commonly flags the stock binary: the reflective/manual checklist (secpol, sc queries, unquoted paths) is the fallback when delivery dies; never disable AV on a client box to force it through.
