---
name: caido
description: Headless Caido proxy on the Kali VM: HTTPQL history triage, proxied curl probes, Replay handoff, Match & Replace, Automate, fuzz (caido-mode CLI + ~/caido.sh). Use when Burp/MCP is down or for isolated per-engagement projects.
---

# Caido (headless instance on Kali, driven seat-side)

Caido is a Rust web-security proxy: one `caido` binary on the VM runs the instance
(server), serves the web GUI, and exposes the GraphQL API the GUI itself uses.
The agent drives it through two surfaces; the operator watches the same data in
the GUI at http://192.168.23.128:8082. Wiki: [[caido]].

1. **caido-mode CLI** (primary API surface): vendored at `skills/caido/caido-mode/`
   (upstream github.com/caido/skills, MIT; reference clone `raw/git/caido-skills`).
   SDK-based (`@caido/sdk-client`), run seat-side against the VM instance. Output is
   JSON unless noted.
2. **`~/caido.sh`** on the VM (helper for lifecycle, fuzz batteries, ad hoc gql),
   source of truth `scripts/caido.sh`.

## The box (already set up)

- Kali VM: `caido` 0.58.3 at `/usr/local/bin/caido`, instance runs headless
  (`--no-open --allow-guests --listen 0.0.0.0:8082 --proxy-listen 0.0.0.0:8080`),
  log `/tmp/caido.log`, data `~/.local/share/caido/` (SQLite, projects live here).
- Claimed by the account (instance name `kali-vm`); Pro features active.
- **Project `default` selected. A project MUST be selected or the proxy 500s every
  request ("Could not acquire a connection to the database").** Per engagement create
  + select a fresh project (`~/caido.sh project <name>` or CLI `projects` /
  `select-project`) to isolate traffic.
- Ports: GUI/GraphQL `8082`, proxy `8080`, both reachable from the host. Note the
  proxy address DIFFERS from the API URL here (upstream defaults proxy = API URL),
  so the stored instance `proxy` entry or `--proxy` is load-bearing.
- MITM HTTPS: `curl -k` through the proxy, or import Caido's CA
  (Settings -> Certificates) into the client.

## caido-mode CLI: install + auth (one-time per seat)

```
cd skills/caido/caido-mode && npm install     # node_modules is gitignored; node 22 works
```

Full command reference lives in the CLI itself: `npx tsx caido-client.ts --help`
(and `<cmd> --help` per command); the upstream SKILL.md/README were deliberately
not vendored. Seat note: the caido-mode non-.md files arrive via git clone only
(Obsidian sync carries `.md` alone), so a synced seat needs a `git pull` of the
vault repo before `npm install` works.

Auth lives in `~/.claude/config/secrets.json` under `.caido`, keyed by instance URL
(`.caido.default`, `.caido.instances[<url>] = {pat, proxy, cachedToken}`).

- **Durable (preferred): PAT.** Operator creates one in the GUI
  (Dashboard -> Developer -> Personal Access Tokens), then:
  `npx tsx caido-client.ts setup <pat> http://192.168.23.128:8082 --proxy http://192.168.23.128:8080`
  (validates via device-code flow, caches token + proxy).
- **Quick prime (no PAT):** reuse the VM's GUI bearer token, valid ~7 days:

```
TOK=$(bash /root/vm.sh 'cat ~/.caido-token' | tr -d "[:space:]")
F="$HOME/.claude/config/secrets.json"; mkdir -p "$HOME/.claude/config"; [ -f "$F" ] || echo '{}' > "$F"
jq --arg tok "$TOK" '.caido = {default: "http://192.168.23.128:8082", instances: {"http://192.168.23.128:8082": {proxy: "http://192.168.23.128:8080", cachedToken: {accessToken: $tok, expiresAt: ((now + 518400) | todateiso8601)}}}}' "$F" > "$F.tmp" && mv "$F.tmp" "$F"
```

- Verify with `npx tsx caido-client.ts auth-status` (prints activeUrl, proxy,
  authMode, token expiry). `health` checks the instance without auth.
