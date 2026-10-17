#!/usr/bin/env bash
# interceptor-automation.sh - bring up the ISOLATED interceptor browser stack.
# LAW (operator 2026-10-14): NEVER drive the operator's Chrome profiles
# (Tomas/buck4bug/renata = OUT OF BOUNDS). Always the dedicated Edge
# automation instance, always incognito. One command, idempotent.
#
# Usage: bash scripts/interceptor-automation.sh up|down|status|context
set -euo pipefail

EXT_DIST="C:/Users/Lenovo/AppData/Local/hermes/tools/interceptor/extension/dist"
PROFILE="C:/Users/Lenovo/AppData/Local/hermes/tools/interceptor/edge-profile"
EDGE="C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
DAEMON="C:/Users/Lenovo/AppData/Local/hermes/tools/interceptor/daemon/interceptor-daemon.exe"
CLI="C:/Users/Lenovo/.bun/bin/bun.exe C:/Users/Lenovo/AppData/Local/hermes/tools/interceptor/dist/interceptor"
# NOTE: $CLI must stay UNQUOTED at call sites (two words: bun + exe)
CDP=9334
WS_CONTEXT_FILE="C:/Users/Lenovo/AppData/Local/hermes/tools/interceptor/edge-context.txt"

edge_pids() {
  powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | Where-Object { \$_.CommandLine -match 'interceptor.edge-profile' } | Select-Object -ExpandProperty ProcessId" 2>/dev/null | tr -d '\r'
}

ctx() {
  $CLI contexts --verbose 2>/dev/null | grep -E "gomcpnagjjlhehnkoobkjgnkbleiooed" | grep -v "a4e0373f" | awk '{print $1}' | head -1 || true
}

case "${1:-status}" in
  up)
    # 1. persistent daemon (the WAKE LAW)
    if ! netstat -an | grep -q "127.0.0.1:19222.*LISTENING"; then
      echo "daemon: starting (persistent)"
      INTERCEPTOR_SPIN_WATCHDOG=off "$DAEMON" --standalone &
    fi
    # 2. Edge automation instance (incognito by launch flag, ONLY our extension)
    # EXTRA_ARGS (space-separated) appends operator-approved flags - e.g. Caido routing:
    #   EXTRA_ARGS="--proxy-server=http://192.168.23.128:8080 --ignore-certificate-errors"
    if [ -z "$(edge_pids)" ]; then
      echo "edge: launching isolated instance${EXTRA_ARGS:+ (extra: $EXTRA_ARGS)}"
      if [ -n "${EXTRA_ARGS:-}" ]; then
        EXTRA_PS=$(printf ",'%s'" $EXTRA_ARGS)
        powershell.exe -NoProfile -Command "Start-Process '$EDGE' -ArgumentList @('--user-data-dir=$PROFILE','--load-extension=$EXT_DIST','--disable-extensions-except=$EXT_DIST','--no-first-run','--no-default-browser-check','--remote-debugging-port=$CDP','--incognito','${2:-about:blank}'${EXTRA_PS})" >/dev/null 2>&1
      else
        powershell.exe -NoProfile -Command "Start-Process '$EDGE' -ArgumentList '--user-data-dir=$PROFILE','--load-extension=$EXT_DIST','--disable-extensions-except=$EXT_DIST','--no-first-run','--no-default-browser-check','--remote-debugging-port=$CDP','--incognito','${2:-about:blank}'" >/dev/null 2>&1
      fi
    fi
    # 3. wait for the extension context + grant incognito via CDP developerPrivate (idempotent)
    until [ -n "$(ctx)" ]; do sleep 2; done
    C="$(ctx)"; echo "$C" > "$WS_CONTEXT_FILE"
    # HARDENING (operator 2026-10-14): write the CLI context allowlist - the daemon
    # can then NEVER auto-route a call to a stray extension (e.g. the operator's
    # personal Chrome if its extension ever comes back); unpinned calls default
    # to the automation Edge context; unknown contexts are refused outright.
    TOOLS_DIR="C:/Users/Lenovo/AppData/Local/hermes/tools/interceptor"
    printf '{"defaultContext":"%s","allowedContexts":["%s"]}
' "$C" "$C" > "$TOOLS_DIR/context-config.json"
    PAGE=$(curl -s "http://127.0.0.1:$CDP/json/new?edge://extensions/" 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])" 2>/dev/null || true)
    if [ -n "$PAGE" ]; then
      C:/Users/Lenovo/.bun/bin/bun.exe -e "
const ws = new WebSocket('ws://127.0.0.1:$CDP/devtools/page/$PAGE');
ws.onopen = () => ws.send(JSON.stringify({id:1, method:'Runtime.evaluate', params:{expression:\"chrome.developerPrivate.updateExtensionConfiguration({extensionId:'gomcpnagjjlhehnkoobkjgnkbleiooed', incognitoAccess:true}, ()=>{}) ; 'granted'\", awaitPromise:false}}));
ws.onmessage = () => process.exit(0);
setTimeout(()=>process.exit(0), 6000);" >/dev/null 2>&1 || true
      curl -s -X DELETE "http://127.0.0.1:$CDP/json/close/$PAGE" >/dev/null 2>&1 || true
    fi
    echo "context: $C  (export INTERCEPTOR_CONTEXT=$C before CLI calls)"
    echo "READY"
    ;;
  down)
  powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | Where-Object { \$_.CommandLine -match 'interceptor.edge-profile' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force -ErrorAction SilentlyContinue }" >/dev/null 2>&1 || true
  echo "edge automation instance stopped (daemon left running)"
    ;;
  status)
  P=$(edge_pids | head -1); [ -n "$P" ] && echo "edge: RUNNING (pid $P)" || echo "edge: down"
  netstat -an | grep -q "127.0.0.1:19222.*LISTENING" && echo "daemon: LISTENING" || echo "daemon: down"
  C="$(ctx)"; [ -n "$C" ] && echo "context: $C CONNECTED" || echo "context: none"
  ;;
  context) ctx ;;
  *) echo "usage: $0 up|down|status|context" >&2; exit 2 ;;
esac
