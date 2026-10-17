#!/usr/bin/env bash
# interceptor-cdp.sh - DevTools (CDP) parallel context channel for the
# isolated Edge interceptor instance. CDP=9334 works there because the
# instance has its own --user-data-dir (the Chrome 136+ default-profile
# ignore does not apply). Extension verbs stay the driver; this is the
# EVIDENCE channel: POST bodies, console/exceptions, DOM, HAR cross-check.
#
# Usage:
#   bash scripts/interceptor-cdp.sh targets
#   bash scripts/interceptor-cdp.sh eval 'document.title'
#   bash scripts/interceptor-cdp.sh dom > page.html
#   bash scripts/interceptor-cdp.sh netwatch <out.jsonl> [seconds=60]
#   bash scripts/interceptor-cdp.sh oos <scope.md>     (if MAIN test tab
#                                                       drifted OOS: navigate
#                                                       it back in-scope)
# NOTE: netwatch outfile MUST be a full Windows path (C:/...) - bun.exe is
# native and drops POSIX-style paths at C:\ root.
set -euo pipefail

CDP="${INTERCEPTOR_CDP:-9334}"
BUN="C:/Users/Lenovo/.bun/bin/bun.exe"
export CDP

# first real page target in the automation instance (skips devtools/edge:// internal)
page_id() {
  curl -s "http://127.0.0.1:$CDP/json" | python3 -c "
import json,sys
for t in json.load(sys.stdin):
    if t.get('type')=='page' and not t.get('url','').startswith(('devtools:','edge://','chrome://')):
        print(t['id']); break
" | tr -d '\r'
}

case "${1:-targets}" in
  targets)
    curl -s "http://127.0.0.1:$CDP/json" | python3 -c "
import json,sys
for t in json.load(sys.stdin):
    print(t.get('type'), t.get('id'), t.get('url','')[:100])
"
    ;;
  eval|dom|netwatch)
    PAGE="${INTERCEPTOR_PAGE:-$(page_id)}"
    [ -n "$PAGE" ] || { echo "no page target on 127.0.0.1:$CDP - stack up?" >&2; exit 1; }
    # ACTIVE-TAB LAW (operator 2026-10-15): the operator watches the foreground tab -
    # bring our target to the front before driving it, so what's "going on" is always
    # visible. Blank parked tabs lead nowhere; the working tab must be the shown tab.
    # Two layers: CDP tab activation + window restore (a minimized/multi-window Edge
    # keeps every tab "hidden" no matter what bringToFront alone says).
    C:/Users/Lenovo/.bun/bin/bun.exe -e "
const ws = new WebSocket('ws://127.0.0.1:$CDP/devtools/page/$PAGE');
let id = 0; const send = (m,p={}) => ws.send(JSON.stringify({id:++id,method:m,params:p}));
let wid = null;
ws.onopen = () => { send('Browser.getWindowForTarget', {targetId: '$PAGE'}); };
ws.onmessage = (m) => {
  const d = JSON.parse(m.data);
  if (d.result && d.result.windowId !== undefined && wid === null) {
    wid = d.result.windowId;
    send('Browser.setWindowBounds', {windowId: wid, bounds: {windowState: 'normal'}});
    send('Page.bringToFront');
  }
  setTimeout(()=>process.exit(0), 400);
};
setTimeout(()=>process.exit(0), 3000);" >/dev/null 2>&1 || true
# NOTE: under multi-lane contention a parallel driver can flip the foreground right
# back - each lane pins ITS tab (PARALLEL-LANE TAB PINNING law in the skill).
    export PAGE MODE="$1" EXPR="${2:-}" OUT="${2:-cdp.jsonl}" SECS="${3:-60}"
    exec "$BUN" -e '
const {CDP, PAGE, MODE, EXPR, OUT, SECS} = process.env;
const ws = new WebSocket(`ws://127.0.0.1:${CDP}/devtools/page/${PAGE}`);
const fs = require("fs");
let id = 0;
const refById = {};
const send = (m, p = {}) => { ws.send(JSON.stringify({id: ++id, method: m, params: p})); };
const sendRef = (m, p, ref) => { ws.send(JSON.stringify({id: ++id, method: m, params: p})); refById[id] = ref; };
const events = [];
const flush = () => { if (events.length) { fs.appendFileSync(OUT, events.splice(0).map(e => JSON.stringify(e)).join("\n") + "\n"); } };
const done = () => { flush(); try { ws.close(); } catch {} process.exit(0); };
ws.onopen = () => {
  if (MODE === "netwatch") {
    send("Network.enable"); send("Runtime.enable");
    console.error(`netwatch -> ${OUT} for ${SECS}s (page ${PAGE})`);
    setInterval(flush, 5000);
    setTimeout(done, Number(SECS) * 1000);
  } else if (MODE === "dom") {
    send("Runtime.evaluate", {expression: "document.documentElement.outerHTML", returnByValue: true});
  } else {
    console.error(`[cdp] > ${EXPR.slice(0, 300)}`);
    send("Runtime.evaluate", {expression: EXPR, returnByValue: true, awaitPromise: true});
  }
};
ws.onmessage = (m) => {
  const d = JSON.parse(m.data);
  if (d.id) { // command reply
    if (MODE !== "netwatch") {
      const r = d.result || {};
      if (MODE === "dom") process.stdout.write(r.result ? r.result.value : "");
      else console.log(JSON.stringify(r.result ?? r.exceptionDetails ?? r, null, 0));
      process.exit(0);
    }
    if (d.result && d.result.body !== undefined) { // getResponseBody reply
      const body = d.result.body || "";
      events.push({ts: Date.now(), kind: "body", ref: refById[d.id], base64: !!d.result.base64Encoded, len: body.length, body: body.length <= 65536 ? body : body.slice(0, 65536) + "...[TRUNC]"});
    }
    return;
  }
  const p = d.params || {};
  if (d.method === "Network.requestWillBeSent")
    events.push({ts: Date.now(), kind: "req", id: p.requestId, method: p.request.method, url: p.request.url, post: p.request.postData ? String(p.request.postData).slice(0, 65536) : undefined});
  else if (d.method === "Network.responseReceived")
    events.push({ts: Date.now(), kind: "res", id: p.requestId, status: p.response.status, mime: p.response.mimeType, url: p.response.url});
  else if (d.method === "Network.loadingFinished")
    sendRef("Network.getResponseBody", {requestId: p.requestId}, p.requestId);
  else if (d.method === "Runtime.consoleAPICalled") {
    const text = (p.args || []).map(a => a.value ?? a.description).join(" ").slice(0, 2000);
    console.error(`[console:${p.type}] ${text}`); // live operator mirror in terminal pane
    events.push({ts: Date.now(), kind: "console", level: p.type, args: text});
  }
  else if (d.method === "Runtime.exceptionThrown") {
    const detail = JSON.stringify(p.exceptionDetails).slice(0, 4000);
    console.error(`[console:exception] ${detail}`);
    events.push({ts: Date.now(), kind: "exception", detail});
  }
};
ws.onerror = () => { console.error("CDP ws error - stack up? (interceptor-automation.sh up)"); process.exit(1); };
'
    ;;
  clean)
    # ACTIVE-TAB LAW sweeper: close parked blank/internal tabs so the tab bar (and the
    # operator's eye) holds only live working tabs.
    python3 - "$CDP" <<'PYEOF'
