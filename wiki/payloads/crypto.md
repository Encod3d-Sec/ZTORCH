---
title: "Payloads: Crypto Attacks (Quick Arsenal)"
type: payloads
tags: [payloads, crypto, padding-oracle, jwt, web]
sources: []
date_created: 2026-06-16
date_updated: 2026-11-11
---

# Payloads: Crypto Attacks

Fast checks for misused crypto in web tokens/data (OWASP A02). Full theory + tooling: [[cryptography-attacks]]; tokens [[jwt-attacks]].

## Identify the blob
```
rO0AB / AAEAAAD     -> Java/.NET serialized (see deserialization)
base64 of 16-byte multiple, changes wholesale per byte -> ECB ; same prefix blocks repeat -> ECB
"0e" + digits hash  -> PHP magic hash / type juggling (see type-juggling)
eyJ...               -> JWT (see jwt)
hex/IV.ct format     -> CBC -> padding oracle candidate
```

## ECB
```
identical plaintext blocks -> identical ciphertext: rearrange/cut-paste blocks
byte-at-a-time decryption against an encryption oracle (controlled prefix)
flip a role block: encrypt "userrole=adminXXX" -> move the admin block
```

## CBC
```
bit-flipping: XOR ciphertext block C[i-1] to flip chosen bytes of P[i]  (e.g. user=0 -> user=1)
padding oracle: distinct "padding error" vs other error -> padbuster URL ciphertext blocksize -> decrypt/forge
IV in token + IV controllable -> flip first block
```

## Stream / keystream reuse
```
same nonce/IV reused (CTR/OTP): C1 xor C2 = P1 xor P2 -> crib-drag
GCM nonce reuse -> recover auth key -> forge tags
```

## Hash / MAC
```
length extension (H(secret||msg)=sig): hashpump -s sig -d known -a append -k keylen  -> forge MAC
magic hash (== compare): provide "0e..." colliding string (type juggling)
weak/no signature on token: strip/forge
```

## JWT (see jwt for full set)
```
alg:none   weak HS256 secret (hashcat -m 16500)   RS256->HS256 confusion (sign with public key)   kid path/SQLi   jku/x5u SSRF
```

## Real-world
Padding-oracle on a "remember me"/state cookie -> decrypt+forge it; ECB cut-and-paste and CBC bit-flip on home-rolled token crypto; hash length extension on `H(secret||data)` MACs - all recurring real findings on custom auth.

## XOR encryption oracle (known-plaintext keystream recovery)

When you can feed chosen input to an "encryptor" that XORs with a fixed repeating keystream then encodes it (base64/hex) - a sudo/SUID tool, a web endpoint, a leaked script - recover the key with one known-plaintext call:

1. Submit a known plaintext at least as long as the target ciphertext (e.g. 16x `A` = `0x41`).
2. Decode the returned blob; `keystream[i] = out[i] XOR 0x41`.
3. Decode the target ciphertext and `plain[i] = target[i] XOR keystream[i]`.

```python
import base64
ks = bytes(b ^ 0x41 for b in base64.b64decode(oracle_out_for_16A))
secret = bytes(base64.b64decode(target_ct)[i] ^ ks[i] for i in range(len(target_ct)))
```

Distinct from keystream **reuse** (two ciphertexts under the same key, crib-drag): here one oracle call under your control yields the key directly.

<!-- promoted-slug: xor-encryption-oracle-known-plaintext -->

## NEW 2025-2026

1. **Authlib trio (CVE-2026-27962 / -28490 / -28498, fixed 1.6.9, affects <=1.6.8)**:
   - **27962 (CVSS 9.1)**: `key=None` in JWKS-lookup verification patterns -> the
     library trusts an attacker-embedded key in the token header; sign with your own
     key, embed the public half, server accepts. Test any OIDC/OAuth server on
     authlib: `{"alg":"RS256","jwk":{...attacker...}}`.
   - **28490 (8.3)**: RSA1_5 JWE key-management exception oracle - ValueError raised
     pre-validation creates a clean padding oracle; Flask/Django/FastAPI all render
     distinguishable HTTP errors for the two exception classes.
   - **28498 (8.2)**: OIDC ID-token validation FAILS OPEN on an unrecognized `alg`
     header (silently returns True) - forge a token with `alg:"x7z"` and it passes.
   https://securityonline.info/broken-keys-critical-authlib-flaws-jwt-forgery-padding-oracles/
2. **Exception-oracle pattern generalizes**: padding oracles live in distinguishable
   error responses across framework defaults - diff status/body/timing across
   modified ciphertext blocks before declaring an oracle absent.
3. **CVE-2026-16459 (Oberon PSA)**: padding oracle in embedded PSA crypto - the IoT/
   firmware variant of the same class; carries into [[privesc-exploit-arsenal]] paths.
4. **Header-embedded key confusion is now a CVE pattern, not just CTF**: `jwk`/`jku`/
   `x5u` in token headers reaching a verifier that fetches or trusts them - SSRF +
   forgery in one primitive (see [[jwt]] NEW section).