- Env overrides: `CAIDO_URL`, `CAIDO_PAT`, `CAIDO_PROXY`.
- VM-side `~/caido.sh` token refresh (localStorage re-extract via
  `scripts/browser.sh` + chrome-devtools) is unchanged and fixes both surfaces.

## Operating doctrine (two modes, kept strictly separate)

1. **Testing -> curl, proxied through Caido.** Find a real authenticated request in
   History, cache its auth ONCE into a reusable curl config
   (`export-curl <id> --config`), then probe with
   `curl -K /tmp/caido/<host>/auth.cfg "$BASE/path"`. The config carries the proxy,
   so every probe lands in History.
2. **Handoff -> named Replay sessions in named collections.** When the operator
   needs to SEE a request (a PoC, a chain step), materialize it as a named session.
   This is the Caido equivalent of a Burp Repeater tab: probing stays in
   History, load-bearing requests get promoted to Replay.

Hard rules:

- **All target traffic goes through the Caido proxy.** Never curl a target directly
  off-proxy; the operator must be able to see every request. Exception: high-volume
  brute/fuzz traffic (100+ requests) stays OFF the proxy (history bloat + VM CPU):
  use the `~/caido.sh fuzz` battery lane or `Skill(fuzz)`, then bring interesting
  hits back through the proxy / promote to Replay.
- **Cache auth in files, don't re-paste it.** One `export-curl --config` per target;
  the big cookie/token blob never enters the transcript.
- **Operator PoCs are FULL self-contained curls** (all headers inline, via
  `export-curl <id>`), never a `curl -K /tmp/...` line; the config is internal.
- **Replay session names are mandatory**; collections for multi-request handoffs;
  refer to sessions/collections by NAME, not id.
- Credential values stay in the proxy capture / config file, never in a vault file.

## Primary workflow (do this by default)

Run from `skills/caido/caido-mode/`; `npx tsx caido-client.ts <cmd>` below.

```
# 1. Find a base request that already has the auth/cookies you need.
npx tsx caido-client.ts search 'req.host.cont:"target.com" AND req.path.cont:"/api/user"' --compact
#    -> 8431  200  GET target.com/api/user/me

# 2. ONCE per target: cache its auth into a reusable curl config.
npx tsx caido-client.ts export-curl 8431 --config
#    -> /tmp/caido/target.com/auth.cfg  (proxy + insecure + compressed + ALL auth
#       headers + inline static cookies) and prints BASE + captured header list

# 3. Probe. -K carries proxy + auth, so it goes through Caido into History.
BASE=https://target.com
curl -K /tmp/caido/target.com/auth.cfg "$BASE/api/user/999"
curl -K /tmp/caido/target.com/auth.cfg -X POST "$BASE/api/profile" \
     -H 'Content-Type: application/json' --data-binary @/tmp/caido/target.com/body.json
```

Confirm a probe landed: `search 'req.host.cont:"target.com"' --limit 5 --compact`.

### The config is a faithful STATIC snapshot

- **All auth/identity headers, not an allowlist.** Modern apps gate on
  app-specific headers (`X-*-Validation`, `Origin`, `Referer`, `Sec-*`); a curated
  subset silently 403s. Only per-request/volatile headers are dropped: `Host`,
  `Content-Length`, `Content-Type`, `Connection`, `Accept-Encoding`.
- **Content-Type is dropped, so pass it yourself on every POST/PUT/PATCH**
  (`-H 'Content-Type: application/json'` or whatever the endpoint expects; a wrong
  one is the classic cause of opaque 400/403). Never add Content-Length; curl does it.
- **Static cookies, no jar.** Response `Set-Cookie` rotation never overwrites the
  captured-good cookies. Opt in to rotation with `--config --cookie-jar`.
- **Lazy refresh:** on 401/403/login-redirect, re-run `export-curl <fresh-id> --config`.
- Drop one header: `--exclude <name>` (repeatable); `--exclude cookie` when an M&R
  rule injects auth instead.
