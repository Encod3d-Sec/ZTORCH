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

STATUS: OPERATIONAL. History/why detail lives in `references/gotchas.md`; every
HARD law is below - if it has a law name, it is binding.

## Lane quick path (a dispatched subagent starts here, in this order)

SUBAGENT BRIEF LAW (operator 2026-10-15): any dispatched subagent doing
browsing MUST have these steps IN ITS BRIEF - a generic "use browser tools /
curl fallback" brief violates BROWSER LAW and gets driven in the wrong
browser. No non-incognito fallback exists: if the stack fails, report the
blocker.

```sh
# 1. bring the stack up (daemon + automation Edge + context pin; idempotent)
bash scripts/interceptor-automation.sh up
CTX=$(bash scripts/interceptor-automation.sh context)   # or cat <tool>/edge-context.txt

# 2. wake check: worker asleep => ESTABLISHED down. Trigger any navigation,
#    poll `netstat -an | Select-String 19222` until ESTABLISHED (WAKE LAW)
# 3. ONE managed tab per lane, then always reuse+group
#    (window new --incognito only for a fresh window; needs the incognito grant)
# 4. EVERY CLI call goes THROUGH powershell.exe with the context pin inside:
PS=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
BUN=C:/Users/Lenovo/.bun/bin/bun.exe
CLI=C:/Users/Lenovo/AppData/Local/hermes/tools/interceptor/dist/interceptor
$PS -NoProfile -Command "`$env:INTERCEPTOR_CONTEXT='$CTX'; & '$BUN' '$CLI' open 'https://<in-scope-host>' --reuse --group <lane-label>"

# 5. pin YOUR tab for every cdp call (id from `targets`, matched by URL)
bash scripts/interceptor-cdp.sh targets
INTERCEPTOR_PAGE=<own-tab-id> bash scripts/interceptor-cdp.sh netwatch <out.jsonl> 60

