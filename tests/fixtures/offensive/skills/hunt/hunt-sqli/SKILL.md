---
name: hunt-sqli
description: SQLi and NoSQLi hunting (fixture slice).
---

# hunt-sqli (fixture)

## Wiki

```
qmd_query "SQL injection error-based union boolean blind" via wiki-search MCP
```

Primary page: [[wiki/payloads/sqli]]. Automation: [[sqlmap]].

## Attack Surface Signals

DB error strings, login forms, numeric/string params reflected into a query.

**APPROACH:** Manually confirm the injection (error/boolean/time), then hand to sqlmap for extraction.

**AVOID:** A generic 500 with no DB error string is NOT proof of injection.
