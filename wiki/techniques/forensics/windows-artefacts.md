---
title: "Windows Artefact Triage"
type: technique
tags: [forensics, windows, dfir, kape, prefetch, amcache, event-logs]
phase: post-exploitation
date_created: 2026-09-05
date_updated: 2026-09-05
sources: []
---

## Windows artefact triage (KAPE / triage collections)

Parse order that answers attacker-timeline questions fastest from a KAPE-style collection: prefetch names first (they outline the attack with zero parsing), then PSReadLine histories, Amcache, scheduled tasks, Security.evtx, and $MFT for corroboration.

## Prefetch run counts (Windows 10+)

Prefetch bodies are LZXPRESS-Huffman compressed after an 8-byte MAM header; reading the documented uncompressed offsets with raw struct unpack returns garbage. Decompress first:

```py
from dissect.util.compression import lzxpress_huffman   # pip install dissect.util
import struct, glob
for p in glob.glob("prefetch/*.pf"):
    d = open(p, "rb").read()
    body = lzxpress_huffman.decompress(d[8:])
    name = body[16:76].decode("utf-16-le", "ignore").split("\x00")[0]
    runcount = struct.unpack("<I", body[208:212])[0]
    print(f"{name:28s} runcount={runcount}")
```

Offsets are prefetch format v30+ (Win10/11). Run counts are THE fallback for "how many times was X executed" when process-creation auditing is off or was turned off by the attacker: a count of 1 marks single attacker executions, a count of N+1 splits N benign runs from 1 attacker run once the benign cadence is known.

## Amcache

`InventoryApplicationFile` keys carry `LowerCaseLongPath`, `Size`, and `FileId` = `0000` + SHA1 of the file. Byte-order gotcha: many forensic tools (EZTools suite) display the SHA1 with each 4-byte group reversed; the registry stores it raw. Both forms are 40-hex, so a validator accepts exactly one. If a hash is rejected, submit the other convention (reverse each 4-byte group of the stored value, or use it as stored).

## Event log IDs that carry an intrusion

- 1102 (Security) and 104 (System/operational logs): log clears, one per log. Enumerate ALL clears first; they bracket the incident and name the clearer.
- 4616 x many: system time was changed. A long run of them means the clock was manipulated, so the nominal "incident window" may be fabricated; correlate on an anchor artefact (prefetch, task XML author, RID order) instead of the shifted timestamps.
- 4719: audit-policy change. If it disables Process Creation auditing, 4688 is absent BY DESIGN; switch to prefetch run counts + PSReadLine for execution counts.
- 4720 -> 4722 -> 4724 -> 4732: local account created / enabled / password set / added to a group; the 4720 names the creating account. Rogue accounts ending in `$` mimic machine accounts in listings.
- Scheduled task creation: 4698 may be absent; TaskScheduler-Operational 106 plus the XML under `Windows\System32\Tasks` plus `SOFTWARE\...\Schedule\TaskCache` give name, author, trigger, and action. A fake updater task living OUTSIDE the real vendor's Tasks subfolder is the standard persistence tell.
- PowerShell/Operational 4104 (script-block logging) leaks FULL attacker/builder script bodies; classic-pipeline 800 carries the command line. Grep 4104 before reverse-engineering any dropped binary; the builder script usually explains every dropped artefact.

## Console history, timestomps, RIDs

- PSReadLine `ConsoleHost_history.txt` per user: the attacker's typed commands verbatim, including credentials used for lateral moves. Read every user's file in full, not grep.
- Timestomp tell: SI (modified) timestamps years old while SI/FN creation is recent, or SI and FN disagreeing wildly; an NTFS `$EA` named `$CI.CATALOGHINT` on a Temp-directory binary is a catalog-trust masquerade. Executables impersonating svchost with one extra letter are the usual lookalike pattern.
- SAM `Users` key RIDs: 1000+ in creation order; a rogue account takes the RID right after the last legitimate one, pinning creation order even with the logs cleared.

<!-- promoted-slug: windows-artefacts -->
