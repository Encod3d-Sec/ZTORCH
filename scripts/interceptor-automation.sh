#!/usr/bin/env bash
# interceptor-automation.sh - bring up the ISOLATED interceptor browser stack.
# LAW (operator 2026-10-14): NEVER drive the operator's Chrome profiles
# (Tomas/buck4bug/renata = OUT OF BOUNDS). Always the dedicated Edge
# automation instance, always incognito. One command, idempotent.
#
# Usage: bash scripts/interceptor-automation.sh up|down|status|context
#
# SEAT TRANSPORT (operator 2026-10-17): every Windows-side action runs THROUGH
# powershell.exe. On the WSL seat the distro is NAT-mode (Windows loopback
# 19222/9334 is invisible to Linux netstat/curl) and PATH carries no Windows
# dirs, so PS via the absolute interop path is the only correct vehicle;
# direct /mnt/c exe execs and Linux-side network calls are the broken patterns.
set -euo pipefail

TOOLS_WIN="C:/Users/Lenovo/AppData/Local/hermes/tools/interceptor"
EXT_DIST="$TOOLS_WIN/extension/dist"
PROFILE="$TOOLS_WIN/edge-profile"
EDGE="C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
DAEMON_WIN="$TOOLS_WIN/daemon/interceptor-daemon.exe"
BUN_WIN="C:/Users/Lenovo/.bun/bin/bun.exe"
# NOTE: $CLI must stay UNQUOTED at call sites (two words: bun + exe)
CDP=9334

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    PS_BIN="powershell.exe"
    TOOLS_LOCAL="$TOOLS_WIN"
    ;;
  *)
    PS_BIN="/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
    TOOLS_LOCAL="/mnt/c/Users/Lenovo/AppData/Local/hermes/tools/interceptor"
    ;;
esac
WS_CONTEXT_FILE="$TOOLS_LOCAL/edge-context.txt"

ps() { "$PS_BIN" -NoProfile -Command "$@"; }
# bun CLI through PS: no direct /mnt/c exe exec (seat law above). Context pin
# rides $env: because WSL->Windows env vars do NOT cross the interop boundary.
cli() {
  local pin=""
  [ -f "$WS_CONTEXT_FILE" ] && pin=$(tr -d '\r\n' < "$WS_CONTEXT_FILE")
  ps "\$env:INTERCEPTOR_CONTEXT='$pin'; & '$BUN_WIN' '$TOOLS_WIN/dist/interceptor' $*"
}

edge_pids() {
  ps "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | Where-Object { \$_.CommandLine -match 'interceptor.edge-profile' } | Select-Object -ExpandProperty ProcessId" 2>/dev/null | tr -d '\r'
}

ctx() {
  cli contexts --verbose 2>/dev/null | tr -d '\r' | grep -E "gomcpnagjjlhehnkoobkjgnkbleiooed" | grep -v "a4e0373f" | awk '{print $1}' | head -1 || true
}

daemon_listening() {
  ps "if (netstat -an | Select-String -Quiet '127.0.0.1:19222.*LISTENING') { exit 0 } else { exit 1 }" 2>/dev/null
}

