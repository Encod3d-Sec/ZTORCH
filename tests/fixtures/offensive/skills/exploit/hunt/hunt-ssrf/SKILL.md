---
name: hunt-ssrf
description: SSRF hunting (fixture slice).
---

# hunt-ssrf (fixture)

## Wiki

```
qmd_query "SSRF server-side request forgery cloud metadata" via wiki-search MCP
```

Hub: [[web-moc]]. Primary page: [[wiki/payloads/ssrf]]. Bypass variants:
[[dns-rebinding]] and [[open-redirect]].

## Attack surface signals

URL patterns: `?url=` `?uri=` `?src=` `/api/*/fetch` `/api/*/webhook`.

**APPROACH:** Confirm outbound via OOB, then enumerate 127.0.0.1 ports through the sink before grinding cloud metadata.

**AVOID:** A URL echo in an error message, a different status code, or a delayed response alone is NOT confirmation.

## Confirmation gate

Blind SSRF requires an OOB callback.
