#!/usr/bin/env bash
# caido.sh - drive the headless Caido instance on the Kali VM. Vault copy is source of
# truth; push to the VM once:  bash scripts/vm-ssh.sh 'cat > ~/caido.sh && chmod +x ~/caido.sh' < scripts/caido.sh
# (or:  bash /root/vm.sh 'tee ~/caido.sh >/dev/null; chmod +x ~/caido.sh' < scripts/caido.sh)
# Run ON the VM (via vm.sh). Companion skill: skills/caido. Token: ~/.caido-token (7-day expiry, see skill).
set -euo pipefail

TOK="${CAIDO_TOKEN:-$(cat ~/.caido/token 2>/dev/null || cat ~/.caido-token 2>/dev/null || true)}"
API="${CAIDO_API:-http://127.0.0.1:8082/graphql}"
LISTEN="${CAIDO_LISTEN:-0.0.0.0:8082}"
PROXY_LISTEN="${CAIDO_PROXY_LISTEN:-0.0.0.0:8080}"

die() { echo "caido.sh: $*" >&2; exit 1; }
need_tok() { [ -n "$TOK" ] || die "no token (~/.caido-token empty/missing; re-extract per skills/caido)"; }

# gql <query-string> [variables-json] -> raw JSON response
gql() {
  need_tok
  local q="$1" v="${2:-{\}}"
  jq -n --arg q "$q" --argjson v "$v" '{query:$q, variables:$v}' \
    | curl -s -m 60 "$API" -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' -d @-
}

cmd_start() {
  pgrep -x caido >/dev/null && { echo "already running: $(pgrep -x caido)"; return 0; }
  setsid nohup caido --no-open --allow-guests --listen "$LISTEN" --proxy-listen "$PROXY_LISTEN" >/tmp/caido.log 2>&1 &
  sleep 3
  pgrep -x caido >/dev/null || { tail -5 /tmp/caido.log; die "failed to start"; }
  echo "started: $(pgrep -x caido | head -1) ui=$LISTEN proxy=$PROXY_LISTEN log=/tmp/caido.log"
}

cmd_stop() {
  pkill -x caido && echo stopped || echo "not running"
}

