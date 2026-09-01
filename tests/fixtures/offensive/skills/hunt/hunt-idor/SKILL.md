---
name: hunt-idor
description: IDOR / BOLA hunting (fixture slice).
---

# hunt-idor (fixture)

## Wiki

```
qmd_query "IDOR BOLA broken object level authorization" via wiki-search MCP
```

Primary page: [[wiki/payloads/idor]]. See also [[access-control]].

## Attack surface

Any path/param carrying a numeric ID, UUID, or account identifier.

**APPROACH:** Two-account methodology - request account A's object as account B; a returned object you do not own is the finding.

**AVOID:** A 200 with an empty body, or the object echoed back from your own request, is NOT confirmation.
