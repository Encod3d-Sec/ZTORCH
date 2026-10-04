---
title: "Grafana Observability Stack Attacks"
type: technique
tags: [web, cloud, observability, grafana, prometheus, alertmanager, ssrf]
phase: exploitation
date_created: 2026-10-05
date_updated: 2026-10-05
sources: [github-usestrix-strix]
---

## What it is

Attack surface of the Grafana / Prometheus / Alertmanager / Loki observability stack. These
services ship with weak or absent authentication by default, so reachability itself is often
the finding; there is rarely a CVE involved. Payoff is recon data, credential leakage, internal
network pivoting, and detection-evasion. Pair every open endpoint with concrete recovered data
so impact is visible, not implied.

## Access and defaults

- Default credentials `admin:admin` with a Skip button on the forced password-change prompt;
  a meaningful fraction of internet-facing instances still accept them. Try Skip before
  concluding the password was changed.

## Grafana arbitrary file read (CVE-2021-43798)

Plugin path traversal, fixed in 8.3.1. Every install ships pre-installed plugins, so the path
always exists; ids that always exist: `prometheus`, `graph`, `text`, `alertlist`, `table-old`.

```sh
curl --path-as-is "https://target:3000/public/plugins/prometheus/../../../../../../etc/grafana/grafana.ini"
```

`--path-as-is` is mandatory; the default client normalization strips the traversal.

## Data source proxy SSRF mechanics

The single most misunderstood primitive in Grafana:

- Grafana OSS ships a no-op URL validator and an empty `allowed_domains` list (empty = allow
  all), but the proxy resolves the request path against the SELECTED data source's configured
  base URL. To reach an arbitrary host you must first create or edit a data source whose URL
  is the target, which needs data source write permission (`datasources:create` or
  `datasources:write` in role terms).
- Reusing an ordinary Prometheus data source id and appending a metadata path just hits
  Prometheus, not the metadata service. That is not SSRF; do not report it as one.
- The Image Renderer plugin is NOT a `?url=` fetch proxy. It renders dashboard and panel
  routes (`/render/d-solo/...`); SSRF arises only when a render request can be coerced to
  fetch an internal URL (chained, e.g. with CVE-2025-4123).

## Version-gated RCE (CVE-2024-9264)

DuckDB SQL injection: Grafana 11.0.0-11.2.x only (10.x not affected), any Viewer-or-higher role. RCE requires the `duckdb` binary to be present in Grafana's `$PATH`; it is not shipped
by default. No duckdb in PATH means not exploitable: report the injection, do not call it RCE.

## Recovering data source secrets

The API never echoes secrets, but two paths exist:

1. Query a backend directly through the data source proxy using the stored credentials.
2. Extract `grafana.db` (file read or disk access) and decrypt `secure_json_data` offline with
   the `secret_key` from `grafana.ini` (AES).

## Plugin installation chain

Plugin archives are extracted BEFORE signature verification, so a malicious archive carrying
chained symlinks writes the filesystem even though the signature check then fails. Archive
installation is the trigger, not signature bypass.

MCP integrations (mcp-grafana): SSRF via `grafana_api_request` and `X-Grafana-URL` header
forwarding. Preventing token forwarding alone does not prevent this SSRF.

## Prometheus and Alertmanager

- Both ship with no authentication by default. Absence of auth is the finding; enumerate
  targets, rules, labels, and config for internal topology and credentials.
- Alertmanager silence abuse as anti-forensics: `POST /api/v2/silences` is unauthenticated in
  default deployments; a matcher of `alertname=~".+"` with a 30-day duration suppresses all
  alerts. Report as detection-evasion impact, not just misconfiguration.
- Alertmanager receiver configuration holds plaintext Slack / PagerDuty / SMTP credentials.

```sh
curl -s -X POST https://target:9093/api/v2/silences -H 'Content-Type: application/json' \
  -d '{"matchers":[{"name":"alertname","value":".+","isRegex":true}],"duration":"720h","comment":"probe"}'
```

## Masking: what is and is not a leak

Prometheus `<secret>` masking is incomplete; report masked values correctly:

- Masked `<secret>` values are NOT leaks.
- What genuinely leaks: `basic_auth` usernames, and credentials embedded in target or endpoint
  URLs (`https://user:pass@host/...`), which are NOT masked.
- `remote_write` / `remote_read` blocks reveal internal backend endpoints and usernames even
  when secrets are redacted.

## Log and trace backends

Loki, Tempo, and Jaeger hold real traffic: request bodies, headers, tokens, cookies, SQL. A
single logged bearer token is direct account takeover; query history is a credential harvest.

## Related

- [[aws-metadata-ssrf]] - the internal targets the DS proxy typically reaches
- [[default-credentials]] - first check on any exposed instance
- [[safe-probing-and-controls]] - claimability ladders for version-gated RCE reporting
- [[cdn-waf-bypass]] - alternative internal-network pivots

<!-- promoted-slug: grafana-ds-proxy-ssrf-needs-datasource-write -->
