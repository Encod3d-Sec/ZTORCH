---
title: "MicroBurst"
type: tool
tags: [cloud, azure, enumerate, powershell]
date_created: 2026-09-10
date_updated: 2026-09-10
sources: []
phase: enumerate
---

## Purpose

**MicroBurst** is the Azure/Office-365 enumeration PowerShell suite (NetSPI): subscription-level permission sweeps, blob/container discovery, Key Vault and automation-account reads, domain info gathering. Routed for Azure identity fingerprints where per-resource az calls are too slow.

## Core usage

```powershell
Import-Module .\MicroBurst.psm1
Get-AzDomainInfo -folder MicroBurst -Users
Invoke-EnumerateAzureBlobs -Base $base
```

## Gotchas

- Requires an authenticated Az context first (`Connect-AzAccount` with the recovered cred or token); MicroBurst enumerates, it does not authenticate.
- Blob enumeration (`Invoke-EnumerateAzureBlobs`) permutations can be noisy; on a rules-of-engagement-sensitive engagement prefer targeted `az storage container list` on known accounts.
- Run from a Windows tooling seat (PowerShell Az module); on the Kali VM use a pwsh container rather than mutating the host.
