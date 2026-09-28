---
name: caido
description: Drive the headless Caido instance on the Kali VM - web-audit proxy (HTTP/WS history), HTTPQL triage, Replay sends, Automate bulk runs, Match & Replace, Findings/Exports - via the helper script over vm.sh plus the web UI at http://192.168.23.128:8082. Use as the proxy layer when Burp/MCP is down, for a per-engagement isolated project, or for any Caido-native feature (Automate, workflows).
---

# Caido (headless instance on Kali)

Caido is a Rust web-security proxy: one `caido` binary on the VM runs the instance
(server), serves the web GUI, and exposes the GraphQL API the GUI itself uses. The
agent drives everything through that GraphQL API; the operator watches the same data
in the GUI at http://192.168.23.128:8082. Wiki: [[caido]].

## The box (already set up)

- Kali VM: `caido` 0.58.3 at `/usr/local/bin/caido`, instance runs headless
  (`--no-open --allow-guests --listen 0.0.0.0:8082 --proxy-listen 0.0.0.0:8080`),
  log `/tmp/caido.log`, data `~/.local/share/caido/` (SQLite, projects live here).
- Claimed by the account (instance name `kali-vm`); Pro features active.
- **Project `default` selected. A project MUST be selected or the proxy 500s every
  request ("Could not acquire a connection to the database").** Per engagement create
  + select a fresh project (GraphQL `createProject`/`selectProject`) to isolate traffic.
- API auth: Bearer token in `~/.caido-token` (VM), 7-day expiry, refresh below.
- Helper on VM: `~/caido.sh` (source of truth `scripts/caido.sh`; re-push with
  `bash /root/vm.sh 'tee ~/caido.sh >/dev/null; chmod +x ~/caido.sh' < scripts/caido.sh`).
- Ports: GUI/GraphQL `8082`, proxy `8080` - both reachable from the host
  (`http://192.168.23.128:8082`, proxy `192.168.23.128:8080`). MITM HTTPS: `curl -k`,
  or import Caido's CA (Settings -> Certificates) into the client.

## Lifecycle + token refresh

```
bash /root/vm.sh '~/caido.sh status'    # process + ui + proxy + token-valid
bash /root/vm.sh '~/caido.sh start'     # detached; auto-skips if running
bash /root/vm.sh '~/caido.sh stop'
```

Token expired (`token-valid:no` / auth errors)? Re-extract from the logged-in GUI:
open http://127.0.0.1:8082 in the VM chromium (`scripts/browser.sh`), then with
chrome-devtools MCP `evaluate_script` on that tab:
`JSON.parse(localStorage.CAIDO_AUTHENTICATION).accessToken` -> write to VM
`~/.caido-token` (chmod 600). GUI session itself stays logged in far longer.

## Agent surface (all over vm.sh, one command per call)

```
bash /root/vm.sh '~/caido.sh history "req.host.eq:\"target.com\"" 20'   # HTTPQL-filtered history
bash /root/vm.sh '~/caido.sh raw 15 resp'     # full raw response of captured req 15 (req for the request)
bash /root/vm.sh '~/caido.sh send /tmp/req.txt target.com 443 1'        # Replay send, prints raw response
bash /root/vm.sh '~/caido.sh fuzz /tmp/tpl.txt /tmp/pays.txt t.com 443 1 0.4'  # variant battery
bash /root/vm.sh '~/caido.sh gql "<query>" "<vars-json>"'               # anything else, ad hoc
```

- `send`: file = full HTTP/1.1 request text; creates a Replay session + entry the
  operator can see/resend in the GUI (Replay tab). Load-bearing requests go through
  `send`, never bare curl, so they are visible + repeatable.
- Evidence pairs: `raw <id> req` / `raw <id> resp` -> `targets/<eng>/poc/` (verbatim
  source), same policy as [[evidence]].
- Schema is public but drifts between releases (0.58.3: `startReplayTask(sessionId)`
  takes NO input; `replayEntry(id, sessionKind: HTTP)` needs the `ReplayEntryHttp`
  fragment for request/response). On a field error, introspect first:
  `__type(name:"...")` / `__schema { mutationType { fields { name } } }`, or check
  github.com/caido/schemas. Do NOT trust older docs snippets blindly.

