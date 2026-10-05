---
title: "Electron Desktop App Attacks"
type: technique
tags: [web, desktop, electron, client-side, ipc]
phase: exploitation
date_created: 2026-10-05
date_updated: 2026-10-05
sources: [github-usestrix-strix]
---

## What it is

Attack surface specific to Electron desktop applications: the preload bridge between the
privileged main process and the renderer, IPC handler authorization, navigation and URL
policy, and update pipelines. The recurring theme: a security-relevant-looking mechanism
(preload config, `will-navigate` handler, registered IPC handler list) that does not enforce
what it appears to enforce.

Engine-separation rule first: do not apply Electron conclusions to NW.js, CEF, Tauri, or
Wails without mapping that framework separately; their bridge, sandbox, update, and process
APIs differ.

## Preload survives navigation

Web preferences belong to a `webContents`; navigation does not automatically turn a privileged
window into an ordinary browser tab. A configured preload can run for newly loaded documents
and expose its bridge to content that was never intended to receive it. The single most-missed
Electron fact: test whether remote or navigated content reaches the preload bridge, not just
the initially loaded page.

## `will-navigate` is not an allowlist

`will-navigate` does not cover every programmatic navigation, so the handler's presence is not
complete enforcement. Treat it as one signal; drive navigation through every other channel
(window.location, target=_blank without noopener handling, iframes, webview tags,
window.open from the renderer) and observe which paths the policy misses.

## URL policy mechanics

Where the app validates URLs before loading them:

- Parse with `URL` and compare explicit `protocol`, `origin`, `host`, `port`, `path`.
- Never accept prefix checks such as `startsWith("https://trusted.example")`; they fall to
  `https://trusted.example.attacker.com` and embedded-basic-auth forms.
- One canonical policy must apply across initial loads, redirects, frames, popups,
  programmatic loads, and external opens (`shell.openExternal`). Divergent checks per channel
  are the bug.

## The IPC handler list is not the ACL

An IPC handler's existence does not prove an untrusted frame can invoke it, and its absence
from your list does not prove safety. Per handler, inspect:

- `senderFrame` / origin validation (does it check WHO is calling?)
- argument schema (does it validate WHAT is passed?)
- result exposure (what does the reply leak?)

## Flag ladder: claim only what the flags prove

- `nodeIntegration: true` in a renderer that can run untrusted script: direct RCE.
- `contextIsolation: false` alone: prototype-pollution and bridge-reachability risk, NOT by
  itself proof of native code execution.
- `sandbox: false`: trace which capabilities actually become reachable (native modules, file
  system) and claim those.

## At-rest encryption and update feeds

- At-rest encryption of local data does not protect it when the renderer can retrieve the key
  or ask a privileged bridge to decrypt. "We encrypt the DB" is not a defense the attacker
  path respects.
- Two-sided update rule: an attacker-controlled update feed is not automatically RCE if
  artifact signatures are mandatory; conversely HTTPS on the feed does not compensate for
  missing artifact authenticity or unsafe rollback behavior. Check both directions before
  rating.

## Version-defaults ambiguity

Record the Electron version and the behavior of any MISSING explicit setting: a flag the app
never set can mean different behavior on different major releases. Absence of a config line is
ambiguous evidence until resolved against the shipped version.

## Custom protocol semantics

Whether a registered scheme is marked secure / standard / CORS-enabled / stream-capable /
privileged changes origin and storage behavior for content loaded through it. Read the
registration, not just the scheme name.

## Related

- [[dom-attacks]] - renderer-side bugs the bridge amplifies
- [[browser-extension-attacks]] - the adjacent privileged-JS surface
- [[safe-probing-and-controls]] - the claimability ladders used throughout this page
- [[client-side-path-traversal]] - file URLs through privileged bridges

<!-- promoted-slug: electron-preload-survives-navigation -->
