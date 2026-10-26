---
name: osint-workflow
description: Always-on passive OSINT for the engagement. Two flash-tier lanes
  (osint-archive: Wayback/CommonCrawl/URLScan/OTX via waymore+gau+wigolo;
  osint-infra: CT logs, DNS/ASN, repos, third-party refs) running in parallel
  with active-workflow from move 0. Zero packets to in-scope targets.
---

# osint-workflow

Launched by workflow-brain into slots 1-2 and re-run as scope grows. Every
discovered domain is classified into `lists/inscope-hosts.md` or
`lists/outscope-3rdparty.md`; historical URL sets merge into the locked
vhost's stage 2-3 inputs.
