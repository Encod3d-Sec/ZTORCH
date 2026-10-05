---
title: "<short title>"
type: finding
severity: MEDIUM
class: ""            # optional: canonical vuln class (ssrf/idor/rce/...) for chain triggers + coverage; fuzzy-inferred from title if blank
status: RESEARCH   # ladder: DETECTED (tool hit, unverified) -> CONFIRMED (PoC validated + poc/ capture) -> EXPLOITED (used in the chain); RESEARCH = alias of DETECTED; terminal-neutral: FALSE_POSITIVE / IGNORED (Description first sentence starts `FP:` / `IGNORED:`)
cvss: ""
affected: ""
counterevidence: ""      # required on CONFIRMED+: the strongest case AGAINST this finding (what you could not verify)
confidence: ""           # required on CONFIRMED+: high | medium | low + one-line basis
severity_change_conditions: ""   # required on CONFIRMED+: what discovered fact would raise/lower this rating
date_created: "{{DATE}}"
sources: []
---

# `<short title>`

## Description

`<What the vulnerability is, where it lives, and the root cause. One tight paragraph.>`

## Proof of Concept

`<Numbered, reproducible steps. Exact requests/commands in fenced code blocks. A reviewer must be able to replay this verbatim. Fence sizing: if the content contains a backtick run, open the fence one backtick longer than the longest run inside (a ``` inside a ``` fence breaks the card render).>`

```
<# step 1 ...>
```

## Impact

`<Concrete technical and business impact. What an attacker gains. Tie to data/access, not theory.>`

## Remediation

`<How to fix it. Specific, actionable.>`

## Recommended next

`<one line: next class/skill + the evidence input it needs>`

## References

`<CVE / advisory / docs links.>`

<!-- canonical-vocab (single source of truth; read by tests/test_find_lint_ladder.py, do not drift)
find_filename_placeholder: FIND-XXX-SEVERITY-short-slug.md
vuln_index_status: CONFIRMED | PARTIAL
find_status_ladder: RESEARCH -> DETECTED -> CONFIRMED -> EXPLOITED
find_status_neutral: FALSE_POSITIVE | IGNORED
find_confirmed_fields: counterevidence | confidence | severity_change_conditions
find_section: Recommended next
-->

