---
title: "Payloads: MFA / 2FA Bypass"
type: payloads
tags: [payloads, mfa, 2fa, authentication, web]
sources: []
date_created: 2026-06-16
date_updated: 2026-10-31
---

# Payloads: MFA / 2FA Bypass

Defeat the second factor (OWASP A07). Routed via the `hunt-auth` skill. See [[authentication-attacks]] (MFA Bypass section); reset/login [[wiki/techniques/web/account-takeover]].

## Skip / state
```
complete step 1 (password) -> go DIRECTLY to the post-MFA endpoint (forced browsing)
the pre-MFA session cookie is already authenticated -> use it on protected pages
response manipulation: {"mfa_required":true} -> false ; {"verified":false} -> true ; 4xx -> 200
remove the otp/mfa param entirely; send empty otp=
toggle a 2fa-enabled flag in a profile/update request
```

## OTP brute / reuse
```
no rate limit: brute 000000-999999 (Turbo Intruder / ffuf)
weak code: 4-digit, sequential, predictable seed/time
reuse: one OTP works multiple times / does not expire
race the verify (parallel) to dodge lockout (see race-conditions)
OTP leaked in response JSON / sent to attacker-controlled email (param pollution)
```

## Backup / alternate factor
```
backup codes guessable / unlimited tries
"remember this device" cookie reusable / forgeable / no binding
downgrade: SMS/email fallback to a weaker or attacker-controlled channel
recovery flow bypasses MFA entirely (reset password -> logged in, no 2FA)
disable 2FA without re-auth (CSRF/IDOR on the disable endpoint)
```

## SSO / token
```
direct OAuth/JWT login path skips MFA (see oauth-saml, jwt)
"trusted" SAML assertion sets MFA-satisfied claim -> forge it
```

## Real-world
Forced-browse-past-MFA, OTP brute without lockout, and reset-password-skips-2FA are the recurring ATO bypasses; "remember device" cookies and response-flag tampering are close behind.

## Probe set

| probe | where | expected signal |
|---|---|---|
| forced browse to post-MFA URL | right after the password step | protected page loads = step not enforced server-side |
| pre-MFA session on app APIs | authenticated-but-unverified session | API honors the half-authed cookie as full auth |
| remove the otp param | verify endpoint | no error = param optional |
| empty otp value | verify endpoint | accepted = presence-only validation |
| response-flag tamper | verify response in the proxy | `"mfa_required": true` flipped client-side only |
| OTP reuse | verify the same code twice | second accept = not single-use |
| OTP expiry | replay an old code after delay | still accepted = no expiry |
| OTP echoed in response | verify/login JSON body | the code comes back in the response |
| rate limit | verify endpoint | 100+ attempts, no lockout or throttle |
| null / `0` OTP value | verify endpoint | type juggling accepts the empty branch |
| verify flag flip | state-changing endpoints | a `false` to `true` client flag unlocks the session |
| backup code brute | backup-code verify | unlimited tries on a small keyspace |
| remember-device cookie | trust flow | the cookie alone skips MFA on the next login |
| recovery flow | lost-device / password reset | post-reset session never sees the MFA step |

## Bypass ladder

| rung | technique |
|---|---|
| 1 | forced browsing straight to the post-MFA endpoint |
| 2 | drop the otp param or send it empty |
| 3 | tamper the response flag in the proxy |
| 4 | reuse or brute the OTP where there is no lockout |
| 5 | race parallel verifies to slip past the counter |
| 6 | fallback to backup codes or a weaker channel |
| 7 | forge or replay the remember-device cookie |
| 8 | password reset / recovery flow that skips MFA |
| 9 | SSO, OAuth, or direct API path with no MFA step |

## Confirmation

Finding = one captured request pair: the password-step request establishing the half-authed session, then the post-MFA or tampered-verify request landing fully authenticated.
Negative control: the same protected URL from a fully unauthenticated session must redirect to login; that proves the flaw is the MFA gate, not an open endpoint.
Severity ladder: any bypass reaching a full session = Critical (account takeover); OTP rate-limit weakness alone = Medium; remember-device weakness = Medium/High by what the cookie unlocks.

## Chaining notes

Chain with the login flow plus trust-device persistence: one bypassed login that mints a remembered device is durable access.
Pair with password reset for a full ATO chain when reset skips MFA.
CSRF or IDOR on the 2FA-disable endpoint turns a low-impact foothold into MFA removal; see [[authentication-attacks]].
