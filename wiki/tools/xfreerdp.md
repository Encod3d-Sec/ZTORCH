---
title: "xfreerdp"
type: tool
tags: [windows, rdp, access, postex]
date_created: 2026-09-10
date_updated: 2026-09-10
sources: []
phase: exploit
---

## Purpose

**xfreerdp** is the Linux RDP client: the standard move once a Windows cred lands, and the cleanest way to turn a valid account into an interactive session for GUI-only paths (vendor consoles, RDP-only privesc steps).

## Core usage

```sh
xfreerdp /v:10.0.0.5 /u:user /p:'Password1' +clipboard /dynamic-resolution /cert:ignore
```

## Gotchas

- On a limited-egress network append `/gateway:` or ride the engagement pivot; RDP over Ligolo works but needs the port forwarded first.
- Session locking: a fullscreen grab (`/f`) on a shared box can lock the operator out of their own view; prefer windowed `/w:1600 /h:900`.
- Failed logins here still count toward lockout thresholds exactly like any other auth surface; check lockout policy before spraying RDP.
