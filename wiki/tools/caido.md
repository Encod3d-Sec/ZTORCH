---
title: Caido
tags: [tool, proxy, web]
description: Rust web-audit proxy running headless on the Kali VM; GraphQL API + web GUI, HTTPQL filtering, Replay, Automate.
phase: exploit
sources:
  - https://docs.caido.io/
---

# Caido

Rust web-security proxy (Burp-class alternative, MITM core). One `caido` binary
runs the instance headless: web GUI + GraphQL API on `:8082`, MITM proxy on
`:8080`. Desktop app exists but is not needed for the headless instance.
Companion skill: `caido` (skills/surface/caido/SKILL.md: lifecycle, token refresh, agent surface, caido-mode CLI doctrine).

## Core usage

```
bash /root/vm.sh '~/caido.sh status'      # process + ui + proxy + token-valid
bash /root/vm.sh '~/caido.sh history "req.host.eq:\"example.com\"" 20'
bash /root/vm.sh '~/caido.sh raw 15 resp'   # full raw response of captured req 15
bash /root/vm.sh '~/caido.sh send /tmp/req.txt example.com 80 0'   # Replay send
bash /root/vm.sh '~/caido.sh fuzz /tmp/tpl.txt /tmp/pays.txt example.com 443 1'  # variant battery
bash scripts/caido-battery.sh example.com pays.txt   # one-command battery (ships template+payloads)
bash /root/vm.sh '~/caido.sh findings 20'             # in-project findings (Scanner passive etc.)
bash /root/vm.sh '~/caido.sh cookies example.com'      # Cookie hdr of latest captured req to host
cd skills/surface/caido/caido-mode && npx tsx caido-client.ts search 'req.host.cont:"example.com"' --compact   # SDK CLI, seat-side
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

- caido-mode CLI (seat-side, `npx tsx caido-client.ts` from `skills/surface/caido/caido-mode/`;
  vendored from github.com/caido/skills, built on `@caido/sdk-client`): HTTPQL
  `search`/`recent`, `export-curl <id> --config` auth snapshots for
  curl-through-proxy probing, named Replay sessions/collections handoff,
  Match & Replace rule CRUD, findings/scopes/filters/envs. Auth: PAT
  (`setup <pat> http://192.168.23.128:8082 --proxy http://192.168.23.128:8080`) or
  prime `~/.claude/config/secrets.json` `.caido.instances[<url>].cachedToken` from
  the VM's `~/.caido-token` (~7d). Full doctrine + commands: skills/surface/caido/SKILL.md.
- Helper `~/caido.sh` (source of truth `scripts/caido.sh`): `start|stop|status|gql|
  history|findings|cookies|project|raw|send|fuzz`. All calls go over vm.sh as one command each.
  `scripts/caido-battery.sh` (vault side) ships a whole battery in one vm.sh call.
  `project <name>` creates + selects an isolated per-engagement project (the skill's
  isolation step, now one command; `project` alone lists + marks the selected one).
- `fuzz <template> <payloads> <host> [port] [tls] [delay]`: template carries
  `{{PAYLOAD}}`; each variant = one Replay session; prints
  status/bytes/session/history-id per line. Cap 60 payloads (RoE); no URL-encoding
  done for you. `raw <history-id>` (the id after the slash in column 3) pulls the
  variant body from history. NEVER feed a replayEntry id to `raw`: `request(id:)`
  resolves the HISTORY table and both id spaces are dense numbers, so a replayEntry
  id silently returns a different capture (lane-regsurface5: entry 98 returned an
  example.com status-check row); when the history id is unavailable the column shows
  `?:<entry>` and the row must be located via `history "req.host.eq:..."` instead.
  Authenticated runs:
  template may carry `{{COOKIE}}` (refused unless `CAIDO_COOKIE` is set); the
  vault-side battery injects `Cookie:` from `CAIDO_COOKIE` into every variant.
- Ad hoc GraphQL: `~/caido.sh gql '<query>' '<vars-json>'` (POST
  `http://127.0.0.1:8082/graphql` with the Bearer token).
- MITM HTTPS through the proxy needs the client to trust Caido's CA (Settings ->
  Certificates) or `curl -k`.
- Cloudflare-fronted hosts: `send` replays can take an edge 403 while `fuzz`/battery
  variants pass in the same minute (seen on WP hosts, two independent lanes); prefer
  the battery for load-bearing sends, or pull the body from history `raw <id> resp` -
  the captured response is already on disk at zero extra target traffic. Same edge
  also fingerprints headless `--headless=new` chromium: all deep paths 403 while
  curl-shaped battery GETs pass the same proxy (lane-regsurface3). A HEADED browser
  (scripts/browser.sh + chrome-devtools MCP) is the browser fallback, not headless.

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
| Plugins | installable packages (Scanner/Autorize/Shift official); gql `installPluginPackage` with `{source:{url}}` works headless |
| Environment / Files | per-project variables + hosted wordlists, `{{env.VAR}}` |
| Scopes | target allowlists to cut noise |

Related: [[burp-mcp]] (primary proxy lane), [[burp-suite]].
