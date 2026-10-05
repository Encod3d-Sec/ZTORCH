---
name: hunt-api
description: API attack hunting (REST / GraphQL / gRPC) - BOLA/IDOR, BFLA, mass assignment, excessive data exposure, auth/JWT, introspection + batching, rate-limit abuse. OWASP API Top 10. Wiki-first, FIND schema output. Use when the target is a REST/GraphQL/gRPC API or a swagger/openapi doc surfaces.
---

# Hunt: API Security

**Assumes `hunt-core`** for the scope gate, two-account rule, confirmation gate, enumeration limits, stop conditions, wiki protocol, FIND output, and Deadends. Do not re-derive any of that here.

## Wiki

Hub: [[web-moc]] · Primary page: [[api-security]] · Payload arsenal: `wiki/payloads/api.md`
Anchors: [[api-testing]], [[graphql-attacks]], [[grpc-web-attacks]], [[rsql-injection]], [[rsql]], [[rate-limit-bypass]], [[redos]], [[jwt-attacks]]
**REFS:** [[api-security]], wiki/payloads/api.md

qmd_query "API REST GraphQL gRPC BOLA BFLA mass assignment excessive data exposure OWASP API Top 10" via wiki-search MCP — ONLY when you have a concrete hint the map above
doesn't cover (a specific sink/version/CVE, an observed escape); not a blanket first step.

For object-level authorization (BOLA/IDOR) see `hunt-idor`.

## Attack surface signals

**APPROACH:** Get the spec (Swagger/introspection/.proto), then rank undocumented/undialed endpoints, batching/alias ops, bulk/export routes and non-GET verbs; run BOLA (cross-account ID swap), BFLA (privileged call as low-priv), and mass assignment (`role`/`isAdmin`), driving load-bearing requests through Burp.
**AVOID:** A 200 echoing your own request, an object that is shared/public/org-visible, a BFLA 200 without the action performed, or a mass-assign field merely accepted is NOT confirmation - verify B pulls A's data / the privileged action executes / the field takes effect on a fresh read.

`/api/`, `/v1/`, `/graphql`, `/rest/`, gRPC (`application/grpc`, HTTP/2), Swagger UI (`/swagger`, `/api-docs`, `/openapi.json`), mobile/SPA backends.

**Rank before testing.** Not all surface is equally likely to be broken:

- **Undocumented endpoints** present in the spec (Swagger/introspection) but never called by the UI - the classic BFLA surface; nobody tested the route the client does not exercise.
- **GraphQL introspection** and the mutations/fields it reveals that the client never invokes.
- **Batching and alias endpoints** - one request, many operations; per-item authorization and rate limiting are frequently applied to the request, not each operation.
- **Bulk and export endpoints** - one call, many objects; much higher severity per finding.
- **Non-GET verbs on read-looking routes** - `GET /orders/123` authorized, `PATCH`/`DELETE` not.
- **Newest features** - authorization middleware lags new code; a route written outside the conventions misses it.

## Methodology

**Setup:** two accounts per `hunt-core` (A owns, B attacks, separate profiles). Get the spec if any - Swagger/OpenAPI, GraphQL introspection, `.proto`.

**Drive it through Burp** for operator visibility. Push the load-bearing requests (the BOLA cross-account swap, the mass-assignment body, the BFLA verb/route call) into **Repeater** via `Skill(hunt-burp)` / the native Burp MCP (`mcp__burp__*`) so the operator can replay and inspect them; brute/fuzz belongs in **Intruder** (`send_to_intruder`), not a hand-rolled loop. A quick throwaway `curl` per account for the writeup PoC is fine.

