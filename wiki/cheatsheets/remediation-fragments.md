---
title: "Remediation Fragments (Per Vuln Class Fix Text)"
type: cheatsheet
tags: [remediation, reporting, fix-text, findings]
phase: exploitation
date_created: 2026-11-20
---


# Remediation fragments (Fix text for FIND cards)

Distilled from the Remediation sections of the claude-red web-family skills. Each fragment is copy-paste-ready Fix prose for the corresponding FIND-card class. Operator promotes; never auto-promoted.

## XSS

Contextual output encoding plus a modern layered defense, not filtering alone:

- Render untrusted HTML only through the native Sanitizer API (`element.setHTML(userInput, { sanitizer })`, Chrome/Edge 105+, Firefox 117+ flag) with DOMPurify fallback for older browsers.
- Enable Trusted Types (`require-trusted-types-for 'script'`) so `innerHTML`/`eval` sinks require a registered policy; Angular 17+ and React DOM 19 can enforce at build time.
- Strict CSP: `default-src 'self'; script-src 'nonce-RANDOM' 'strict-dynamic'; object-src 'none'; base-uri 'none'` (nonce + strict-dynamic replaces host allowlists).
- Reject cross-site state-changing requests via `Sec-Fetch-Site` middleware; add CORP/COEP/COOP headers.
- Cookies: `HttpOnly; Secure; SameSite=Strict`; server-side sessions over tokens in localStorage.
- Framework gotchas to name in the card: React `dangerouslySetInnerHTML`, Vue `v-html` + dynamic components, Svelte `{@html}`, Angular `bypassSecurityTrust*`, Astro `set:html`, Remix loader-data XSS.

## XXE

- Disable DTD processing and external entity resolution entirely; keep XML parser patches current; prefer JSON where feasible.
- Parser snippets: Java `DocumentBuilderFactory` with `disallow-doctype-decl=true`, external-general/parameter-entities=false, XInclude off; Python `defusedxml`; .NET `DtdProcessing.Prohibit` + `XmlResolver = null`; PHP `libxml_disable_entity_loader(true)`.
- Modern defaults (2024-2025): libxml2 >= 2.13 (`XML_PARSE_NO_XXE`), Python >= 3.13 stdlib forbids external entities, .NET 8 templates prohibit DTD, Java 22 secure processing on.
- Gateway layer: reject bodies containing `<!DOCTYPE`/`<!ENTITY` (Lambda authorizer, Kong xml-threat-protection, Apigee XMLThreatProtection, ModSecurity rules); enforce size and structure limits.
- Egress allow-list XML-parsing hosts to kill blind-XXE callbacks.

## SSRF

- Two-stage validation with a trusted RFC-3986 parser: validate scheme/host, THEN resolve DNS and validate IP/CIDR; re-validate after every redirect hop; disallow redirects into private space.
- Fetch by resource ID instead of arbitrary URL; where a URL is unavoidable use signed (HMAC) callbacks and queue-based fetchers; pre-signed URLs for cloud resources.
- Egress: sandboxed proxy with allowlists and post-resolution IP checks; block IMDSv2 token acquisition (`PUT /latest/api/token`) for workloads that do not need metadata; verify SNI/Host match to mitigate HTTP/2 coalescing.
- Layered allowlists in order: scheme -> network range -> domain. Timeouts on all fetches.

## RCE / command injection

- Never place user input into evaluated code; remove `eval`, `exec`, `Function`, `subprocess shell=True`, `Runtime.exec()` where possible; parameterized process execution (`shell=False`, argument arrays, allowlists).
- Template engines: sandbox mode, dangerous tags disabled, no user-authored templates.
- Uploads feeding execution: magic-byte + extension + content-type checks, metadata stripped (`exiftool -all=`), stored outside web root, processing in seccomp/AppArmor sandboxed containers as non-root without network, publish delayed until validation completes.
- Safe deserialization: JSON with strict schemas, signed payloads, class allowlists, no pickle/marshal/native object graphs.
- Dependencies pinned and audited (`npm audit`, `pip-audit`, OWASP Dependency-Check); egress filtering against OAST callbacks; WAF/RASP with RCE signatures.
- Log4j-specific: 2.17.1+, `log4j2.formatMsgNoLookups=true`, remove JndiLookup from classpath.