cmd_status() {
  local up=""
  pgrep -x caido >/dev/null && up="process:$(pgrep -x caido | head -1)" || up="process:DOWN"
  local ui pr tok
  ui=$(curl -s -o /dev/null -m 3 -w '%{http_code}' "http://127.0.0.1:${LISTEN#*:}" 2>/dev/null || echo 000)
  pr=$(curl -s -o /dev/null -m 5 -x "http://127.0.0.1:${PROXY_LISTEN#*:}" -w '%{http_code}' http://example.com 2>/dev/null || echo 000)
  tok=no
  if [ -n "$TOK" ]; then
    gql 'query { currentProject { project { id } } }' 2>/dev/null | jq -e '.data.currentProject.project.id != null' >/dev/null 2>&1 && tok=yes
  fi
  echo "caido $up ui:$ui proxy:$pr token-valid:$tok api:$API"
}

# history "<httpql>" [count] - list captured requests (HTTPQL e.g. 'req.host.eq:"example.com"')
cmd_history() {
  local code="${1:?need httpql filter, e.g. 'req.host.eq:\"example.com\"'}" n="${2:-10}"
  gql 'query H($code: String!) { requests(last: '"$n"', filter: {code: $code}) { edges { node { id method host path query response { statusCode } } } } }' \
    "$(jq -cn --arg code "$code" '{code: $code}')" \
    | jq -r '.data.requests.edges[].node | "\(.id)\t\(.method)\t\(.response.statusCode // "-")\t\(.host)\(.path)\(if .query then "?"+.query else "" end)"'
}

# raw <request-id> [resp|req] - print the full raw request (default) or response, decoded
cmd_raw() {
  local id="${1:?need request id}" part="${2:-resp}"
  if [ "$part" = resp ]; then
    gql 'query R($id: ID!) { request(id: $id) { response { statusCode raw } } }' "{\"id\": \"$id\"}" \
      | jq -r '.data.request.response.raw' | base64 -d
  else
    gql 'query R($id: ID!) { request(id: $id) { raw } }' "{\"id\": \"$id\"}" \
      | jq -r '.data.request.raw' | base64 -d
  fi
}

# findings [count] - list in-project findings (Scanner passive checks, workflows, manual)
cmd_findings() {
  local n="${1:-20}"
  gql 'query F($first: Int!) { findings(first: $first) { edges { node { id title reporter host path createdAt } } } }' "{\"first\": $n}" \
    | jq -r '.data.findings.edges[].node | "\(.id)\t\(.reporter)\t\(.host)\(.path)\t\(.title)\t\(.createdAt)"'
}

# cookies <host> - print the Cookie header of the most recent captured request to host
# (login through the proxy once, then reuse the session in hand-crafted templates:
#  CAIDO_COOKIE="$(~/caido.sh cookies host)" ~/caido.sh fuzz ... with a {{COOKIE}} template)
cmd_cookies() {
  local host="${1:?need host}" id
  id=$(gql 'query H($code: String!) { requests(last: 1, filter: {code: $code}) { edges { node { id } } } }' \
    "$(jq -cn --arg code "req.host.eq:\"$host\"" '{code: $code}')" \
    | jq -r '.data.requests.edges[0].node.id // empty')
  [ -n "$id" ] || { echo "# no captured requests for $host" >&2; return 1; }
  local line
  line=$(gql 'query R($id: ID!) { request(id: $id) { raw } }' "{\"id\": \"$id\"}" \
    | jq -r '.data.request.raw' | base64 -d | grep -i '^Cookie:' | head -1 || true)
  [ -n "$line" ] || { echo "# last captured request to $host carried no Cookie header" >&2; return 1; }
  printf '%s\n' "$line"
}

# send <raw-request-file> <host> [port] [tls 0|1] - create Replay session, send, print response.
# Raw file: full HTTP/1.1 request text. TLS=1 for https targets.
cmd_send() {
  local f="${1:?need raw request file}" host="${2:?need host}" port="${3:-80}" tls="${4:-0}"
  [ -r "$f" ] || die "cannot read $f"
  local raw; raw=$(base64 -w0 "$f")
  local sni="$host"; [ "$tls" = 1 ] && port="${3:-443}"
  local sid
  sid=$(gql 'mutation C($input: CreateReplaySessionInput!) { createReplaySession(input: $input) { session { id } error { __typename } } }' \
    "$(jq -cn --arg host "$host" --arg sni "$sni" --arg raw "$raw" --argjson port "$port" --argjson tls "$([ "$tls" = 1 ] && echo true || echo false)" \
      '{input: {kind: "HTTP", requestSource: {raw: {connectionInfo: {host: $host, port: $port, isTLS: $tls, SNI: $sni}, raw: $raw}}}}')" \
    | jq -r '.data.createReplaySession.session.id // empty')
  [ -n "$sid" ] || die "createReplaySession failed"
  local eid
  eid=$(gql 'mutation S($sessionId: ID!) { startReplayTask(sessionId: $sessionId) { task { replayEntry { id } } error { __typename } } }' \
    "$(jq -cn --arg sid "$sid" '{sessionId: $sid}')" \
    | jq -r '.data.startReplayTask.task.replayEntry.id // empty')
  [ -n "$eid" ] || die "startReplayTask failed"
  # poll for the response (replay entries fill in async)
  local i out=""
  for i in 1 2 3 4 5 6 7 8 9 10; do
    out=$(gql 'query G($id: ID!) { replayEntry(id: $id, sessionKind: HTTP) { error ... on ReplayEntryHttp { request { response { statusCode raw } } } } }' "{\"id\": \"$eid\"}")
    echo "$out" | jq -e '.data.replayEntry.request.response.raw != null' >/dev/null 2>&1 && break
    sleep 1
  done
  echo "# replay session=$sid entry=$eid"
  echo "$out" | jq -r '.data.replayEntry.error // empty' >&2 || true
  echo "$out" | jq -r '.data.replayEntry.request.response.statusCode // empty' >&2 || true
  echo "$out" | jq -r '.data.replayEntry.request.response.raw // "NO RESPONSE (timeout)"' | base64 -d
}

# fuzz <template-file> <payloads-file> <host> [port] [tls 0|1] [delay-s]
# Template: full HTTP/1.1 request with one or more {{PAYLOAD}} markers; payloads file:
# one per line. Each variant goes out as its own Replay session (operator-visible in
# the GUI Replay tab). Prints: STATUS<TAB>bytes<TAB>session<TAB>payload per variant.
# RoE bounds: hard cap 60 payloads, default 0.3s between sends. no_bruteforce applies:
# this is for request-shape variation, never credential/password spraying.
cmd_fuzz() {
  local tf="${1:?need template file}" pf="${2:?need payloads file}" host="${3:?need host}" port="${4:-80}" tls="${5:-0}" delay="${6:-0.3}"
  [ -r "$tf" ] || die "cannot read $tf"
  [ -r "$pf" ] || die "cannot read $pf"
  local tpl; tpl=$(cat "$tf")
  grep -q '{{PAYLOAD}}' <<<"$tpl" || die "template lacks {{PAYLOAD}} marker"
  if grep -q '{{COOKIE}}' <<<"$tpl"; then
    [ -n "${CAIDO_COOKIE:-}" ] || die "template has {{COOKIE}} but CAIDO_COOKIE is unset (run: CAIDO_COOKIE=\"\$(~/caido.sh cookies <host>)\" ...)"
    tpl="${tpl//\{\{COOKIE\}\}/$CAIDO_COOKIE}"
  fi
  local n; n=$(grep -c . "$pf" || true)
  [ "$n" -gt 60 ] && die "$n payloads exceeds the 60-payload cap (RoE); split the battery"
  [ "$tls" = 1 ] && port="${4:-443}"
  local p req raw sid eid out code len i
  while IFS= read -r p; do
    [ -n "$p" ] || continue
    req="${tpl//\{\{PAYLOAD\}\}/$p}"
    # $(cat) strips the trailing blank line; restore it or the request never terminates
    raw=$(printf '%s\n\n' "$req" | base64 -w0)
    # set -e aborts the WHOLE battery on one transient gql hiccup (seen: 8/12 lines,
    # no error, remaining payloads silently unsent). || true on the three in-loop gql
    # calls routes every failure to the per-variant ERR/PEND lines, so the invariant
    # line-count == payload-count always holds.
    sid=$(gql 'mutation C($input: CreateReplaySessionInput!) { createReplaySession(input: $input) { session { id } error { __typename } } }' \
      "$(jq -cn --arg host "$host" --arg sni "$host" --arg raw "$raw" --argjson port "$port" --argjson tls "$([ "$tls" = 1 ] && echo true || echo false)" \
        '{input: {kind: "HTTP", requestSource: {raw: {connectionInfo: {host: $host, port: $port, isTLS: $tls, SNI: $sni}, raw: $raw}}}}')" \
      | jq -r '.data.createReplaySession.session.id // empty' || true)
    if [ -z "$sid" ]; then printf 'ERR\t0\t-\t%s\n' "$p"; continue; fi
    eid=$(gql 'mutation S($sessionId: ID!) { startReplayTask(sessionId: $sessionId) { task { replayEntry { id } } error { __typename } } }' \
      "$(jq -cn --arg sid "$sid" '{sessionId: $sid}')" \
      | jq -r '.data.startReplayTask.task.replayEntry.id // empty' || true)
    out=""
    for i in 1 2 3 4 5 6; do
      out=$(gql 'query G($id: ID!) { replayEntry(id: $id, sessionKind: HTTP) { error ... on ReplayEntryHttp { request { response { statusCode raw } } } } }' "{\"id\": \"${eid:-0}\"}" || true)
      echo "$out" | jq -e '.data.replayEntry.request.response.raw != null' >/dev/null 2>&1 && break
      sleep 1
    done
    code=$(echo "$out" | jq -r 'if .data.replayEntry.request.response.statusCode then .data.replayEntry.request.response.statusCode elif .data.replayEntry.request then "PEND" else "ERR" end' 2>/dev/null || echo ERR)
    len=$(echo "$out" | jq -r '.data.replayEntry.request.response.raw // ""' 2>/dev/null | base64 -d 2>/dev/null | wc -c)
    # 3rd column carries BOTH ids: session/eid - `raw <eid>` pulls the body straight
    # from history without the manual mapping step (bit the sportas-version2 lane)
    printf '%s\t%s\t%s/%s\t%s\n' "$code" "$len" "$sid" "${eid:-0}" "$p"
    sleep "$delay"
  done < "$pf"
}

# project [name] - list projects (+ which is selected); with a name: create + select
cmd_project() {
  if [ -z "${1:-}" ]; then
    local cur; cur=$(gql 'query { currentProject { project { name } } }' | jq -r '.data.currentProject.project.name // "none"')
    gql 'query { projects { id name } }' | jq -r --arg cur "$cur" '.data.projects[] | "\(.name)\t\(.id)\t\(if .name == $cur then "SELECTED" else "" end)"'
    return
  fi
  local pid
  pid=$(gql 'mutation C($input: CreateProjectInput!) { createProject(input: $input) { project { id } error { __typename } } }' \
    "$(jq -cn --arg name "$1" '{input: {name: $name, temporary: false}}')" \
    | jq -r '.data.createProject.project.id // empty')
  [ -n "$pid" ] || die "createProject failed"
  gql 'mutation S($id: ID!) { selectProject(id: $id) { __typename } }' "{\"id\": \"$pid\"}" >/dev/null
  echo "created+selected: $1 ($pid)"
}

case "${1:-}" in
  start) cmd_start ;;
  stop) cmd_stop ;;
  status) cmd_status ;;
  gql) shift; gql "$@" ;;
  history) shift; cmd_history "$@" ;;
  findings) shift; cmd_findings "$@" ;;
  cookies) shift; cmd_cookies "$@" ;;
  project) shift; cmd_project "$@" ;;
  raw) shift; cmd_raw "$@" ;;
  send) shift; cmd_send "$@" ;;
  fuzz) shift; cmd_fuzz "$@" ;;
  *) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; echo; echo "usage: caido.sh {start|stop|status|gql|history|findings|cookies|project|raw|send|fuzz} ..."; exit 2 ;;
esac
