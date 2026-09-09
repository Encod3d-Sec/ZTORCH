---
title: "HTTP/2 Protocol Attacks"
type: technique
tags: [web, http2, protocol, dos, triage, exploitation]
phase: exploitation
date_created: 2026-09-10
date_updated: 2026-09-10
sources: []
---

## What it is

Protocol-level HTTP/2 attacks that are NOT request smuggling (that family, H2.CL/H2.TE/CSD/h2c, lives on [[http-request-smuggling]]): stream-lifecycle abuse (rapid reset, CVE-2023-44487) and HPACK header-buffer abuse (continuation flood, CVE-2024-27316). Both burn server resources per stream/frame rather than per connection, so a single client starves a frontend that sits fine under HTTP/1.1 load.

## How it works

- **Rapid reset (CVE-2023-44487):** HTTP/2 lets the client cancel a stream at any time with RST_STREAM. The attacker opens a stream, sends HEADERS, immediately RSTs it; the server has already allocated per-stream state (and often starts work) before the cancel lands. Because the reset frees the concurrent-stream slot instantly, the max-concurrent-streams limit never trips, and the request rate is decoupled from TCP connection count. Any h2 frontend that does non-trivial per-request work before handling the reset is affected; backend HTTP/1.x pools amplify it (each reset request may already have been proxied).
- **Continuation flood (CVE-2024-27316):** a HEADER block may span HEADERS + an unbounded run of CONTINUATION frames. HPACK decompression buffers grow while the header block is incomplete; many server implementations never bound CONTINUATION count or buffered size and apply no flow control to it. Endless CONTINUATION frames with padding grow memory until OOM; latency creep or connection stalls are the observable.

## Attack phases
Triage / exploitation (needs an h2-capable frontend). RoE gate: both are DoS-class; only run them where `no_dos` is NOT set, and prefer the single-burst probes below over a sustained flood.

## Prerequisites
- Frontend speaks h2 (ALPN negotiated). Confirm before anything else:
```sh
curl -sI --http2 -o /dev/null -w '%{http_version}\n' https://TARGET/
```

## Methodology

### 1. Rapid reset triage (bounded, evidence-grade)
One burst, capped, then measure recovery; do not loop.
```sh
# nghttp2-client based single-burst: open N streams, RST immediately, watch error rate + recovery time
# public reference PoCs: github.com/google/security-research (2023 HTTP/2 rapid reset advisory PoCs)
```
Signals: 5xx/STREAM_REFUSED spike during the burst, p99 latency, and whether the frontend sheds other clients (connection resets for bystander traffic). Capture one request/response pair showing the 502/503 window plus a timing note as the PoC evidence; the vendor advisory math (stream cancellation rate vs worker count) does the impact argument.

### 2. Continuation flood triage
Send one oversized header block split across many CONTINUATION frames and watch memory-sensitive behavior:
```sh
# nghttp or a python h2 socket script: HEADERS frame, then CONTINUATION frames with padding
# until the server closes, errors, or stalls; single connection, no reconnect loop
```
Signals: connection stall vs clean FRAME_SIZE_ERROR/ENHANCE_YOUR_CALM close. A server that accepts an unbounded run without RST or GOAWAY lacks the bound; report with the observed max accepted before failure.

### 3. Amplification checks
- Is h2 terminated at a proxy that pools HTTP/1.1 to the backend? Reset requests already proxied do backend work the attacker never pays for (the amplification core).
- gRPC frontends (h2-native) are frequently the worst case; check for gRPC reflection/health endpoints as the cheap canary.

## Bypasses and variants
- Rate limiting keyed on connections or QPS is blind here (few connections, normal QPS, huge stream churn): frame-count-based limits are the mitigation to test against.
- Spread across multiple frontend IPs/CDN edges when a single edge sheds load; the origin behind the CDN is the real target.
- HTTP/3 (QUIC) sibling: rapid-reset-style stream abuse reappears in h3 where the frontend supports it; same triage against alt-svc advertised endpoints.

## Detection and defence
Server: bound concurrent streams AND resets-per-window (e.g. nginx `http2_max_concurrent_streams`, reset-rate limits, `lingering_close`), reject header blocks over a size/count cap (CONTINUATION limits; Apache/Envoy patches 2.4.59+/1.29+ era), per-connection frame budgets. Network: alert on streams/sec and CONTINUATION frames/sec per client, not req/s.

## Tools
`curl` (ALPN check), `nghttp`/`nghttpd`, python `h2` lib for frame-level scripts, h2load for a controlled load baseline. Public advisory PoCs: Google security-research repo (rapid reset), Bartek Bróźek's continuation-flood PoC. See [[http-request-smuggling]] for the h2 smuggling family and [[cdn-waf-bypass]] for finding the origin behind a CDN.

## Sources
