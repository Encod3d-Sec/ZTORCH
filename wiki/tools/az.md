---
title: "az (Azure CLI)"
type: tool
tags: [cloud, azure, enumerate]
date_created: 2026-09-10
date_updated: 2026-09-10
sources: []
phase: enumerate
---

## Purpose

**az** is the Azure CLI: with a leaked cred, token, or managed-identity endpoint it enumerates subscriptions, role assignments, and Key Vault secrets directly. The playbook routes Azure metadata/identity fingerprints here.

## Core usage

```sh
az login -u user@tenant.onmicrosoft.com -p 'Password1'
az account list --output table                 # what the cred can actually reach
az keyvault secret list --vault-name VAULT     # then `keyvault secret show`
az role assignment list --all --output table   # privileged identities
```

## Gotchas

- A leaked client secret logs in non-interactively: `az login --service-principal -u <appId> -p <secret> --tenant <id>`.
- `az account show` failing does not mean the cred is dead; it may only reach a single tenant or resource graph. Try `az ad signed-in-user show` and `az rest` against the graph.
- Cloud class rows pair this with pacu where applicable; keep cred reuse first (loot matrix before new enumeration).
