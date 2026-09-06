---
title: "Redline .mans SQLite Querying"
type: technique
tags: [forensics, dfir, redline, sqlite, windows, ransomware]
phase: post-exploitation
date_created: 2026-09-07
sources: []
---

## What it is

A Mandiant Redline collector session file (`.mans`) is a plain **SQLite 3 database**, not a proprietary container. Query it directly with `sqlite3` instead of driving the Redline GUI, which is slow and brittle over RDP.

## How it works

- `file AnalysisSession1.mans` reports `SQLite 3.x database`. Open read-only: `sqlite3 -readonly session.mans`.
- Table map (the ones that carry answers): `Files` (FullPath, FileName, Size, MD5, Created/Modified timestamps, FileAttributes, FileExt), `RegistryKeys` (KeyPath, ValueName, TextValue live here; the `RegistryKeyTextValues` table does NOT carry ValueName), `ProcessEvents`, `ServiceEvents`, `AgentEvents*` (usually empty), `URLHistory` / `CookieHistory` / `DownloadHistory` (IE history: full download URL + local destination path per row), `NetworkEvents`, `SystemInfo` (single row: OS, user, BIOS, NIC MAC, IP, timezone).
- `sqlite3 .recover` salvages b-tree-damaged copies into a new DB, but user-era rows often live in the damaged pages; a corrupted local copy is worthless, verify the hash against the remote original before trusting any "missing evidence" conclusion.

## Querying on the endpoint (no bulk transfer)

For a 1 GB session across a slow link, query on the box instead of pulling it:

1. Upload the sqlite-tools `sqlite3.exe` (~3.7 MB, hash-verified) to the endpoint.
2. Ship SQL as a script file, redirect output to a text file, pull only the KB-size results: `sqlite3.exe session.mans < run.sql > out.txt`.
3. Redline stores `FullPath` values **without a leading backslash** (`Users\John Smith\...`), so `LIKE '%\Users\%'` silently matches nothing; filter on `LIKE '%John Smith%'` or anchor on the profile name.

## Gotchas

- **Dot-evaded filenames**: malware named `d.e.c.r.yp.tor.exe` breaks every `LIKE '%decryptor%'` filter. Filter on stable fragments (`'%yp.tor%'`, `'%d.e.c.r%'`) or by path + size instead.
- **Timeline event counts vs file counts**: Redline's Timeline shows EVENTS, not files. With both the Modified and Changed boxes ticked, the match count is NOT the number of `Files` rows with that extension (observed: Timeline 48 vs SQL census 10). Count rows only as a floor; the room's expected number comes from the Timeline search bar.
- **Wallpaper artefacts**: ransomware sets wallpaper via `SystemParametersInfo`, no registry write; the evidence is a dropped image file (commonly `.bmp` under the user profile `AppData\Local\Temp`), not a `Control Panel\Desktop` registry value.
- **The GUI is still the source of truth for Timeline numbers** the room/report asks for; SQL enumerates the rows, the Timeline event semantics decide the count.

## Related

- [[digital-forensics]]
- [[windows-artefacts]]