import json, sys, urllib.request
cdp = sys.argv[1]
n = 0
for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{cdp}/json")):
    u = t.get("url", "")
    if t.get("type") == "page" and (u in ("about:blank", "") or u.startswith(("edge://", "chrome://"))):
        urllib.request.urlopen(urllib.request.Request(
            f"http://127.0.0.1:{cdp}/json/close/{t['id']}", method="DELETE"))
        print(f"[clean] closed {u[:50]}")
        n += 1
print(f"[clean] {n} blank/internal tab(s) closed")
PYEOF
    ;;
  oos)
    # OOS MAIN-PAGE LAW: if the MAIN test tab (first non-internal page) drifted
    # out-of-scope via redirect or same-tab link: observe (netwatch caught where
    # it led + requests), then NAVIGATE IT BACK to the first in-scope host.
    # Other tabs (test-opened redirects etc.) are NOT touched.
    SCOPE_="${2:?usage: oos <scope.md>}"
    python3 - "$CDP" "$SCOPE_" <<'PYEOF'
import json, sys, urllib.parse, urllib.request
cdp, scope = sys.argv[1], sys.argv[2]
ins = []
grab = False
for ln in open(scope, encoding="utf-8"):
    if ln.startswith("## "): grab = ln.lower().startswith("## in scope")
    elif grab and ln.strip().startswith("- "):
        host = ln.strip()[2:].strip().lstrip("`").split()[0]
        if host and not host.startswith("#"): ins.append(host)
def in_scope(h): return any(h == s or h.endswith("." + s) for s in ins)
main = None
for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{cdp}/json")):
    if t.get("type") == "page" and t.get("url", "").startswith(("http://", "https://")):
        main = t; break
if not main:
    print("[oos] no main page tab found - nothing open?"); sys.exit(0)
def host_of(u): return urllib.parse.urlparse(u).hostname or ""
def url_of(tid):
    for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{cdp}/json")):
        if t.get("id") == tid: return t.get("url", "")
    return ""
if in_scope(host_of(main["url"])):
    print(f"[oos] main page in-scope ({host_of(main['url'])}) - nothing to do"); sys.exit(0)
print(f"[oos] MAIN PAGE DRIFTED OOS: {host_of(main['url'])} <- {main['url'][:90]}")
print("[oos] observing where the path leads for 10s (requests land in netwatch)...")
seen = main["url"]
import time
for _ in range(5):  # 5 x 2s = 10s observation window, log the redirect chain
    time.sleep(2)
    u = url_of(main["id"])
    if u and u != seen:
        print(f"[oos]   -> {host_of(u)}  {u[:90]}")
        seen = u
if in_scope(host_of(seen)):
    print(f"[oos] path returned in-scope by itself ({host_of(seen)}) - keeping it")
    sys.exit(0)
back = f"https://{ins[0]}/"
print(f"[oos] still OOS ({host_of(seen)}) after 10s - closing the path, back to {back}")
# Page.navigate via WS (curl cannot); minimal bun one-liner, same pattern as eval
import subprocess
subprocess.run(["C:/Users/Lenovo/.bun/bin/bun.exe", "-e", f"""
const ws = new WebSocket('ws://127.0.0.1:{cdp}/devtools/page/{main['id']}');
ws.onopen = () => ws.send(JSON.stringify({{id:1, method:'Page.navigate', params:{{url:'{back}'}}}}));
ws.onmessage = () => process.exit(0);
setTimeout(() => process.exit(0), 5000);
"""], capture_output=True)
print("[oos] back on in-scope ground")
PYEOF
    ;;
  *) echo "usage: $0 targets|eval '<js>'|dom|netwatch <out.jsonl> [secs]|oos <scope.md>" >&2; exit 2 ;;
esac
