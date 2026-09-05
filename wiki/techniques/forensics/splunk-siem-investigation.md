---
title: "Splunk SIEM Investigation"
type: technique
tags: [forensics, blue-team, splunk, siem, dfir, ctf, log-analysis, incident-response]
phase: post-exploitation
date_created: 2026-09-05
date_updated: 2026-09-05
sources: []
---

## What it is

Answering blue-team / DFIR CTF rooms where the evidence is pre-indexed in Splunk and the task is a question ladder over one incident: reconstruct the chain by correlating web, Windows-auth, endpoint, and network (Zeek) evidence. Covers the search workflow AND the curl/REST automation lane for when driving the UI by hand is too slow.

## Access lane for THM Splunk rooms

- The reverse-proxy URL is public (no VPN needed); the app may sit under a path prefix (e.g. `/splunk`), root just 302s there. Direct `<ip>:8000` needs the room VPN.
- Default login for THM pre-indexed rooms: see [[default-credentials]] (`admin` / `TryHackMe!`, then `changeme`).
- REST automation gotchas (each one cost a debugging round):
    - the THM reverse proxy STRIPS the `Authorization` header, so a `services/auth/login` sessionKey is useless on subsequent calls (every REST call 303s to the login page). Drive REST through the web-form session instead: cookie jar (`splunkd_8000` + `splunkweb_csrf_token_8000`) plus header `X-Splunk-Form-Key: <splunkweb_csrf_token_8000 cookie value>`, `Origin`, `Referer`, `X-Requested-With: XMLHttpRequest`, else `search/jobs/export` answers 401 "CSRF validation failed"
    - the login page embeds the anti-CSRF cval as JSON (`"cval":123...`), not as a `cval=` form field
    - SPL POSTed to `search/jobs/export` must start with the literal word `search`, else 400 `SEARCHFACTORY:UNKNOWN_OP__index`
    - `stats ... by <field>` SILENTLY returns 0 rows when the BY field does not exist in that sourcetype; if a query looks empty, re-run with `| head 40` and no table to see `_raw`

REST search pattern (one fresh login per session):

```sh
curl -sk -c cj.txt 'https://<rp-host>/<prefix>/en-US/account/login' -o login.html
curl -sk -b cj.txt -c cj.txt -X POST 'https://<rp-host>/<prefix>/en-US/account/login' --data-urlencode 'username=admin' --data-urlencode 'password=<pw>' --data-urlencode 'cval=<CVAL from login.html>' --data-urlencode 'return_to=/<prefix>/en-US/app/search/search' -o /dev/null
curl -sk -b cj.txt -H 'X-Splunk-Form-Key: <splunkweb_csrf_token_8000 cookie value>' -H 'Origin: https://<rp-host>' -H 'Referer: https://<rp-host>/<prefix>/en-US/app/search/search' -H 'X-Requested-With: XMLHttpRequest' -X POST 'https://<rp-host>/<prefix>/en-US/splunkd/__raw/services/search/jobs/export' --data-urlencode 'search=search <SPL>' --data-urlencode 'output_mode=json'
```

## Investigation workflow (the question ladder)

1. Map the evidence before filtering anything: indexes, sourcetypes, hosts. Note which host is a SENSOR (e.g. Zeek logs carry `host=<sensor>`, so pivot on `src`/`dest`, never on `host`; wineventlog `host` is the endpoint). Rooms explicitly hint "use source-specific endpoint fields, not the ingestion host".
2. Time-bound with EPOCH values inside the SPL (`earliest=... latest=...`) to dodge UI timezone ambiguity; widen +/- 1 day around the stated incident day.
3. Find the anomaly broad -> narrow: count the rare thing first (`index=* POST | stats count by index sourcetype`), then table the events. One odd POST among thousands of GETs is the usual room opener.
4. Pivot each answer into the next question: attacker IP -> logons on the box -> group change -> lateral movement. The typical intrusion chain and its queries:

```sh
# entry: rare web method
index=* POST earliest=<e1> latest=<e2> | stats count by index sourcetype
index=network sourcetype=zeek:http POST | table _time src dest uri method user_agent status_code
# auth on the box: batch/service logons just before the entry event
index=wineventlog host="<endpoint>*" EventCode=4624 | table _time LogonType TargetUserName SubjectUserName ProcessName IpAddress
# AD change: who got added to which group
index=wineventlog (EventCode=4728 OR EventCode=4732 OR EventCode=4756) | table _time host SubjectUserName TargetUserName MemberName MemberSid
# lateral movement: same attacker IP, RDP conns, sustained vs reset
index=network sourcetype=zeek:conn src=<attacker-ip> dest_port=3389 | table _time src dest duration conn_state orig_bytes resp_bytes
index=network sourcetype=zeek:rdp | table _time src dest dest_port cookie result security_protocol
```

5. Sustained vs reset in Zeek: sub-millisecond `RSTO`/`RSTR` with 0 bytes is a scan/failed attempt; a duration of seconds with real `orig_bytes`/`resp_bytes` is the session the question means. `zeek:rdp` `cookie` often carries the RDP username.

## Field cheat sheet

Windows LogonType (EventCode 4624): `2` interactive, `3` network (SMB/share), `4` batch (scheduled task / service abuse), `5` service, `8` network-cleartext, `10` RemoteInteractive (RDP), `11` cached-interactive. A non-system account showing type 3 AND type 10 on a server it never logs into is the classic compromised-service-account signature.

AD group-change events: `4728` member added to a GLOBAL security group, `4732` to a domain-LOCAL group, `4756` to a UNIVERSAL group. In all three `SubjectUserName` is who made the change, `TargetUserName` is the GROUP, and the added member is `MemberName`/`MemberSid` (often only the SID). A service account landing in an admin-capable group is the standard privilege-escalation beat of these rooms.

Zeek sourcetype field names: `zeek:http` uses `uri` / `src` / `dest` / `user_agent` / `status_code` (NOT `uri_path` / `clientip` / `method`-as-field in every dataset); `zeek:conn` uses `duration`, `conn_state`, `orig_bytes` (attacker->dest), `resp_bytes` (dest->attacker, "data returned by the destination").

Room answer-format masks (the `**.**.**` strings) are approximate; trust the raw event field over the mask.

## Tools

- Splunk Search & Reporting UI (time picker: All time for evidence maps)
- curl for the REST lane above; drive it from a cheap subagent and demand raw JSON back

## See also

- [[digital-forensics]] for artifact/memory/pcap forensics (non-SIEM rooms)
- [[splunk-lpe-persistence]] for the offensive side of Splunk instances

<!-- promoted-slug: splunk-siem-investigation -->
