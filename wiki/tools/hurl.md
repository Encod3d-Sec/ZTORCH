---
title: "hurl"
type: tool
tags: [web, http, automation, testing]
date_created: 2026-10-05
date_updated: 2026-10-05
sources: [github-usestrix-strix]
phase: exploit
---

# hurl

Plain-text HTTP request runner with per-request asserts (Orange-OpenSource/hurl, Rust on
top of libcurl, `hurl 8.0.1`). A `.hurl` file chains requests: response bodies and
headers captured into variables feed the next request, and each transition carries an
explicit assertion (`status`, `jsonpath`, `regex`, `contains`). That makes a multi-step
flow (login, CSRF token, object create, cross-account read) a REVIEWABLE artifact under
`poc/` instead of an opaque script: the file is the evidence, reruns are one command,
and `--test` mode reports pass/fail per assert like a test suite.

## Core usage

```bash
# run a flow file, report the sequence + asserts
hurl --variable host=10.10.10.5 --test login-and-read.hurl

# verbose single request through the proxy, path untouched (--path-as-is)
hurl --path-as-is --proxy http://127.0.0.1:8080 http://10.10.10.5/%2e%2e/%2e%2e/etc/passwd
```

Flow file shape (capture feeds the next request; assert per transition):

```text
POST https://{{host}}/login
Content-Type: application/json

{ "user": "admin", "pass": "{{pass}}" }

[Captures]
token: jsonpath "$.token"
[Asserts]
status == 200

GET https://{{host}}/api/orders/{{token}}
[Asserts]
status == 200
jsonpath "$.owner" == "admin"
```

## When hurl vs Burp

Burp Repeater stays the home for confirm-worthy single requests (the operator replays
them). hurl encodes the SEQUENCE: multi-step flows, smoke tests that gate a claim
(unique canary expected at step N), and regression re-checks of a confirmed chain at
close-out. Ceiling: stack-normalized parser differentials and HTTP smuggling stay in
Burp (raw socket control); hurl rides libcurl, which normalizes what curl normalizes.

## Gotchas

- Kali's apt `hurl` package is an unrelated tool (`hURL`); install the deb from
  Orange-OpenSource/hurl releases (done on the VM 2026-10-05, `/usr/bin/hurl`).
- Canaries: every step that asserts identity/data carries a UNIQUE per-run token, so a
  cached or stale response fails the assert instead of passing it.
- Negative control transition: encode the control request (no attack input) in the same
  file; its failing assert beside the passing one is the pair evidence.
- `--path-as-is` for any traversal/encoding probe; hurl (curl) re-encodes paths by
  default, silently defusing the payload.