## Fuzz batteries (request-variation through Replay)

`fuzz <template> <payloads> <host> [port] [tls] [delay]`: template = full HTTP/1.1
request with `{{PAYLOAD}}` marker(s), payloads = one per line. Each variant sends as
its own Replay session (operator-visible); output is `STATUS  bytes  session  payload`
per line - triage by status/length differential, then pull the interesting body via
`gql replayEntry` or re-send the variant with `send`.

Typical batteries (vary ONE thing per run): parameter values (where/filter/ID tamper),
formats (f=json/geojson/html/pjson), headers (auth token swap, X-Original-URL,
method override), verb/path variants. Baked-in bounds: 60-payload cap, 0.3s default
delay; RoE still applies on top (no_bruteforce = shape variation, NEVER cred/
password spraying; back off on 5xx; anti-lockout). Note: payloads render bash-natively,
no URL-encoding is done for you - pre-encode (`=` -> `%3D`, space -> `+`).

Recon-phase fuzzing (content/param/discovery variation) routes through this lane too
when scanners are RoE-barred (serial, bounded, operator-visible beats a banned ffuf)
or when every request must be replay-visible; where wordlist scanners are permitted,
`Skill(fuzz)` stays the primary lane and Caido is the fallback/visibility layer.

## HTTPQL (filter language, used by history + GUI filters + Automate)

`<ns>.<field>.<op>:"<value>"` with ns `req`/`resp`/`row`; combine with `and`/`or`.

```
req.host.cont:".target.com"                resp.code.eq:403
req.path.cont:"/api/" and resp.code.gte:500
req.raw.cont:"isAdmin"                     req.method.eq:"POST" or req.method.eq:"PUT"
```
Full field/op reference: docs.caido.io/app/reference/httpql.

## Caido-native workflow (GUI concepts the agent maps onto)

- **Proxying traffic through it**: point any client at `192.168.23.128:8080`
  (`curl -kx`, chromium proxy, foxyproxy). Everything lands in HTTP History of the
  selected project.
- **Scopes / Filters**: define a scope preset from `targets/<eng>/scope.md`
  (GUI: Scopes, or `scopes`/GraphQL) and filter presets from HTTPQL; scoping inside
  Caido does NOT replace the RoE scope-guard (gql calls are invisible to it - you
  own the check).
- **Replay**: `send` per load-bearing request; GUI for manual tweak-and-resend.
- **Match & Replace** (tamper rules): header/param rewrites on live traffic - useful
  for auth-token swapping, testing header injection. GUI or `tamperRuleCollections`.
- **Automate**: bulk request runs (wordlist payloads + extractors + rate limits) -
  Caido's Intruder equivalent. Build in the GUI; monitor/collect via
  `automateSessions`/`automateTasks` queries. RoE first: `no_bruteforce` and
  anti-lockout rules apply exactly as to Burp Intruder.
- **Workflows** (preprocessors on requests/responses, can emit Findings) and
  **Environment variables / hosted Files** (wordlists, `{{env.VAR}}` placeholders in
  Replay): per-engagement setup in the GUI, persisted in the project.
- **Findings + Exports**: log confirmed findings in-project (GUI Findings), export
  requests to files (Exports) for the report; raw pairs still go to `targets/<eng>/poc/`.
- **Plugins** (Pro): install headless via gql `installPluginPackage(input:
  {source: {url: <release-zip>}})` -> `pluginPackages { plugins { id enabled } }`;
  `togglePlugin(id, enabled)` flips them. Official ones worth installing: Scanner
  (checks engine - passive mode adds ZERO target requests, RoE-safe; active mode
  is scanner-class tooling, respect RoE) and Autorize (baseline/mutated/no-auth
  request diffs = the IDOR lane; needs one authenticated session). Shift (BYO-key
  LLM) is redundant when the agent is the LLM lane.

## Relation to Burp

Burp stays the primary transport when its MCP is up ([[hunt-burp]]). Reach for Caido
when: Burp/MCP is down, you want a per-engagement isolated project, the target needs
Automate-style bulk runs, or the operator prefers the lighter GUI. Same discipline
either way: load-bearing requests must be visible to the operator (Replay entries
here, Repeater tabs there) - never silent background curl.
