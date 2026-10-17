---
name: interceptor
description: "Use when a target must be browsed as a human: drive a dedicated incognito Chrome via the Interceptor CLI and capture all traffic locally; spider mode composes open/links/act/net."
metadata:
  hermes:
    version: 2
    author: seat
    license: MIT
    tags: [interceptor, browser, spider, dynamic, surface]
    related_skills: [js-discover, js-parser, hunt-core]
---

# Interceptor - real-browser driving + local traffic capture

STATUS: OPERATIONAL.

BROWSER LAW (operator standing rule, hard): NEVER drive the operator's
personal Chrome profiles - they are OUT OF BOUNDS. Every Interceptor run uses
a DEDICATED throwaway Chrome instance: its own --user-data-dir under the tool
tree, launched with --incognito. Logins inside it are minted fresh via the
engagement's own accounts (magic-link etc.), never by riding an existing
signed-in profile. Keeps personal sessions untouched and test isolation exact.

NEVER-CHROME corollary (2026-10-15, hook-ENFORCED): agents never LAUNCH or
CDP-drive Chrome on the seat - no chrome.exe, no --remote-debugging-port, no
connecting to seat 9333/9222. The scope-guard hook hard-denies these. The one
seat browser is the automation EDGE instance (CDP 9334); the generic seat
launcher scripts/browser.sh is Edge-only with no fallback. VM chromium work
runs ON the VM. CONTEXT PINNING: the daemon accepts ANY extension connection -
if the operator's Chrome ever joins (contexts shows 2+), export
INTERCEPTOR_CONTEXT from edge-context.txt before every CLI call and treat a
foreign context as a violation to report, never a target to drive.
KILL-VERIFY-LISTENER: killing a browser's main pid does NOT close its debug
port - the process tree promotes/respawns a child that keeps the listener.
After killing any browser that held a CDP port, verify the LISTENER died
(netstat -ano | grep :<port>) and repeat the kill on the new owner pid until
the port is free; a dead pid with a live listener is an open CDP hole.

WAKE LAW (the operational gotcha): CLI-spawned daemons die before the
extension service worker's WS retry, so `interceptor open` fails with
"no extensions connected" forever. The fix: hold a PERSISTENT standalone
daemon first -
INTERCEPTOR_SPIN_WATCHDOG=off /mnt/c/Users/Lenovo/AppData/Local/hermes/tools/interceptor/daemon/interceptor-daemon.exe --standalone
(run as a background process that stays alive) - the sleeping worker
auto-reconnects to ws://127.0.0.1:19222. LIFECYCLE: the worker falls back
asleep after ~30s idle and drops the socket - before any CLI command, check
`netstat -an | grep 19222` for ESTABLISHED; if down, trigger ANY navigation
in the automation instance (powershell.exe Start-Process '<url>') and poll until
ESTABLISHED returns.

CDP PITFALL: --remote-debugging-port is IGNORED by Chrome 136+ on the default
user-data-dir, and /json/new no longer navigates - do not burn time on CDP
control of an existing profile. EXCEPTION: the dedicated automation instance
has its own --user-data-dir, so its --remote-debugging-port=9334 IS live -
see DEV-TOOLS CONTEXT LAW below.

MULTI-PROFILE PITFALL: chrome:// URLs opened via Start-Process land in the
LAST-ACTIVE profile's window, and each profile has its own extension set -
the card you need may not be in the window you opened. A chrome-extension://
URL in a context without the extension redirects to the Chrome Web Store
("app not found" symptom). "Allow in Incognito" is per-profile; in a
DEDICATED automation instance it can be set PROGRAMMATICALLY via CDP on the
extensions WebUI - navigate a target to edge://extensions (or chrome://),
then Runtime.evaluate
chrome.developerPrivate.updateExtensionConfiguration({extensionId:'<id>',incognitoAccess:true},()=>{})
- idempotent, persists in that user-data-dir. Without the grant,
window_create --incognito returns "no window".

EDGE BRING-UP (the working automation stack): Chrome Stable STRIPS
--load-extension (ignored silently), and forcelist policy needs elevation -
so the automation instance is EDGE, not Chrome: msedge --user-data-dir=<tool
Tree>/edge-profile --load-extension=<extension/dist>
--disable-extensions-except=<same> --incognito --remote-debugging-port=9334.
Edge honors --load-extension; CDP works on its non-default user-data-dir;
NM host registered per-browser (HKCU\Software\Microsoft\Edge\NativeMessagingHosts
-> same host manifest; no admin needed). --disable-extensions-except kills
the junk store extensions Edge auto-installs on first run (ad-blockers
corrupt traffic capture). ONE COMMAND: `bash scripts/interceptor-automation.sh
up|down|status|context` (repo scripts/) brings the whole stack - daemon,
Edge, incognito grant, context pin - and `context` prints the
INTERCEPTOR_CONTEXT id to export before CLI calls (pins the automation
context, never any other).

