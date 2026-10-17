# CRX forcelist bring-up (dedicated automation Chrome)

Goal: a disposable Chrome instance (own --user-data-dir, launched --incognito)
that auto-installs the Interceptor CRX via policy on first run.

## 1. Derive the CRX's REAL ID from the packing key

The appid in the forcelist policy and in update.xml must equal the ID derived
from the CRX itself - NOT the upstream web-store ID. On mismatch Chrome
downloads the CRX and silently drops it; no error surfaces anywhere.

CRX3 recipe:

    import struct, hashlib
    data = open("<repo>/extension/dist.crx","rb").read()
    hl = struct.unpack("<I", data[8:12])[0]
    header = data[12:12+hl]
    i = header.find(bytes.fromhex("30820122300d06092a864886f70d0101010500"))
    spki = header[i:i+294]
    aid = "".join(chr(97+int(c,16)) for c in hashlib.sha256(spki).hexdigest()[:32])

For an unpacked dir, the same ID derives from the manifest "key" field
(base64 DER -> sha256 -> a-p map, first 32 hex chars).

## 2. Serve CRX + update.xml over localhost HTTP

    cd <repo>/extension && python -m http.server 8791 --bind 127.0.0.1   # background

update.xml appid = the derived ID; version = the extension manifest version.
The server must be up BEFORE Chrome starts or the install silently no-ops.

## 3. Native messaging host - registry form (data-dir independent)

A file-based NM manifest under the DEFAULT "User Data" dir does not cover
custom --user-data-dir instances. Register via HKCU instead:

    reg add "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.interceptor.host" /ve /t REG_SZ /d "<path>\com.interceptor.host.LIVE.json" /f

The LIVE manifest: path = dist/interceptor.exe; allowed_origins must include
chrome-extension://<derived-ID>/ (plus the unpacked key-derived ID if that
form is also used).

## 4. Forcelist policy (HKLM - one elevated reg add)

    reg add "HKLM\SOFTWARE\Policies\Google\Chrome\ExtensionInstallForcelist" /v 1 /t REG_SZ /d "<derived-ID>;http://127.0.0.1:8791/update.xml" /f

Elevate via a one-shot ps1 + Start-Process -Verb RunAs (operator approves the
UAC); poll `reg query` until the new value shows before relaunching Chrome.

## 5. Launch the automation instance

    Start-Process chrome.exe -ArgumentList '--user-data-dir=<tool-tree>/chrome-profile','--incognito','--no-first-run','--no-default-browser-check','https://<first-url>/'

Forcelist installs the CRX at startup (verify: grep the new profile's Secure
Preferences for the derived ID). Then the ONE manual step, in THIS instance:
chrome://extensions -> Interceptor -> Details -> "Allow in Incognito"
(persists in that data dir; without it, window_create --incognito returns
"no window").

## 6. Verify the chain

- standalone daemon held (SKILL.md WAKE LAW)
- netstat 19222 ESTABLISHED (worker connected)
- `interceptor window new <url> --incognito` returns a window

## Pitfalls

- NEVER publish dist.pem (the CRX private key) or push it to any remote.
- Never reuse a vendor/upstream store ID in the forcelist for a locally
  packed CRX - derive from the key every time the CRX is repacked.
- If the instance was killed uncleanly, clear the profile dir rather than
  debugging ghost state.
