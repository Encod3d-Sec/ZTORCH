---
title: "Next.js Middleware Authorization Bypass (CVE-2025-29927)"
type: technique
tags: [web, nextjs, authorization-bypass, cve, access-control]
phase: exploitation
date_created: 2026-06-17
date_updated: 2026-10-05
sources: [jfrog-cve-2025-29927, projectdiscovery-cve-2025-29927, zhero-nextjs-cache-chains, github-usestrix-strix]
---

# Next.js Middleware Authorization Bypass (CVE-2025-29927)

## What it is
CVE-2025-29927 (CVSS 9.1, March 2025) is an authorization bypass in Next.js. Middleware (commonly used for auth, redirects, and route protection) can be skipped entirely by sending a crafted `x-middleware-subrequest` request header, because Next.js blindly trusts that internal header to short-circuit middleware.

## How it works
Next.js uses the `x-middleware-subrequest` header internally to prevent infinite middleware recursion: when the framework makes an internal subrequest, it sets this header so middleware is not re-run. The flaw is that the value is trusted from the incoming request without verifying it originated internally. An attacker who sets the header to the expected value makes Next.js treat the request as an internal subrequest and skip middleware execution, so any access control, authentication redirect, or path protection implemented in middleware is bypassed. Any route protected only by middleware becomes directly reachable.

## Attack phases
Exploitation; authorization bypass and access control.

## Prerequisites
- Target runs a vulnerable Next.js version (before 12.3.5, 13.5.9, 14.2.25, or 15.2.3).
- Authorization is enforced in middleware (the common pattern).

## Methodology
1. Fingerprint Next.js (`x-powered-by: Next.js`, `/_next/` assets, build manifest version).
2. Identify a route protected by middleware (login redirect, admin area).
3. Resend the request with the `x-middleware-subrequest` header set to the expected sentinel; middleware is skipped and the protected route responds.
4. The exact value depends on version: it encodes the middleware module path (`middleware` or `src/middleware`), and newer branches expect a repeated chain of it.

## Key payloads / examples
Bypass header (value varies by version family):
```http
GET /admin HTTP/1.1
Host: target
x-middleware-subrequest: middleware
```
Newer branches expect a repeated/chained value matching the middleware module path:
```http
x-middleware-subrequest: src/middleware:src/middleware:src/middleware:src/middleware:src/middleware
```
A successful bypass returns the protected content that would otherwise redirect to login.

## Bypasses and variants
- Can also enable cache poisoning and DoS in some setups.
- The required value differs across the 12.x / 13.x / 14.x / 15.x branches; enumerate `middleware` vs `src/middleware` and the chain depth.

## Detection and defence
- Upgrade to Next.js 12.3.5 / 13.5.9 / 14.2.25 / 15.2.3 or later.
- Where patching is blocked: at the load balancer or reverse proxy, strip or block any external request carrying `x-middleware-subrequest`.
- Defence in depth: do not rely solely on middleware for authorization; enforce authz in the route handler and data layer.

## Detection symptom
When middleware rewrites/blocks everything, **every path returns the same page** (`/`, `/admin`,
even `/_next/static/*.js` and `_buildManifest.js` all serve the identical HTML). That uniformity is
the tell that a middleware is intercepting all requests - the routes behind it become reachable once
the header is set.

## Delivering the header through an SSRF (gopher)
If the Next.js app is internal-only and you reach it via an SSRF that only takes a URL
(`?url=` / preview / fetch), you **cannot set `x-middleware-subrequest` with a plain fetch** - a
`?url=` GET sends fixed headers. Tunnel a raw HTTP request carrying the header over **gopher**:
```python
# raw request with the bypass header, sent via gopher through the SSRF sink:
req=b'GET /customapi HTTP/1.1\r\nHost: 127.0.0.1:10000\r\nx-middleware-subrequest: middleware\r\nConnection: close\r\n\r\n'
# gopher://127.0.0.1:10000/_<percent-encoded req>  ->  ?url=<that, re-encoded>
```
Full `gopher()` + `send(method,path,headers,...)` builder in [[wiki/techniques/web/ssrf]] payloads. This was the exact
unlock on THM Extract (internal Next.js on :10000 behind an SSRF); run it via the hunt-ssrf skill.

## Internal cache poisoning chains (CVE-2024-46982)