1. **Enumerate.** Parse Swagger/OpenAPI for every endpoint + param; GraphQL introspection (`__schema`); gRPC server reflection (`grpcurl -plaintext <h> list`, then `list <svc>` / `describe`). **No spec?** Discover endpoints with `ffuf -w <api-wordlist> -u https://HOST/FUZZ` and fingerprint hosts with `httpx`, not a hand `curl` loop. This is service / endpoint DISCOVERY, not object enumeration - it is bounded by the engagement RoE (`no_dos`, scan-rate caps), NOT by the 5-to-20 object cap. Do not clamp the wordlist to 20. On an SPA host the bundle IS the spec: grep it for `API_URL`/route constants instead of fuzzing a uniform catch-all, and prove a disputed route absent with the catch-all oracle (unregistered paths 405 non-GET verbs and 404 GET, byte-identical to a nonsense-path probe), never via `OPTIONS` Allow headers (frequently a uniform lie on every path); dead client code can call endpoints the server never mounted ([[api-testing]]).
2. **BOLA / IDOR (API #1).** Swap object IDs across accounts (numeric, UUID, in body/path/header) - the dominant API bug. Swapping IDs to pull other accounts' records IS object enumeration: bounded to 5 identifiers by default, 20 ceiling with operator approval, 0 under `no_bruteforce`, per `hunt-core`. Two or three adjacent IDs prove the sequential pattern; cite a `total`/pagination count for scale, never a sweep. Full bounded-sample loop and the trusted-identifier test live in `hunt-idor`. -> overlaps `hunt-idor`.
3. **Broken function-level auth (BFLA).** Call admin/privileged methods as a low-priv user; swap the HTTP verb (GET -> PUT/DELETE); hit the undocumented endpoints from the spec.
4. **Mass assignment.** Add fields the client never sends (`role`, `isAdmin`, `verified`, `balance`) to JSON bodies; look for the privilege/state change to actually take effect (confirm from a fresh read, step below). Create filtering a privileged field says nothing about the UPDATE path (PUT/PATCH handlers are written separately): re-submit the same field there, with the object identifier in the BODY as well as the query (query-only is often rejected; try `id`/`<object>_id`/`<object>_number` aliases) ([[access-control]]).
5. **Excessive data exposure.** The API returns more than the UI shows (full objects, other users' fields, internal flags) - inspect the raw response, not the rendered page.
6. **Auth.** JWT flaws ([[jwt-attacks]]: `alg:none`, weak secret, `kid` injection), API-key reuse, missing auth on some routes, OAuth scope creep.
7. **GraphQL specifics.** Introspection, batching/aliases (rate-limit/brute bypass), nested-query DoS, field suggestion leaks. Payloads: [[graphql-attacks]].
8. **gRPC specifics.** Reflection to enumerate; `grpcurl` to call methods; tamper protobuf fields; run the same authz tests as REST.
9. **Rate limit / resource.** Unbounded pagination, no throttle on sensitive actions (OTP/login). Prove the throttle is absent with a bounded burst; honor `no_bruteforce`/`no_dos` - do not actually brute credentials or OTPs and never run this at volume against a live auth endpoint. See [[rate-limit-bypass]].

**When a direct call 403s or the extra field is stripped, it is not closed.** Parameter pollution (`?id=A&id=B` - check and fetch may read different occurrences), array/nested wrapping of the field (`{"user":{"role":"admin"}}`), casing and separator variants of a mass-assign key (`isAdmin`/`is_admin`/`admin`), alternate content-type (form vs JSON vs XML), verb-override headers (`X-HTTP-Method-Override`), **version downgrade** (`/v1/` predates the middleware `/v2/` has - the most reliable), and batching to skip per-item authorization.

**Chain: mass assignment -> privilege escalation.** A `role:admin`/`isAdmin:true` that actually takes effect turns the whole BFLA admin surface reachable - re-run step 3 as the escalated principal. For the broader workflow/state-tampering angle hand off to `hunt-bizlogic`.

**Distill** a confirmed, GENERIC pattern (product + endpoint + impact, no client host): `python3 scripts/wiki-stage.py --kind technique --slug <slug> --target-page techniques/web/api-security.md`

## Confirmation gate

**NOT confirmation:** a `200` echoing your own request back; an empty or shell response; B seeing an object that is shared, public, or org-visible; a body you have not compared against A's baseline; a BFLA endpoint returning `200` without the privileged action actually performed; a mass-assignment write returning `200` with the extra field accepted but the privileged field never verified in effect; any result not re-verified in a clean session.

**IS confirmation:**

- **BOLA** - B's low-priv session returns A's actual *data*, matching A's own baseline response, with A's legitimate/shared access ruled out, reproduced in a clean session.
- **BFLA** - a low-priv token reaching AND executing an admin/privileged function (perform the action, do not just get a `200`).
- **Mass assignment** - the privileged field (`role`/`isAdmin`/`balance`) verified in effect from a fresh authenticated read, not merely accepted in the request body.

## Validation

- Proof = content belonging to ANOTHER account/tenant in the response, with a unique
  canary written by account A and read via account B (two-account rule).
- Negative control: a randomized/nonexistent object id returns 404 or empty; that makes
  the 200-on-B a real object read, not a stub response.
- Counterevidence: 200 with redacted/null fields is server-side filtering WORKING.

## False Positives

- 200 with fields stripped = authorization working, not BOLA.
- Soft-deleted object shadowing (data you own, deleted, still readable once).
- Own-account data mistaken for another's: without a canary you cannot tell, so always
  plant the marker first.
- Public-by-design endpoints (docs, catalogs) read as broken authz.
- 429 read as authz failure; it is rate limiting, not access control.

## Cross-routing

- Load hunt-idor for the same object-level flaw outside a formal API (UI routes,
  direct object links).
- Load hunt-auth when the failure is token scope/audience rather than object id.
- Load hunt-bizlogic for quota/price/limit abuse on API endpoints.
- Not this skill: GraphQL-specific traversal/introspection (hunt-injection).

## Severity

- **CRITICAL** - unauthenticated admin action, or cross-tenant data access.
- **HIGH** - BOLA/BFLA reaching other users' data or functions; mass-assignment privilege escalation.
- **MEDIUM** - excessive data exposure; missing or weak rate limiting.

## Deadends

```
Append: - [ ] API on <host> <endpoint> -- BOLA/BFLA/mass-assign all enforced;
              extra fields ignored; JWT validated; introspection off
```

Record what you tried (pollution/array/verb/version-downgrade/batch), not just that it failed.