case "${1:-status}" in
  up)
    # 1. persistent daemon (the WAKE LAW). PS 5.1 has no -Environment on
    # Start-Process: set $env: in the same PS session, the child inherits it.
    if ! daemon_listening; then
      echo "daemon: starting (persistent)"
      ps "\$env:INTERCEPTOR_SPIN_WATCHDOG='off'; Start-Process -FilePath '$DAEMON_WIN' -ArgumentList '--standalone' -WindowStyle Hidden" >/dev/null
      sleep 1
    fi
    # 2. Edge automation instance (incognito by launch flag, ONLY our extension)
    # EXTRA_ARGS (space-separated) appends operator-approved flags - e.g. Caido routing:
    #   EXTRA_ARGS="--proxy-server=http://192.168.23.128:8080 --ignore-certificate-errors"
    if [ -z "$(edge_pids)" ]; then
      echo "edge: launching isolated instance${EXTRA_ARGS:+ (extra: $EXTRA_ARGS)}"
      if [ -n "${EXTRA_ARGS:-}" ]; then
        EXTRA_PS=$(printf ",'%s'" $EXTRA_ARGS)
        ps "Start-Process '$EDGE' -ArgumentList @('--user-data-dir=$PROFILE','--load-extension=$EXT_DIST','--disable-extensions-except=$EXT_DIST','--no-first-run','--no-default-browser-check','--remote-debugging-port=$CDP','--incognito','${2:-about:blank}'${EXTRA_PS})" >/dev/null 2>&1
      else
        ps "Start-Process '$EDGE' -ArgumentList '--user-data-dir=$PROFILE','--load-extension=$EXT_DIST','--disable-extensions-except=$EXT_DIST','--no-first-run','--no-default-browser-check','--remote-debugging-port=$CDP','--incognito','${2:-about:blank}'" >/dev/null 2>&1
      fi
    fi
    # 3. wait for the extension context + grant incognito via CDP developerPrivate (idempotent)
    until [ -n "$(ctx)" ]; do sleep 2; done
    C="$(ctx)"; echo "$C" > "$WS_CONTEXT_FILE"
    # HARDENING (operator 2026-10-14): write the CLI context allowlist - the daemon
    # can then NEVER auto-route a call to a stray extension (e.g. the operator's
    # personal Chrome if its extension ever comes back); unpinned calls default
    # to the automation Edge context; unknown contexts are refused outright.
    printf '{"defaultContext":"%s","allowedContexts":["%s"]}\n' "$C" "$C" > "$TOOLS_LOCAL/context-config.json"
    PAGE=$(ps "(Invoke-WebRequest -UseBasicParsing -Method Put -Uri 'http://127.0.0.1:$CDP/json/new?edge://extensions/').Content" 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])" 2>/dev/null || true)
    PAGE="${PAGE%%$'\r'}"
    if [ -n "$PAGE" ]; then
      # JS via temp file: quoting through bash+PS+bun -e is the known failure
      # vector; a written file carries the WS grant snippet verbatim.
      cat > "$TOOLS_LOCAL/.grant-incognito.js" <<EOF
const ws = new WebSocket('ws://127.0.0.1:$CDP/devtools/page/$PAGE');
ws.onopen = () => ws.send(JSON.stringify({id:1, method:'Runtime.evaluate', params:{expression:"chrome.developerPrivate.updateExtensionConfiguration({extensionId:'gomcpnagjjlhehnkoobkjgnkbleiooed', incognitoAccess:true}, ()=>{}) ; 'granted'", awaitPromise:false}}));
ws.onmessage = () => process.exit(0);
setTimeout(()=>process.exit(0), 6000);
EOF
      ps "& '$BUN_WIN' '$TOOLS_WIN/.grant-incognito.js'" >/dev/null 2>&1 || true
      ps "(Invoke-WebRequest -UseBasicParsing -Method Delete -Uri 'http://127.0.0.1:$CDP/json/close/$PAGE').StatusCode" >/dev/null 2>&1 || true
    fi
    echo "context: $C  (export INTERCEPTOR_CONTEXT=$C before CLI calls)"
    echo "READY"
    ;;
  down)
  ps "Get-CimInstance Win32_Process -Filter \"Name='msedge.exe'\" | Where-Object { \$_.CommandLine -match 'interceptor.edge-profile' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force -ErrorAction SilentlyContinue }" >/dev/null 2>&1 || true
  echo "edge automation instance stopped (daemon left running)"
    ;;
  status)
  P=$(edge_pids | head -1); [ -n "$P" ] && echo "edge: RUNNING (pid $P)" || echo "edge: down"
  daemon_listening && echo "daemon: LISTENING" || echo "daemon: down"
  C="$(ctx)"; [ -n "$C" ] && echo "context: $C CONNECTED" || echo "context: none"
    ;;
  context) ctx ;;
  *) echo "usage: $0 up|down|status|context" >&2; exit 2 ;;
esac