TAB DISCIPLINE (operator, standing): ONE managed tab per lane - first
`open <url>`, then ALWAYS `open <url> --reuse --group <lane-label>`. Never
plain-open twice - tab/window spam churns the browser and orphans state.
POPUP LAW (operator, standing): before reading or acting on ANY page,
dismiss JS overlays BY CLICKING - cookie banners, newsletter modals, age
gates, onboarding overlays, full-screen backdrops (query visible close
buttons [aria-label*="close" i], .modal [class*="close"], button[class*="dismiss"]
filtered to offsetParent!==null, click each, dispatch Escape, repeat until
0). A modal-blocked page is NOT the page state: never report a gated page
as a finding.
STACK BOOKING: ONE lane on the Edge stack at a time - concurrent lanes on the
shared instance kill each other's sessions, hijack tabs, and trip the
magic-link rate limiter. Serialize lanes; prefer password login in the
automation instance (bot-wall captchas usually pass invisibly in the real
browser) over magic-link relay. If a session wedges into an out-of-scope
OAuth bounce loop, do NOT follow it: CDP Network.clearBrowserCookies on the
automation instance clears the poisoned state; note the dangling server
session for revoke on next login. THE MAIN SESSION COUNTS AS A LANE: an
operator-requested main-session drive while a lane holds the stack is the
same collision - `open --reuse --group <distinct-label>` does NOT protect,
because reuse resolves across the shared extension context and can navigate
ANOTHER lane's managed tab (the auth session survives, the page state does
not). If you must drive while a lane runs, steer the lane instead; never
issue open/reuse yourself.

CONTEXT HARDENING (built + verified): the CLI reads
<install>/context-config.json ({defaultContext, allowedContexts}); the
launcher writes it on every `up`. Unpinned calls default to the automation
context; any context NOT in allowedContexts is refused outright, including
an explicit --context - so the daemon can never auto-route a call to a
stray extension (e.g. the operator's personal browser if its extension
ever returns). Invoke the compiled CLI directly (dist/interceptor.exe,
no bun prefix). When patching the CLI source: `bun build --compile`
artifacts do NOT carry argv[1] as the script path (it is the first
command word) - resolve install-relative files from process.execPath,
with an argv fallback for source runs.

SUBAGENT BRIEF LAW (operator 2026-10-15): any dispatched subagent doing
browsing MUST receive the automation-stack commands IN ITS BRIEF
(automation.sh up, INTERCEPTOR_CONTEXT export, bun CLI path, window
--incognito + --reuse --group). A generic "use browser tools / curl
fallback" brief violates BROWSER LAW and gets driven in the wrong browser -
the skill only loads for agents told to load it. No non-incognito fallback
exists: if the stack fails, report the blocker.

Agent-driven Chrome extension + CLI (Hacker-Valley-Media/Interceptor). Unlike
CDP/headless automation it drives a REAL desktop Chrome: genuine fingerprint,
real codecs, full extension surface - with the isolation of a throwaway
profile. `we drive the website with Interceptor and capture all traffic
locally.`

## Choose the tool

| Situation | Tool |
|---|---|
| Static pages, cheap recon | katana / wigolo fetch |
| Bot wall detected (403/challenge), login-gated surface, dynamic SPA | **Interceptor** |
| Cross-domain chunked JS discovery | **Interceptor -Spider** |

## Wiki

Hub: [[web-moc]] - Primary page: [[static-code-analysis]] - no dedicated
page yet (tool-specific). Anchors: none. This tool has no wiki
technique page of its own; stage one via wiki-stage.py when a
confirmed finding derives from an Interceptor-only capture.

## Scope warning (compensating control)

The VM PATH scope-shim CANNOT see this traffic (real browser on the seat, not
the VM). Compensating control, mandatory: before ANY click execution, verify
every host Interceptor will visit is in the engagement scope.md in-scope list.
The checklist box `every Interceptor-visited host verified in-scope BEFORE
click execution` is hard. The real fix is the nftables egress allowlist
(deferred - see design-scope-shim.md OPEN QUESTIONS Q1).

## Install state

- DONE: repo cloned to `/mnt/c/Users/Lenovo/AppData/Local/hermes/tools/interceptor`,
  bun installed, `bun install` + `bun run build` run; daemon + CLI built.
