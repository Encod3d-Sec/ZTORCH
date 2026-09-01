---
name: hunt-core
description: Shared discipline for every hunt-* skill (fixture slice).
---

# hunt-core (fixture)

Minimal slice used by tests/test_index.py. Mirrors the real
skills/hunt/hunt-core/SKILL.md routing-table contract.

## Routing table (machine-readable)

The parse contract `offensive.py index` reads: fixed columns, one row per
fingerprint token.

| fingerprint | class | hunt-skill | primary wiki | arsenal slug |
|---|---|---|---|---|
| ssrf | ssrf | hunt-ssrf | ssrf | payloads/ssrf |
| idor | idor | hunt-idor | access-control | payloads/idor |
| sqli | sqli | hunt-sqli | sql-injection | payloads/sqli |
| login-form | sqli | hunt-sqli | sql-injection | payloads/sqli |

## Something after

Text past the table must not be slurped into the last row.
