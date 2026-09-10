---
title: "Default Credentials"
type: cheatsheet
tags: [cheatsheet, credentials, default-creds]
sources: []
date_created: 2026-06-05
date_updated: 2026-09-10
---

# Default Credentials

Reusable list of product/appliance default credentials. **Check here before any credential work** when you identify a product; if you hit the same product on a later engagement, reuse from here instead of re-researching.

`source`: `vendor` (documented default, often via context7 product docs) or `observed` (seen in the field; record the generic product fact only, never the client host/IP).

Per the engagement discipline, default-cred checks are an acceptable early move; broad spraying of captured creds is a last resort. See [[bug-hunting-methodology]].

| product | version | username | password | source | notes |
|---------|---------|----------|----------|--------|-------|
| MSSQL | any | sa | (blank) / sa | vendor | SQL auth; check before assuming |
| Tomcat Manager | any | tomcat / admin | tomcat / admin / s3cret | vendor | /manager/html |
| Grafana | any | admin | admin | vendor | forces reset on first login |
| Jenkins | any | admin | admin / (install token) | vendor | initialAdminPassword file |
| PostgreSQL | any | postgres | postgres / (blank) | vendor | |
| Elasticsearch | <8 | (none) | (none) | vendor | unauth by default pre-8 |
| RabbitMQ | any | guest | guest | vendor | localhost-only by default |
| InfluxDB | 1.x | (none) | (none) | vendor | auth often disabled |
| Camunda Platform (7.x web apps) | 7.x | demo | demo | vendor | distribution's example user; login at `/camunda/app/welcome/`; Cockpit/Tasklist reaches scripted tasks (business-logic impact) |
| Splunk (THM lab rooms) | 9.x/10.x | admin | TryHackMe! | observed | THM pre-indexed-evidence rooms ship Splunk with this pair; also try admin/changeme (vendor default) before anything else |
| Generic admin interface | any | admin | admin / password / (blank) | vendor | first trio on any vendor admin UI |
| Generic root account | any | root | root / 12345678 | vendor | |
| Windows local administrator | any | administrator | Password | vendor | |
| FTP server | any | anonymous | (blank) | vendor | anonymous login check before any brute force |
| SNMP v1/v2c | any | (community string) | public (read) / private (write) | vendor | community strings act as the passwords |
| Product | Service / entry point | Default | Note |
| <product> | <version> | <username> | <password> | observed | <generic notes; NO client host> |

## Citizen-portal default password: the national ID number itself

A recurring pattern on government or municipal self-service portals (health, permits, tax, education): the account is provisioned with the citizen's OWN national identity number as the default password, rather than a generated or vendor-standard default. The login form itself is the tell: alongside name fields it carries a field literally named for the national-ID concept, used as the password rather than only as a lookup key.

Where this matters most: any co-located bug (an ID-lookup oracle, a leaked ID in another disclosure, a predictable ID scheme) upgrades directly to account takeover, because the secret and the identifier are the same public-ish value. Check lockout and rate limiting on the login form specifically because of this: a low-entropy, citizen-known default password makes throttling the only real remaining control, and its absence is a materially worse finding here than on a normal app.

Test with a held or self-registered account confirming an untouched account still authenticates with ID-as-password; never brute the ID field against real citizens.

## How to extend
- New product encountered: look up vendor defaults via `context7` (resolve the library/product, query for default credentials), add a row with `source: vendor`.
- Default observed in the field: add a row `source: observed` with the **generic** product + cred only. Client-specific hostnames/IPs stay in `targets/<eng>/loot.md`.

<!-- promoted-slug: camunda-platform-7-x-ships-a-documented-demo-demo-account-on -->

<!-- promoted-slug: some-government-or-citizen-self-service-portals-set-the-acco -->

<!-- promoted-slug: splunk-thm-default -->

<!-- promoted-slug: pluxml-default-admin -->

<!-- promoted-slug: ipmi-oracle-default-creds -->

## Network appliance defaults (routers, cameras, DVRs, IoT)

Edge/consumer appliances ship documented vendor defaults; on network-facing engagements these rows land more often than software-service defaults. Full corpus: `SecLists/Passwords/Default-Credentials/default-passwords.txt`.

| Product | Username | Password |
|---|---|---|
| Linksys / D-Link / TP-Link / Asus router | admin | admin |
| Netgear / Belkin router | admin | password |
| Cisco router | cisco | cisco |
| Zyxel router | admin | 1234 |
| Samsung SmartCam | admin | 4321 |
| Hikvision DVR / Panasonic DVR | admin | 12345 |
| Axis IP camera | root | pass |
| Ubiquiti UniFi AP | ubnt | ubnt |
| Canon network printer | admin | admin |
| Honeywell smart thermostat | admin | 1234 |

Default usernames stay valuable even after the password is changed: a confirmed name (`admin`, `root`, `ubnt`) collapses the attack to password-only. Before any matrix spray, enumerate likely usernames from `SecLists/Usernames/top-usernames-shortlist.txt` plus per-vendor documentation.

<!-- promoted-slug: network-appliance-default-credentials -->