# 6. before reading/acting on any page: dismiss overlays BY CLICKING (POPUP LAW)
# 7. capture PAIR: netwatch (bodies, ground truth) + `net log` (HAR), reconcile
# 8. stay in scope: verify every host you will visit is in scope.md BEFORE clicks
```

One lane on the Edge stack at a time (STACK BOOKING) unless the operator
authorized parallel lanes - then tab pinning (step 5) is mandatory.

## Hard laws

**BROWSER LAW (operator standing, hard):** NEVER drive the operator's
personal Chrome profiles - OUT OF BOUNDS. Every run uses the DEDICATED
automation instance (own `--user-data-dir`, incognito); logins are minted
fresh via the engagement's own accounts, never by riding a signed-in profile.
**NEVER-CHROME corollary (2026-10-15, hook-ENFORCED):** agents never LAUNCH
or CDP-drive Chrome on the seat (no chrome.exe, no `--remote-debugging-port`,
no seat 9333/9222) - scope-guard hard-denies. The one seat browser is the
automation EDGE instance (CDP 9334); `scripts/browser.sh` is Edge-only, no
fallback. VM chromium work runs ON THE VM. **Context pinning:** the daemon
accepts ANY extension connection - export `INTERCEPTOR_CONTEXT` before every
CLI call; a foreign context (contexts shows 2+) is a violation to REPORT,
never a target to drive.

**STACK BOOKING:** ONE lane on the Edge stack at a time - concurrent lanes
kill each other's sessions, hijack tabs, and trip the magic-link rate
limiter. Prefer password login in the automation instance (bot-wall captchas
usually pass invisibly) over magic-link relay. Out-of-scope OAuth bounce
loop: do NOT follow it; CDP `Network.clearBrowserCookies` clears the poisoned
state, note the dangling server session for revoke. **THE MAIN SESSION
COUNTS AS A LANE:** an operator-requested main-session drive while a lane
holds the stack is the same collision - `--reuse --group <distinct>` does
NOT protect (reuse resolves across the shared context and can navigate
ANOTHER lane's tab). Steer the lane instead; never issue open/reuse yourself.

**PARALLEL-LANE TAB PINNING:** when the operator authorizes concurrent lanes
(each overriding STACK BOOKING), each lane opens its OWN tab and pins every
netwatch/eval with `INTERCEPTOR_PAGE=<own id>` (from `targets`, matched by
URL). Never reuse a tab id you did not create; never trust the first-tab
default in a multi-tab session - it silently attaches to whichever tab sorts
first, so captures interleave and UI actions fight over one page. Discard as
contaminated any capture taken on a foreign tab. `interceptor-cdp.sh` refuses
multi-tab sessions without `INTERCEPTOR_PAGE` (exit 4).

**TAB DISCIPLINE (operator, standing):** ONE managed tab per lane - first
`open <url>`, then ALWAYS `open <url> --reuse --group <lane-label>`. Never
plain-open twice; tab spam churns the browser and orphans state.
**POPUP LAW (operator, standing):** before reading or acting on ANY page,
dismiss JS overlays BY CLICKING - cookie banners, modals, age gates,
onboarding overlays, full-screen backdrops (query visible close buttons
`[aria-label*="close" i]`, `.modal [class*="close"]`,
`button[class*="dismiss"]` filtered to `offsetParent!==null`, click each,
dispatch Escape, repeat until 0). A modal-blocked page is NOT the page state:
never report a gated page as a finding.

**WAKE LAW:** CLI-spawned daemons die before the extension service worker's
WS retry, so commands fail with "no extensions connected" forever. The
persistent standalone daemon is held by `interceptor-automation.sh up`
(Start-Process detach, PS 5.1-safe env; the env var must be set INSIDE the
PS command - WSL->Windows env does NOT cross interop). The worker falls
asleep after ~30s idle: before any CLI command check ESTABLISHED on 19222
via PS netstat; if down, trigger any navigation and poll until it returns.

**ACTIVE-TAB LAW (operator 2026-10-15) + OPERATOR VISIBILITY (hard):** the
operator must always be LOOKING AT the tab that is doing something -
`interceptor-cdp.sh` activates the target tab before every eval/dom/netwatch
(`clean` closes parked blanks; open real URLs, not blanks). Everything
through the console channel echoes live (`[cdp] > <expr>` results,
`[console:*]` netwatch lines). Never run silent JS; a probe that cannot echo
does not run. Visibility is the TERMINAL ECHO LAYER ONLY - the operator
declined a DevTools frontend window: do not build or open one.

**KILL-VERIFY-LISTENER:** killing a browser's main pid does NOT close its
debug port - the tree promotes/respawns a child holding the listener. After
killing any CDP-port browser, verify the LISTENER died
(`netstat -ano | Select-String :<port>` via PS) and repeat the kill on the
new owner pid until the port is free. A dead pid with a live listener is an
open CDP hole. Linux netstat cannot see Windows loopback - route through
powershell.exe.

**CONTEXT HARDENING (built + verified):** the CLI reads
`<install>/context-config.json` (`{defaultContext, allowedContexts}`);
unpinned calls default to the automation context, any context NOT in
allowedContexts is refused outright - the daemon can never auto-route a call
to a stray extension. Invoke the compiled CLI directly (`dist/interceptor.exe`,
no bun prefix). (CLI-source patching note: `references/gotchas.md`.)

**Scope warning (compensating control):** the VM PATH scope-shim CANNOT see
this traffic. Mandatory: before ANY click execution, verify every host
Interceptor will visit is in the engagement scope.md in-scope list. The
checklist box `every Interceptor-visited host verified in-scope BEFORE click
execution` is hard.

## Choose the tool

| Situation | Tool |
|---|---|
| Static pages, cheap recon | katana / wigolo fetch |
| Bot wall detected (403/challenge), login-gated surface, dynamic SPA | **Interceptor** |
| Cross-domain chunked JS discovery | **Interceptor -Spider** |

## Capture levers (CLI + CDP)

All CLI calls use the powershell.exe routing from the quick path. Verbs:
`status`, `window new <url> --incognito`, `open <url> [--reuse --group <g>]`,
`net log` (drain HAR; NO `net start` - subcommands are log|clear|headers),
`links`, `act <ref>` (per control, tree refs), `eval --main <js>` (in-page
JS; the fetch-patch lever).

CAPTURE CAVEAT: passive `net log` misses APQ POST bodies (beacons only);
recover bodies via `eval --main` fetch-patch - override window.fetch to
record OR REWRITE outgoing request bodies. The rewrite form is the in-flight
TAMPERING lever: mutations fire from genuine browser context and beat any
curl-fingerprint wall (seat replays of context-gated op classes ISE; the
same bodies through the page succeed). Full page loads can beat the patch -
fire captures from SPA-internal navigation.

APQ HASH LAW: persisted-query hashes are computed CLIENT-SIDE at runtime by
the minified Apollo link - NOT strings you can grep out of bundles. When you
need a mutation body + hash, CLICK the real control with a CDP netwatch
running on that tab and harvest the POST from the JSONL; replay that body
verbatim (variables swapped).

TWO-TIER PATCH LAW: an in-page fetch wrapper (eval --main) survives SPA
CLICKS but dies on any full URL load; a CDP `Fetch.enable`
requestStage:Response interception patches response bodies before the
framework sees them AND survives full navigations (python over the CDP
WebSocket needs `suppress_origin=True` or the handshake 403s). Pick per
probe: request tampering = in-page wrapper on SPA nav; response forgery
(client-trust probing) = CDP response-stage.

## DEV-TOOLS CONTEXT LAW (operator 2026-10-14)

Every investigation runs the CDP DevTools channel IN PARALLEL with the
extension verbs. The automation instance is launched with
`--remote-debugging-port=9334` on its own user-data-dir, so CDP works there
(the Chrome 136 default-profile ignore does NOT apply). Drive it via
`scripts/interceptor-cdp.sh`:

```sh
bash scripts/interceptor-cdp.sh targets
INTERCEPTOR_PAGE=<id> bash scripts/interceptor-cdp.sh eval '<js>'
INTERCEPTOR_PAGE=<id> bash scripts/interceptor-cdp.sh dom > page.html
INTERCEPTOR_PAGE=<id> bash scripts/interceptor-cdp.sh netwatch <out.jsonl> [secs]
```

- netwatch is the BODY recovery channel (Network events + getResponseBody).
  Run it during every act/eval sequence, then reconcile against the HAR.
- Console + exceptions are a free error oracle: grep the netwatch JSONL
  after each mutation.
- Cross-check rule: HAR vs CDP disagree -> CDP is ground truth for
  bodies/status. `net log` is CONTEXT-SCOPED: never conclude "no such
  requests" from the HAR alone. `eval --main` stays the TAMPERING lever;
  CDP Runtime.evaluate is the read/context lever.
- CDP attaches, it does not drive: navigation stays with extension verbs.
  `/json/new` needs PUT on modern Edge. Derive target ids programmatically
  (curl /json -> filter), never hand-type a 32-hex id.
- netwatch outfile: full Windows path (`C:/...`) - bun.exe drops POSIX
  paths at `C:\` root.
- OOS MAIN-PAGE LAW: link/redirect drift on the MAIN test tab -> observe
  first, recover after. `interceptor-cdp.sh oos <eng>/scope.md` watches the
  drifted path 10s (logging the chain), and only if it stayed out-of-scope
  navigates back to the first in-scope host. Test-opened tabs never touched.

## Spider = composed loop (upstream -Spider is a fork feature; compose it)

For each in-scope URL: open -> links -> enqueue unvisited -> act click each
control -> net captures every request/response to HAR -> pull all .js URLs
from the HAR into the js-discover corpus (`raw/external/`). Cross-domain
chunks ARE captured. Record every visited host in the run manifest +
`_requests.md`.

## Auth note

Sessions are minted INSIDE the automation instance with the engagement's own
accounts (magic-link typed via act refs, link from the pool inbox).
identities.md owns the credentials; the instance only holds resulting
cookies. Teardown = UI logout-all + verify; the user-data-dir is disposable.

## Contract with js-discover

- Corpus owner is js-discover; Interceptor output is INGESTED into its tree.
- Every visited host also appended to `_requests.md`.
- Findings never leave without the G1 proof gate (this tool produces
  surface, not findings).

## Install state

- Tool tree: `/mnt/c/Users/Lenovo/AppData/Local/hermes/tools/interceptor`
  (vendor clone; bun build done). Local patches are NEVER PUSHABLE - commit
  locally in the clone AND export the diff to
  `setup/interceptor/local-patches.patch` (the only disaster-recoverable
  copy). Runtime state stays untracked.
- Automation bring-up (CRX forcelist + NM host + ID derivation):
  `references/crx-forcelist-setup.md` (ID mismatch = silent drop, no error).
  One-time user-only toggle: extension Details -> "Allow in Incognito"
  (CDP-settable, see `references/gotchas.md`).
- Why Edge not Chrome, Chrome 136 CDP ignore, multi-profile pitfalls, CLI
  patching notes: `references/gotchas.md`.

## Wiki

Hub: [[web-moc]] - Primary page: [[static-code-analysis]] - no dedicated
page yet (tool-specific). Anchors: none. Stage one via wiki-stage.py when a
confirmed finding derives from an Interceptor-only capture.
