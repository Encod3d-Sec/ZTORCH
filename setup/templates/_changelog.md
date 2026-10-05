---
title: "Changelog - {{ENGAGEMENT}}"
type: engagement-changelog
tags: [engagement, changelog]
date_created: "{{DATE}}"
---

# Changelog - {{ENGAGEMENT}}

Every write-type change on a compromised host, logged live at the moment of the change.
Never auto-cleaned. Config edits back up `.bak` first and the backup path goes in the
rollback column. At close-out, `scripts/eng-close.py` emits a reverse-order rollback
script and flags rows whose `verified` column is still empty.

Distinct from `write-ledger.md` (the RoE write-verify-revert plan for LIVE target
records, logged before firing); both may exist on one engagement. `type` vocabulary:
webshell, account, config, persistence, privilege, cred-request, database, network, file.

| # | time | host | type | location | content | rollback | verified |
|---|------|------|------|----------|---------|----------|----------|