- **Path traversal tests need `curl --path-as-is`** or curl collapses `../` and
  `/./` client-side and the payload never reaches the server. Add `-g` if the URL
  contains `[ ] { }` curl would interpret.
- Per-target scratch dir `/tmp/caido/<host>/` holds `auth.cfg`, bodies, notes.
- Alternative: a Match & Replace rule can inject auth on all proxied traffic, then
  `curl -x <proxy> -k "$BASE/path"` needs no headers at all (see M&R).

## History + Replay commands

```
npx tsx caido-client.ts search '<httpql>' --compact --limit 50   # newest first
npx tsx caido-client.ts recent --compact                         # newest, no filter
npx tsx caido-client.ts get 8431 --compact                       # full detail
npx tsx caido-client.ts get-response 8431 --compact
npx tsx caido-client.ts raw 8431 --out /tmp/caido/target.com/body.json   # byte-exact dump
npx tsx caido-client.ts export-curl 8431                         # FULL curl, for the operator

# Handoff sessions (names mandatory; CRLF auto-normalized from raw files)
npx tsx caido-client.ts create-session 8431 --name "IDOR /api/user/:id"
npx tsx caido-client.ts send-raw --host target.com --raw @/tmp/req.txt --name "crafted repro"
npx tsx caido-client.ts sessions ; collections
npx tsx caido-client.ts rename-session "old" "new" ; move-session "<name>" "<collection>"

# Edit + send (preserves cookies/auth; requires --nonach or --new-name)
npx tsx caido-client.ts edit 8431 --path /api/user/999 --name "IDOR victim 999"
npx tsx caido-client.ts edit-session "IDOR victim 999" --body '{"role":"admin"}' --nonach

# Inspect an open replay tab (by name or id)
npx tsx caido-client.ts get-session "IDOR victim 999" --compact
npx tsx caido-client.ts replay-entries "IDOR victim 999" --limit 20
```

- `edit` supports `--method --path --set-header --remove-header --body` (auto
  Content-Length) `--replace <from>:::<to>` and connection overrides
  (`--sni --connect-host --connect-port ...`) for v-host/upstream routing tests.
- Collections: query FIRST (`collections`), never auto-create. One reproduced
  request -> default collection, just name the session. Multi-request chain ->
  `Vuln chain - <description>` with steps named `1. ...`, `2. ...`. Endpoints from
  one JS file -> `JS File Endpoints`; from a spec -> `Swagger - <filename>`.
- Evidence pairs: `raw <id> --out` (or VM `~/caido.sh raw <id> req|resp`) ->
  `targets/<eng>/poc/` (verbatim source), same policy as [[evidence]].
- `create-finding <id> --title ... --description ...` logs confirmed finds in the
  project so they surface in the GUI Findings tab alongside [[evidence]] cards.

## Match & Replace (tamper rules)

Rewrites requests/responses automatically as they pass through Caido. Killer use:
inject auth at the proxy, so probe curls carry no headers at all.

A rule = section x operation x matcher x replacer, optional HTTPQL `--condition`
and `--sources`:

| Piece | Choices |
|-------|---------|
| section | req: `req-method req-path req-query req-body req-first-line req-header req-all req-sni` ; resp: `resp-body resp-status resp-first-line resp-header resp-all` ; ws: `ws-up ws-down` |
| operation | `raw` (match within section) ; `update`/`add`/`remove` (header + query only, by name) |
| matcher | `--match-value <s>` / `--match-regex <re>` / `--match-full` / `--match-name <n>` |
| replacer | `--replace <term>` (literal, `""` allowed) / `--workflow <id>` |

```
# Preview without creating anything:
npx tsx caido-client.ts test-mr-rule --section req-header --operation add \
  --match-name X-Test --replace hi --raw 'GET / HTTP/1.1\r\nHost: t.com\r\n\r\n'

# Inject auth on all proxied requests to one host, then enable:
ID=$(npx tsx caido-client.ts create-mr-rule --section req-header --operation add \
  --match-name Authorization --replace "Bearer eyJ..." \
  --condition 'req.host.eq:"target.com"' --name "auth inject" | jq -r '.created.id')
npx tsx caido-client.ts toggle-mr-rule "$ID" --on

npx tsx caido-client.ts mr-rules ; toggle-mr-rule <id> --off ; delete-mr-rule <id>
```