## Race condition

- Pessimistic locking on the resource, or optimistic concurrency (version/timestamp); database-level unique constraints as the backstop.
- Idempotent, safely-retriable API design; distributed locks for cross-service flows; queue-based serialization for critical sections.
- Per-user rate limiting raises the bar; enforce transaction isolation levels appropriate to the operation.
- Name the classic exploitable shapes in the card if observed: single-use code redemption, balance check-then-deduct, permission check-then-write, connection-pool exhaustion during cleanup.

## IDOR / BOLA

- Deny-by-default authorization at the first layer, on object owner AND tenant; validate the requested object belongs to the current session server-side on every request.
- Indirect references (per-session tokens or numeric IDs mapped to pre-approved values) instead of raw object references.
- Dedicated authorization frameworks (RBAC/ABAC) over hand-rolled checks; context-aware controls beyond bare ownership.
- Rate limiting to slow brute-force object enumeration; log all access attempts on sensitive resources.
- Per-endpoint/per-field authorization unit tests plus CI BOLA scanners; partition CDN caches by auth headers, never cache private 200/304 responses.

## Open redirect

- Server-side allowlist of permitted redirect targets; full URL parsing, never substring checks; only http/https schemes.
- Indirect references: numeric IDs mapping to pre-approved URLs.
- Interstitial warning page for unavoidable external redirects; CSRF protection on redirect endpoints.
- Mobile deep links: validate package/bundle IDs, enforce App Links / Universal Links verification.

## HTTP parameter pollution

- Consistent parameter handling across every layer (edge, app, ORM); know your framework's duplicate-parameter semantics.
- Reject duplicate parameters at CDN/API gateway; canonicalize before processing; JSON Schema/OpenAPI validation rejecting unexpected fields.
- Express: custom query parser forbidding duplicates (except explicit `[]` arrays).
- GraphQL: query depth and alias-count limits. WebSocket frames validated consistently with HTTP parameters.

## Request smuggling

- Single RFC-compliant parser shared by front and back tiers; normalize `Host`/`:authority`; avoid HTTP/2-to-HTTP/1.1 translation where possible.
- Gateway: strip hop-by-hop and duplicate headers; allow only `chunked` TE; exactly one message-framing signal (reject multiple Content-Length or CL+TE).
- Reset connections after each request where feasible; validate Content-Length against actual body.
- Client-side desync: `Connection: close` on sensitive responses, prefer HTTP/2 end to end, strict cache controls.
- Monitor and alert on multiple Content-Length/Transfer-Encoding headers and anomalous connection-reuse patterns; validate WebSocket upgrade requests and `Sec-WebSocket-*` headers.

## File upload

- Content-based validation (magic bytes, content inspection), not extension alone; allowlists for both type AND extension; malware scanning.
- Random server-generated filenames; paths validated against traversal; size limits.
- Store outside web root; serve user content from a separate domain/CDN; no execution permissions on upload directories.
- Re-encode images and documents (CDR pipeline) before storage; strip metadata; sandbox converters (Ghostscript, ImageMagick, HEIC) under seccomp/Firejail/bubblewrap; SBOM + automated updates for the processing chain.
- Downloads: `Content-Disposition: attachment`, `X-Content-Type-Options: nosniff`.
- Object storage: presigned PUT with TTL <= 60s and single-use semantics; require server-side encryption headers; IAM limited to PutObject; validate keys post-upload (reject `../`, `%2f`, homoglyphs, hidden dot-segments); Object Lock against overwrites; scan-and-quarantine before publish from a separate read-only bucket.
- Pipelines: quarantine path until all validations complete (blocks multipart chunk races); treat `?url=` image sources as SSRF (private-IP block, metadata block, DNS-rebinding protection); backends validate the final object after full receive (blocks chunked smuggling into storage).

<!-- promoted-slug: remediation-fragments -->
