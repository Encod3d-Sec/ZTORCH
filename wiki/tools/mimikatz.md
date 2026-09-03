---
title: "Mimikatz"
type: tool
tags: [windows, credentials, lsass, post-exploit, ad]
date_created: 2026-09-03
date_updated: 2026-09-03
sources: []
phase: postex
---

# Mimikatz

## Purpose

Mimikatz is a Windows post-exploitation tool that reads plaintext passwords, NTLM/LM hashes, and
Kerberos tickets directly out of LSASS (Local Security Authority Subsystem Service) process memory,
where Windows caches credentials for SSO. Once you have local admin on a box, Mimikatz turns that
access into reusable credential material: logon passwords for pivoting, SAM hashes for local
pass-the-hash, and Kerberos tickets for pass-the-ticket/golden-ticket attacks against the domain.

## Installation

Precompiled binaries are on the releases page: `https://github.com/gentilkiwi/mimikatz/releases`

```bash
# Download the release zip on the attacker box, then transfer to the target
# (Windows Defender flags mimikatz.exe on sight -- see Tips for offline alternatives)
wget https://github.com/gentilkiwi/mimikatz/releases/latest/download/mimikatz_trunk.zip
unzip mimikatz_trunk.zip
```

Build from source (Visual Studio required) if you need a custom/obfuscated build to dodge
signature-based AV:

```bash
git clone https://github.com/gentilkiwi/mimikatz
# open mimikatz.sln in Visual Studio, build Release x64
```

Also ships bundled inside Impacket-adjacent toolkits, Cobalt Strike (as a BOF/aggressor script), and
Meterpreter (`load kiwi`), which wrap the same primitives without dropping the raw `mimikatz.exe`
binary to disk.

## Core usage

```powershell
mimikatz.exe
```

Mimikatz is interactive; every real command needs `privilege::debug` first to acquire
`SeDebugPrivilege` (required to read another process's memory, i.e. LSASS) then chains into a
module.

### privilege::debug -- required first step

```
privilege::debug
```

Fails silently to `ERROR kuhl_m_privilege_simple ; RtlAdjustPrivilege (1300)` if you are not local
admin, or if the process was not launched elevated. Every dump command below needs this to have
succeeded.

### sekurlsa::logonpasswords -- dump logon credentials

```
sekurlsa::logonpasswords
```

Walks every logon session cached in LSASS and prints plaintext passwords (if WDigest/credential
guard is not blocking it), NTLM hashes, and SHA1 hashes per user. This is the highest-value single
command: a domain admin's interactive/RDP session on the box hands you their NTLM hash (or
plaintext) directly.

### lsadump::sam -- local SAM hashes

```
lsadump::sam
```

Dumps local account NTLM hashes from the SAM hive (requires `privilege::debug` and, for a remote
target, `token::elevate` first if not already SYSTEM). Useful when local accounts are reused across
the estate (a shared local admin password is a common lateral-movement pivot).

### sekurlsa::tickets /export -- Kerberos tickets for pass-the-ticket

```
sekurlsa::tickets /export
```

Exports every Kerberos ticket (TGT and service tickets) currently cached in memory as `.kirbi`
files in the current directory. Inject one into a new logon session with `kerberos::ptt
<ticket>.kirbi` to impersonate that user/machine without ever touching their password.

## Common use cases

- **Foothold-to-lateral-movement pivot.** Land local admin on one box, run
  `privilege::debug` then `sekurlsa::logonpasswords`, and harvest whatever admin/service account
  last logged on interactively -- often enough for immediate pass-the-hash into the next host. See
  [[pass-the-hash]].

```
privilege::debug
sekurlsa::logonpasswords
# NTLM hash for DOMAIN\svc_backup falls out -- reuse with psexec.py / netexec / evil-winrm
```

- **Domain takeover via a DC-cached ticket or krbtgt hash.** On a Domain Controller,
  `lsadump::lsa /patch` or `lsadump::dcsync /user:krbtgt` pulls the krbtgt hash needed to forge
  golden tickets. Full chain in [[kerberos-attacks]].

- **Offline hash extraction to avoid live LSASS-read detection.** Dump the LSASS process memory
  with `procdump -ma lsass.exe lsass.dmp` (or `rundll32.exe comsvcs.dll, MiniDump <lsass_pid>
  lsass.dmp full`) then run Mimikatz **locally on your own box** against the dump file:

```
sekurlsa::minidump lsass.dmp
sekurlsa::logonpasswords
```

  This never puts `mimikatz.exe` on the target and never touches LSASS live from a flagged binary,
  so EDR that hooks `mimikatz.exe`'s process behavior sees nothing; only the memory-dump step
  touches the target, and legitimate sysadmin tools (`procdump`, signed by Microsoft) are far less
  likely to trip on-write AV than an unsigned `mimikatz.exe`.

- **Pass-the-ticket lateral movement.** Export tickets with `sekurlsa::tickets /export`, then
  `kerberos::ptt <file>.kirbi` on a second host (or the same host in a fresh logon) to act as that
  principal against Kerberos-authenticated services (SMB, LDAP, MSSQL) with no password ever
  touched. See [[kerberos-attacks]].

## Tips and gotchas

- **Requires local admin.** Every dump module needs `privilege::debug` to succeed first, which
  needs an elevated process. No admin, no LSASS read -- full stop.

- **AV/EDR flags it hard.** `mimikatz.exe` is one of the most heavily signatured tools in existence.
  Expect Defender/EDR to quarantine it on write or kill it on execution unless it is
  obfuscated/repacked or run entirely in memory (reflective load via a C2's built-in module, e.g.
  Cobalt Strike's `execute-assembly`/`mimikatz` command, or Meterpreter's `load kiwi`).

- **The offline-dump technique is the reliable bypass.** `procdump`/`rundll32` MiniDump + local
  Mimikatz analysis (see Common use cases above) is the standard way around live-process AV/EDR
  hooks, since the flagged binary never runs on the monitored host.

- **WDigest and Credential Guard affect what you get.** Plaintext passwords in
  `sekurlsa::logonpasswords` output require WDigest caching enabled (`UseLogonCredential=1` in the
  registry, default on older Windows, off by default on modern builds) -- absent that, you still get
  NTLM/SHA1 hashes, just no plaintext. Credential Guard (VBS-backed LSA isolation) blocks LSASS
  credential reads entirely regardless of privilege; check for it before spending time on a dump
  attempt.

- **Run as the right architecture.** A 32-bit `mimikatz.exe` cannot read a 64-bit LSASS process's
  memory; always match the target OS architecture (x64 for essentially every modern Windows box).

- **Clear the tickets you export.** `.kirbi` files are sensitive credential material; treat them
  like plaintext passwords in engagement evidence handling and clean them up off the target.

## Related

- [[pass-the-hash]]: reusing the NTLM hashes Mimikatz dumps
- [[kerberos-attacks]]: pass-the-ticket, golden/silver tickets, DCSync using Mimikatz-exported material
- [[windows-privesc]]: where LSASS credential dumping fits in a Windows privesc/lateral-movement chain

## Sources

- Mimikatz GitHub: https://github.com/gentilkiwi/mimikatz