Gotchas: new rules are created DISABLED (`toggle-mr-rule <id> --on`); default
sources is `INTERCEPT` (proxy traffic) so add `--sources REPLAY,...` to broaden;
default collection is Caido's "Default Collection". For minified JS use
`--match-regex` anchored to structurally stable neighbours (string literals, JSON
keys), NOT `--match-value` on a minified identifier, since those rotate every
deploy and the rule silently stops matching.

## HTTPQL reference

`<ns>.<field>.<op>:"<value>"`; string values MUST be quoted, integers are NOT.
**There is no `NOT` operator**: use the negated ops `ne`, `ncont`, `nlike`,
`nregex`.

| Namespace | Field | Type | Meaning |
|-----------|-------|------|---------|
| `req` | `ext` `host` `method` `path` `query` `raw` | string | request parts (ext includes `.`) |
| `req` | `port` `len` | int | port, body length |
| `req` | `created_at` `tls` | date/bool | timestamp, HTTPS |
| `resp` | `raw` | string | full raw response |
| `resp` | `code` `len` `roundtrip` | int | status, body length, ms |
| `row` | `id` | int | request id |
| `source` | - | special | `intercept` `replay` `automate` `workflow` |
| `preset` | - | special | saved filter preset name |

Operators: string `eq ne cont ncont like nlike regex nregex`; int
`eq ne gt gte lt lte`; bool `eq ne`; combine with `AND`/`OR` and parentheses.

```
req.method.eq:"POST" AND resp.code.eq:200
req.host.cont:".target.com" AND resp.code.gte:500
"password" OR "secret" OR "api_key"          # bare strings search req+resp raw
resp.len.gt:100000                           # large responses
req.path.regex:"/(login|auth|signin|oauth)/"
source:"replay" OR source:"intercept"
req.created_at.gt:"2026-01-01T00:00:00Z"
req.path.ncont:"/static"                     # exclusion without NOT
```

Full reference: docs.caido.io/app/reference/httpql.

## `~/caido.sh` (VM-local helper, over vm.sh)

```
bash /root/vm.sh '~/caido.sh status'    # process + ui + proxy + token-valid
bash /root/vm.sh '~/caido.sh start'     # detached; auto-skips if running
bash /root/vm.sh '~/caido.sh stop'
bash /root/vm.sh '~/caido.sh history "req.host.eq:\"target.com\"" 20'
bash /root/vm.sh '~/caido.sh raw 15 resp'
bash /root/vm.sh '~/caido.sh send /tmp/req.txt target.com 443 1'   # Replay send
bash /root/vm.sh '~/caido.sh cookies target.com'
bash /root/vm.sh '~/caido.sh project'    # list + selected; 'project <n>' create+select
bash /root/vm.sh '~/caido.sh gql "<query>" "<vars-json>"'
```

Source of truth `scripts/caido.sh`; re-push with
`bash /root/vm.sh 'tee ~/caido.sh >/dev/null; chmod +x ~/caido.sh' < scripts/caido.sh`.
Schema drifts between releases (0.58.3: `startReplayTask(sessionId)` takes NO input;
`replayEntry` needs the `ReplayEntryHttp` fragment). On a field error, introspect
first (`__type(name:"...")`), or check github.com/caido/schemas; do not trust older
doc snippets. The SDK CLI absorbs most of this; `gql` is the escape hatch.

## Fuzz batteries (request-variation through Replay)

`~/caido.sh fuzz <template> <payloads> <host> [port] [tls] [delay]`: template =
full HTTP/1.1 request with `{{PAYLOAD}}` marker(s), payloads one per line; each
variant is its own Replay session (operator-visible); output `STATUS bytes session
payload` per line, triage by differential. Authenticated batteries carry
`{{COOKIE}}` and refuse unless `CAIDO_COOKIE` is set
(`CAIDO_COOKIE="$(~/caido.sh cookies target.com)"`); one-command wrapper
`bash scripts/caido-battery.sh target.com pays.txt`.

