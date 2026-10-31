---
title: "Payloads: WebAuthn"
type: payloads
tags: [payloads, webauthn, auth]
sources: []
date_created: 2026-10-31
date_updated: 2026-10-31
---

# Payloads: WebAuthn

Server-side assertion-verification probes and downgrade ladders for passkey/WebAuthn logins.
The cryptography holds; the gates around it (user binding, challenge state, origin checks,
fallback methods, recovery) are what actually break.
Routed via the `hunt-auth` skill. Client-side ceremony-hijack payloads live in
[[webauthn-passkey]]; the technique page is [[passkey-webauthn-attacks]].

## Surface enumeration

Map the full ceremony surface before probing; every item below is a gate that can be missing.

```text
registration endpoint      # attestation policy, re-enroll without re-auth?
assertion/verify endpoint  # which fields are actually validated?
login options endpoint     # which credential ids are listed for a username?
fallback methods           # password, OTP, SMS, email link: the weakest sets the bar
step-up flows              # sensitive actions that demand a second ceremony
recovery flows             # lost-device: what enrolls a NEW passkey?
session binding            # does the assertion tie to THIS session cookie?
```

## Probe set

| probe | where | expected signal |
|---|---|---|
| cross-account assertion replay | verify endpoint, two-account rule | accepted = assertion not bound to the user |
| own old assertion replay | verify endpoint | accepted = challenge not single-use |
| expired challenge replay | verify after a delay | accepted = no challenge expiry |
| UV flag cleared | assertion `authenticatorData` with UV=0 | accepted where user verification is required |
| sign-count replay or zero | assertion counter field | counter unchecked = cloned credential invisible |
| cross-origin assertion | assertion minted on another origin | accepted = origin check missing |
| RP ID swap | assertion carrying a different RP ID hash | accepted = RP ID not validated |
| session not bound | verify, then hop session cookies | assertion valid on a different session |
| attestation unchecked | registration endpoint | any software authenticator enrolls |
| re-enroll without re-auth | settings/registration flow | new passkey added on a weak or stolen session |
| credential id enumeration | login options per username | arbitrary ids listed = account enumeration oracle |
| fallback after passkey failure | login flow, failed ceremony | password/OTP offered = downgrade surface |
| UA downgrade via proxy | login through an AitM proxy, old UA | passkeys disabled, weak method offered |
| recovery enrollment | lost-device flow | email/KBA/SMS enrolls a new passkey |

Raw assertion fields to tamper in the verify request (no re-signing needed when the server
skips the check; swap values between two accounts you control):

```text
id / rawId                   # swap to another account's credential id
response.authenticatorData   # UV byte cleared, sign count zeroed
response.clientDataJSON      # challenge, origin, type fields altered
```

## Bypass ladder

| rung | technique |
|---|---|
| 1 | force fallback by stubbing `navigator.credentials.get` (XSS on the RP origin) |
| 2 | UA downgrade through an AitM proxy so the RP disables passkeys |
| 3 | recovery flow: lost-device plus a weak channel enrolls an attacker key |
| 4 | hijack `navigator.credentials.create` to enroll an attacker authenticator |
| 5 | cross-account assertion replay (user binding missing) |
| 6 | UV=0 accepted where user verification is required |
| 7 | challenge reuse where single-use or expiry is not enforced |
| 8 | sign-count checks skipped: cloned credentials go undetected |
| 9 | synced-passkey cloud account takeover propagates the credential |

## Confirmation

Finding = one captured request pair in Burp Repeater: the verify-endpoint request carrying the
replayed or tampered assertion, plus the response showing an authenticated session was minted.
Negative control: the identical tampered assertion against a second, properly enforcing flow
(usually the same server's step-up endpoint) returns a verification error; and the legit
assertion on the wrong account must fail, proving the bind is the defect.
Severity ladder: assertion-to-user binding break or recovery enrollment = Critical (account
takeover); UV or counter acceptance = High; downgrade/fallback availability = Medium (design
weakness that gates the real attack).

## Chaining notes

Chain with XSS on the RP origin: any on-origin script can neuter or hijack the ceremony
(`webauthn-passkey` payloads).
Chain with an AitM phishing proxy: capture the fallback credentials the downgrade steers to.
Recovery weaknesses pair with password reset and SIM/email takeover for full account takeover;
see [[authentication-attacks]].
