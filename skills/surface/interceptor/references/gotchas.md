---
title: Interceptor gotchas (why-detail)
type: skill-reference
tags: [interceptor, gotchas, reference]
date_created: "2026-10-27"
---

# Gotchas and why-detail (moved out of SKILL.md, 2026-10-27 restructure)

Every hard rule lives in SKILL.md; this file carries the history, the
diagnosis detail, and the patching notes behind those rules.

## Why the automation instance is EDGE, not Chrome

Chrome Stable STRIPS `--load-extension` (ignored silently), and forcelist
policy needs elevation - so the automation instance is Edge:
`msedge --user-data-dir=<tool>/edge-profile --load-extension=<extension/dist>
--disable-extensions-except=<same> --incognito --remote-debugging-port=9334`.
Edge honors `--load-extension`; CDP works on its non-default user-data-dir;
NM host registered per-browser (HKCU `...\Edge\NativeMessagingHosts` ->
same host manifest, no admin). `--disable-extensions-except` kills the junk
store extensions Edge auto-installs on first run (ad-blockers corrupt
traffic capture). One command brings it all up:
`bash scripts/interceptor-automation.sh up|down|status|context`.

## Chrome 136 CDP pitfall

`--remote-debugging-port` is IGNORED by Chrome 136+ on the default
user-data-dir, and `/json/new` no longer navigates - do not burn time on CDP
control of an existing profile. EXCEPTION: the automation instance has its
own user-data-dir, so its port 9334 IS live (the DEV-TOOLS CONTEXT law rides
on this).

## Multi-profile pitfalls

chrome:// URLs opened via Start-Process land in the LAST-ACTIVE profile's
window, and each profile has its own extension set - the card you need may
not be in the window you opened. A chrome-extension:// URL in a context
without the extension redirects to the Chrome Web Store ("app not found"
symptom). "Allow in Incognito" is per-profile; in a DEDICATED automation
instance it can be set PROGRAMMATICALLY via CDP on the extensions WebUI -
navigate to edge://extensions, then Runtime.evaluate:

```js
chrome.developerPrivate.updateExtensionConfiguration({extensionId:'<id>',incognitoAccess:true},()=>{})
```

Idempotent, persists in that user-data-dir. Without the grant,
`window_create --incognito` returns "no window".

## WAKE LAW detail (daemon lifecycle)

CLI-spawned daemons die before the extension service worker's WS retry
("no extensions connected" forever). The persistent standalone daemon
launcher (Start-Process detach, survives the shell):

```powershell
powershell.exe -NoProfile -Command "$env:INTERCEPTOR_SPIN_WATCHDOG='off'; Start-Process -FilePath 'C:/Users/Lenovo/AppData/Local/hermes/tools/interceptor/daemon/interceptor-daemon.exe' -ArgumentList '--standalone' -WindowStyle Hidden"
```

The sleeping worker auto-reconnects to ws://127.0.0.1:19222. WSL->Windows
env does NOT cross interop - the env var must be set INSIDE the PS command.
`interceptor-automation.sh up` handles this; manual form is the fallback.

## CLI-source patching notes

`bun build --compile` artifacts do NOT carry argv[1] as the script path (it
is the first command word) - resolve install-relative files from
`process.execPath`, with an argv fallback for source runs. Local patches are
never pushable (vendor clone, no rights): commit locally in the clone
(`git -c user.name=seat commit -m "LOCAL (do not push upstream): ..."`)
AND export the full diff to `setup/interceptor/local-patches.patch` in the
main repo - that patch file is the only disaster-recoverable copy.

## Deferred

The nftables egress allowlist (the real fix for the seat-side scope
compensating control) is deferred; the donor-side design notes did not
travel with the port.