Typical batteries vary ONE thing per run: parameter values, formats, headers
(token swap, X-Original-URL, method override), verb/path variants. Bounds: 60
payloads, 0.3s delay; RoE on top (`no_bruteforce` = shape variation, NEVER cred
spraying; back off on 5xx). Payloads render bash-natively, pre-encode them
(`=` -> `%3D`). End-to-end authed lane: browser through the proxy ->
`cookies <host>` -> battery -> Autorize plugin diffs triplets = IDOR lane
([[hunt-idor]]). Recon-phase variation routes here when scanners are RoE-barred
(serial, bounded, visible beats a banned ffuf); where wordlist scanners are
permitted, `Skill(fuzz)` stays primary. Automate (CLI `create-automate-session
<id>` then configure payloads in the GUI) is the Caido-native equivalent.

## Caido-native workflow (GUI concepts)

- **Proxying traffic**: point any client at `192.168.23.128:8080` (`curl -kx`,
  chromium proxy). Everything lands in History of the selected project.
- **Scopes / Filters**: scope preset from `targets/<eng>/scope.md`
  (`create-scope "Target" --allow "*.target.com" --deny "*.cdn..."`), filter
  presets via `create-filter "name" --query '<httpql>' --alias <short>` then
  `search 'preset:"<alias>"'`. Scoping inside Caido does NOT replace the RoE
  scope-guard (API calls are invisible to it; you own the check).
- **Environments / hosted Files**: per-engagement vars + wordlists, referenced as
  `{{env.VAR}}` in Replay; `create-env`, `env-set <env> <var> <val>`.
- **Workflows** (preprocessors, can emit Findings) and **Exports** (requests to
  files for the report): GUI; raw pairs still go to `targets/<eng>/poc/`.
- **Plugins** (Pro): install headless via gql
  `installPluginPackage(input: {source: {url: <release-zip>}})`, toggle with
  `togglePlugin(id, enabled)`. Worth it: Scanner (passive mode adds ZERO target
  requests, RoE-safe) and Autorize (IDOR triplets; needs one authenticated
  session). Shift (BYO-key LLM) is redundant when the agent is the LLM lane.
- **Intercept**: `intercept-status` / `intercept-enable` / `intercept-disable`
  (rarely wanted: the agent works from History, not a held queue).

## Output control + gotchas

- `--compact` = `--no-request --max-body 50 --max-body-chars 5000`; also
  `--max-body <n>` / `--max-body-chars <n>` (0 = unlimited), `--headers-only`.
  Browse with `--compact`; `get`/`export-curl` only the request you work from.
- `search` is NEWEST FIRST; `--limit N` = newest N matches. Never fetch a big
  window and re-sort client-side (you only sort the truncated window); let Caido
  order. `recent` takes no filter.
- Do NOT batch CLI calls inside `while`/`for` loops (PATH can get stripped in loop
  subshells and the body fails silently); one top-level command each, or a
  standalone script with an explicit `export PATH`.
- `search --ids-only` returns a JSON array (`["123"]`): unwrap with
  `jq -r '.[0]'`.

## Error handling

- Auth errors / `No Caido auth found` -> `auth-status`; re-`setup <pat>`, or
  re-prime from the VM token (above).
- Probes turn 401/403/login-redirect -> token aged out; regenerate the config from
  a fresh history id.
- Proxy connect refused -> `health`; if down, `bash /root/vm.sh '~/caido.sh start'`.
- gql field errors -> schema drifted; introspect (see `~/caido.sh` section).

## Relation to Burp

Burp stays the primary transport when its MCP is up ([[hunt-burp]]). Reach for
Caido when: Burp/MCP is down, you want a per-engagement isolated project, the
target needs Automate-style bulk runs, or the operator prefers the lighter GUI.
Same discipline either way: load-bearing requests must be visible to the operator
(Replay entries here, Repeater tabs there), never silent background curl.
