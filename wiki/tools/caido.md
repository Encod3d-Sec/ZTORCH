---
title: Caido
tags: [tool, proxy, web]
description: Rust web-audit proxy running headless on the Kali VM; GraphQL API + web GUI, HTTPQL filtering, Replay, Automate.
sources:
  - https://docs.caido.io/
---

# Caido

Rust web-security proxy (Burp-class alternative, MITM core). One `caido` binary
runs the instance headless: web GUI + GraphQL API on `:8082`, MITM proxy on
`:8080`. Desktop app exists but is not needed for the headless instance.
Companion skill: `caido` (skills/caido/SKILL.md: lifecycle, token refresh, agent surface).

## Core usage

```
bash /root/vm.sh '~/caido.sh status'      # process + ui + proxy + token-valid
bash /root/vm.sh '~/caido.sh history "req.host.eq:\"example.com\"" 20'
bash /root/vm.sh '~/caido.sh raw 15 resp'   # full raw response of captured req 15
bash /root/vm.sh '~/caido.sh send /tmp/req.txt example.com 80 0'   # Replay send
```

## Setup facts (Kali VM)

- Binary: `/usr/local/bin/caido` (v0.58.3, from `https://caido.download/releases/latest`,
  JSON `.links[]` -> curl -L -> tarball extracts `./caido-cli`).
- Instance: `caido --no-open --allow-guests --listen 0.0.0.0:8082 --proxy-listen 0.0.0.0:8080`,
  detached via setsid, log `/tmp/caido.log`, data `~/.local/share/caido/` (SQLite).
- A project MUST be created + selected before the proxy persists anything, else every
  proxied request 500s ("Could not acquire a connection to the database").
- Activation: one-time device-flow OAuth (UI Login -> dashboard.caido.io consent),
  instance named `kali-vm`, claimed under the operator account. Credentials never
  stored in the vault.
- API auth: Bearer token, extracted from GUI localStorage `CAIDO_AUTHINATION`
  -> `accessToken`, kept at `~/.caido-token` (600), 7-day expiry.

## Driving it

- Helper `~/caido.sh` (source of truth `scripts/caido.sh`): `start|stop|status|gql|
  history|raw|send`. All calls go over vm.sh as one command each.
- Ad hoc GraphQL: `~/caido.sh gql '<query>' '<vars-json>'` (POST
  `http://127.0.0.1:8082/graphql` with the Bearer token).
- MITM HTTPS through the proxy needs the client to trust Caido's CA (Settings ->
  Certificates) or `curl -k`.

## HTTPQL (filter language)

`<ns>.<field>.<op>:"<value>"`, ns = `req`/`resp`/`row`, ops = `eq ne cont ncont
like nlike regex nregex gt lt gte lte`, joined with `and`/`or`. Values MUST be
quoted; bare values are rejected.

```
req.host.cont:".example.com"
resp.code.gte:500 and req.method.eq:"POST"
```

## Schema drift gotchas (0.58.3)

- History filter arg is `filter: {code: $code}` (docs older: `search:`).
- `startReplayTask(sessionId)` takes ONLY sessionId; the raw request goes in via
  `createReplaySession` `requestSource.raw`.
- `replayEntry(id:, sessionKind: HTTP)` + `... on ReplayEntryHttp { request {
  response { ... } } }` fragment for request/response fields.
- `viewer { email }` invalid; token check = `currentProject { project { id } }`.
- On any field error, introspect (`__type(name:"...")`) before guessing; schema
  repo: github.com/caido/schemas.

## Concept map (Caido-native)

| Concept | What it is |
| --- | --- |
| Projects | isolated traffic stores; select one before proxying |
| HTTP History / Sitemap | captured requests; host tree derived |
| HTTPQL / Filter presets | query language backing history filters + Automate |
| Replay | manual resend/tweak of captured or crafted requests |
| Match & Replace | tamper rules (header/param rewrites on live traffic) |
| Automate | bulk runs: wordlist payloads, extractors, rate limits (Intruder-class) |
| Workflows | request/response pass pipelines, can emit Findings |
| Findings / Exports | in-project issue log; request export to files |
| Environment / Files | per-project variables + hosted wordlists, `{{env.VAR}}` |
| Scopes | target allowlists to cut noise |

Related: [[burp-mcp]] (primary proxy lane), [[burp-suite]].