- LOCAL PATCHES ARE NEVER PUSHABLE: the tool tree is a clone of the VENDOR
  repo (we have no push rights), so any local change (context-config
  allowlist, Edge MV2 extension build) exists ONLY there. Preserve every
  local patch TWICE on change: commit it locally in the tool clone
  (`git -c user.name=seat commit -m "LOCAL (do not push upstream): ..."`)
  AND export the full diff to `setup/interceptor/local-patches.patch` in the
  main repo, then push the main repo - that patch file is the only
  disaster-recoverable copy. Runtime state (edge-profile sessions, daemon
  binary, compiled exe) stays untracked: profiles are disposable engagement
  state, binaries rebuild from the patch.
- Automation-instance bring-up (CRX forcelist auto-install + NM host via HKCU
  registry + ID derivation): follow references/crx-forcelist-setup.md. The
  CRX's real ID must be derived from the packing key and MUST match the
  forcelist + update.xml appid - on mismatch Chrome silently drops the
  install with no error anywhere.
- One-time manual toggle in the automation instance (user-only):
  chrome://extensions -> Interceptor -> Details -> "Allow in Incognito".
  Persists in that user-data-dir; without it, window_create --incognito
  returns "no window".

## CLI pattern (seat-side, full paths; prefer the compiled exe - bun prefix
## only when running the unbuilt script form)

    CLI=/mnt/c/Users/Lenovo/AppData/Local/hermes/tools/interceptor/dist/interceptor
    export INTERCEPTOR_CONTEXT=$(cat /mnt/c/Users/Lenovo/AppData/Local/hermes/tools/interceptor/edge-context.txt)
    /mnt/c/Users/Lenovo/.bun/bin/bun.exe "$CLI" status
    /mnt/c/Users/Lenovo/.bun/bin/bun.exe "$CLI" window new "https://<in-scope-host>" --incognito
    /mnt/c/Users/Lenovo/.bun/bin/bun.exe "$CLI" open "https://<in-scope-host>"
    /mnt/c/Users/Lenovo/.bun/bin/bun.exe "$CLI" net log             (drain captured HAR; NO `net start` - subcommands are log|clear|headers)
    /mnt/c/Users/Lenovo/.bun/bin/bun.exe "$CLI" links              (all links on page)
    /mnt/c/Users/Lenovo/.bun/bin/bun.exe "$CLI" act <ref>          (per control, tree refs)
    /mnt/c/Users/Lenovo/.bun/bin/bun.exe "$CLI" eval --main <js>   (in-page JS; fetch-patch)
    INTERCEPTOR_PAGE=<id> bash scripts/interceptor-cdp.sh eval '<js>'   (CDP on a CHOSEN tab)

CAPTURE CAVEAT: passive `net log` misses APQ POST bodies (beacons only);
recover bodies via eval --main fetch-patch - override window.fetch to record
OR REWRITE outgoing request bodies. The rewrite form is the in-flight
TAMPERING lever: mutations fire from genuine browser context and beat any
curl-fingerprint wall (seat replays of context-gated op classes ISE; the same
bodies through the page succeed). Full page loads can beat the patch - fire
captures from SPA-internal navigation.
APQ HASH LAW: persisted-query hashes are computed CLIENT-SIDE at runtime by
the minified Apollo link - they are NOT strings you can grep out of bundles
(mine all you want, zero sha256 hits). When you need a mutation body + hash,
CLICK the real control in the UI with a CDP netwatch running on that tab and
harvest the POST from the JSONL; replay that body verbatim (variables
swapped) instead of hunting for a registry.
TWO-TIER PATCH LAW: an in-page fetch wrapper (eval --main) survives SPA
CLICKS but dies on any full URL load; a CDP Fetch.enable requestStage:Response
interception over the automation instance's debug port patches response
bodies before the framework sees them AND survives full navigations (python
over the CDP WebSocket needs suppress_origin=True or the handshake 403s).
Pick per probe: request tampering = in-page wrapper on SPA nav; response
forgery (client-trust probing) = CDP response-stage.

## DEV-TOOLS CONTEXT LAW (operator 2026-10-14)

Every Interceptor investigation runs the CDP DevTools channel IN PARALLEL
with the extension verbs. The automation instance is launched by
`scripts/interceptor-automation.sh up` with `--remote-debugging-port=9334`
on its own user-data-dir, so CDP works there (the Chrome 136 default-profile
ignore does NOT apply). Drive it via `scripts/interceptor-cdp.sh`:

    bash scripts/interceptor-cdp.sh targets
    bash scripts/interceptor-cdp.sh eval '<js>'
    bash scripts/interceptor-cdp.sh dom > page.html
    bash scripts/interceptor-cdp.sh netwatch <out.jsonl> [secs]