A separate Next.js bug class from the middleware bypass above: internal cache poisoning by tricking the framework into caching a dynamic (SSR) response as if it were static (SSG). Basis: Rachid Allam (zhero), "Next.js, cache, and chains: the stale elixir" (2025 top-10 #7), CVE-2024-46982.

**Mechanism (source-level chain).** In `server/base-server.ts`, an `isSSG` check decides whether a response is cacheable, and it trusts the inbound `x-now-route-matches` header. An SSR route normally ships `Cache-Control: private, no-cache, no-store, max-age=0, must-revalidate`; misclassified as SSG it instead gets `s-maxage=1, stale-while-revalidate`, which a shared CDN/cache will store. The attacker chains three inputs against a non-dynamic SSR route:

- `?__nextDataReq=1` forces data-fetch (JSON) mode,
- `x-now-route-matches: 1` forces the SSG classification,
- a reflected value (`User-Agent`, cookie, CSRF token) becomes the cached payload.

```http
GET /dashboard?__nextDataReq=1 HTTP/1.1
Host: target
x-now-route-matches: 1
User-Agent: <img src=x onerror=alert(document.domain)>
```

The reflected `User-Agent` from `getServerSideProps` is cached as `text/html` and served to every subsequent visitor.

**Impact:** stored XSS (reflected payload cached for all users); DoS (poisoned JSON served where HTML is expected breaks the page globally); cache deception (another user's dynamic response cached against a shared key).

**Affected / scope:** Next.js 13.5.1 through 14.2.9, Pages router, non-dynamic SSR routes (`pages/dashboard.tsx`, not `pages/blog/[slug].tsx`), self-hosted only (Vercel unaffected). Fix: upgrade to 14.2.10 or later; strip `x-now-route-matches` from external requests at the proxy; never derive cacheability from a client-supplied header.

## Tools
curl or Burp to add the header on a directly-reachable target; gopher-over-SSRF (above) when the app
is only reachable internally. See [[access-control]] and [[authentication-attacks]].

## Proving the bypass end to end

Two independent facts must both hold, and each needs its own check:

1. The deployed build is vulnerable (version + build flags say so). A build artifact in the
   repo is NOT deployment proof: the running instance may be newer, older, or fronted by a
   proxy that strips the header. Verify the live 200/403 behavior.
2. The crafted header actually reaches the origin (no CDN/proxy stripping
   `x-middleware-subrequest` in front).

The real finding is always middleware-only authorization (the deployment pattern), never just
"header accepted". A redirect response is not a bypass: prove a status/content differential
against the same route without the header. An auth wall that 302s to login with the header
present but still serves protected content on 200 when the route handler re-checks is a
partial finding (defence in depth held); grade accordingly.

## Middleware-vs-handler normalization divergence

Middleware and the route handler can normalize the same path differently, so the middleware
auth check sees one route and the handler serves another: double slashes (`//admin`), trailing
slashes, dot segments (`/x/../admin`), and encoded forms. Additionally, when the SAME param
appears multiple times, one layer may take the first value and the other the last: test both
orders before concluding which layer reads which. The same differential applies to
`x-middleware-subrequest` chain-depth probing: enumerate, do not assume one value fits all
branches.

## Router, runtime, and cache skews

- **App Router vs Pages Router dual-router skew**: an app migrated halfway can enforce auth in
  one router's layout and nothing in the other's pages; check both trees.
- **Edge vs Node runtime divergence**: middleware and routes declare runtimes; Node-only
  defence code (DB session checks, allowlist modules) is silently skipped on Edge-rendered
  routes.
- **Cache identity**: with `use-cache`/ISR, audit the closure over cached functions: which
  user/tenant data does the cached value embed, and do `cacheTag`/`cacheLife`/revalidation
  calls separate tenants? A cached render keyed without user identity serves user A's data to
  user B.
- **Stale-while-revalidate plus `revalidatePath`/`revalidateTag`**: tokens leaked via Referer
  to a shared cache or CDN log can poison or read another session's revalidation.
- **`__NEXT_DATA__` over-fetch**: Pages Router serializes the full server props into the HTML;
  select-all ORM objects, internal ids, and full user records leak there even when the visible
  UI renders a subset. Read `__NEXT_DATA__` as a data-exposure surface in its own right.

## Browser-console recon one-liners

On any rendered Next.js page, open the console and enumerate before touching the network tab:

```js
__BUILD_MANIFEST.sortedPages                    // every route in the build, incl. unlinked ones
JSON.stringify(Object.keys(__NEXT_DATA__.props.pageProps))  // server props actually shipped
Object.keys(window).filter(k => k.startsWith("NEXT_PUBLIC_"))  // leaked env config keys, if app-exposed
```

`NEXT_PUBLIC_` values are inlined at build time, so the reliable sweep for them is a bundle
grep (`curl -s <chunk-url> | grep -o "NEXT_PUBLIC_[A-Z_]*" | sort -u`); the window check only
catches apps that explicitly assign them.

Chunk filenames map to routes: an `_next/static/chunks/pages/admin-<hash>.js` implies the
`/admin` route exists and shipped code for it even if nothing links to it.

## Sources
- JFrog, "CVE-2025-29927 - Authorization Bypass Vulnerability in Next.js" (slug: jfrog-cve-2025-29927).
- ProjectDiscovery, "CVE-2025-29927: Next.js Middleware Authorization Bypass - Technical Analysis" (slug: projectdiscovery-cve-2025-29927).
- Rachid Allam (zhero), "Next.js, cache, and chains: the stale elixir" (CVE-2024-46982, 2025 top-10 #7) (slug: zhero-nextjs-cache-chains) (`https://zhero-web-sec.github.io/research-and-things/nextjs-cache-and-chains-the-stale-elixir`).