Ground rules:
- netwatch is the BODY recovery channel: Network events + getResponseBody
  carry POST bodies the passive `net log` misses. Run it during every
  act/eval sequence, then reconcile against the drained HAR.
- Console + exceptions are a free error oracle: grep the netwatch JSONL
  after each mutation.
- Cross-check rule: HAR vs CDP trace disagree -> CDP is ground truth for
  bodies/status. Extension `net log` capture is CONTEXT-SCOPED: traffic from
  tabs outside the pinned context can be entirely absent from a drained
  HAR that otherwise looks healthy - never conclude "no such requests"
  from the HAR alone; the CDP netwatch JSONL is the complete record.
  Extension `eval --main` stays the TAMPERING lever; CDP
  Runtime.evaluate is the read/context lever.
- CDP attaches, it does not drive: navigation stays with extension verbs
  (open/window new). /json/new needs PUT on modern Edge.
- netwatch outfile: full Windows path (C:/...) - bun.exe drops POSIX paths
  at C:\ root.
- OOS MAIN-PAGE LAW: link/redirect drift on the MAIN test tab -> observe
  first, recover after. Run `bash scripts/interceptor-cdp.sh oos
  <eng>/scope.md`: it watches the drifted path for 10s (logging the
  redirect chain; requests land in netwatch), and only if it stayed
  out-of-scope navigates the tab back to the first in-scope host. If the
  path returned in-scope by itself, it is kept. Test-opened tabs are
  never touched.

- Derive CDP target ids programmatically (curl /json -> filter), never
  hand-type a 32-hex id into a ws URL - one wrong character silently
  points the connection at nothing.
- PARALLEL-LANE TAB PINNING: when the operator authorizes concurrent lanes
  on the one automation instance (overriding STACK BOOKING), each lane opens
  its OWN tab (interceptor open) and pins every netwatch/eval to that tab
  with INTERCEPTOR_PAGE=<own id>, taken from `targets` and matched by URL.
  Never reuse a tab id you did not create in your lane, and never trust the
  page_id first-tab default in a multi-tab session - it silently attaches to
  whichever tab sorts first, so lane captures interleave and UI actions fight
  over one page. Discard as contaminated any capture taken on a foreign tab.

OPERATOR VISIBILITY (hard): everything run through the console channel must
be visible to the operator live - interceptor-cdp.sh echoes each eval as
`[cdp] > <expr>` with its result on stdout/stderr, and netwatch streams
`[console:*]` lines to the terminal pane as they fire. Never run silent
JS in the automation instance; if a probe cannot echo, it does not run.

ACTIVE-TAB LAW (operator 2026-10-15): blank/parked tabs lead nowhere - the
operator must always be LOOKING AT the tab that is doing something. Wired
into interceptor-cdp.sh: every eval/dom/netwatch call first activates its
target tab (Browser.getWindowForTarget -> setWindowBounds normal ->
Page.bringToFront), so the working tab is the shown tab. `clean` verb closes
parked about:blank/edge:// tabs. Open tabs with a real URL, not blanks; under
multi-lane contention each lane pins its own tab (foreground may flip between
active lanes - that is two things happening, not zero).
Visibility is the TERMINAL ECHO LAYER ONLY - the operator declined a real
DevTools frontend tab/window on the automation instance (opening one via
PUT /json/new + devtools://inspector.html works technically, extension
`open` refuses devtools://): do not build or open one.

## Spider = composed loop (the upstream -Spider mode is a fork feature not in
## this build; compose it from verbs)

For each in-scope URL: open -> links -> enqueue unvisited ->
act click each control (buttons/tabs) -> net captures every request/response
to HAR -> pull all .js URLs from the HAR into the js-discover corpus
(raw/external/). Cross-domain chunks ARE captured (the network log sees
everything the real session loads). Record every visited host in the run
manifest + _requests.md.

## Auth note

Sessions are minted INSIDE the automation instance with the engagement's own
accounts (magic-link typed via act refs, link pulled from the pool inbox).
identities.md still owns the credentials; the instance only holds the
resulting cookies. Teardown = UI logout-all + verify; the whole user-data-dir
can be deleted afterwards for a clean slate.

## Contract with js-discover

- Corpus owner is js-discover; Interceptor output is INGESTED into its tree.
- Every visited host also appended to `_requests.md`.
- Findings never leave without the G1 proof gate (this tool produces surface,
  not findings).
