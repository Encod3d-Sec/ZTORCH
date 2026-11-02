---
title: "Approach - {{ENGAGEMENT}}"
type: engagement-approach
engagement_type: bugbounty
tags: [engagement, approach, board]
date_created: "{{DATE}}"
date_updated: "{{DATE}}"
sources: []
# current_phase / entered_because: OPTIONAL. Set current_phase to the display label the
# board uses (e.g. "Phase 4 Exploit") and entered_because to the finding/edge that justified
# the transition. When set, status.py + SessionStart report this instead of the heuristic;
# a citation naming an out-of-scope asset is ignored. Leave unset to use the auto-heuristic.
current_phase: ""
entered_because: ""
---
# Kill-Chain Board - {{ENGAGEMENT}}

Status: `[ ]` todo | `[~]` doing | `[x]` done | `[-]` n/a | `[?]` parked (needs follow-up) | `[!]` deadend (-> Deadends.md)
GATE 1 (wiki): no hand-rolled exploit until its Weaponize wiki item is `[x]`.
GATE 2 (poc):  no exploit step goes `[~]`->`[x]` without a poc/ image.
GATE 3 (loop): a vector exhausted -> mark `[!]`, one Deadends line, move to the next open item. Never re-run `[!]`.

## 4. Exploit

Stage-by-stage routing lives in Skill(active-workflow) (the stage table below)
+ Skill(engage); per-technique tooling in [[wiki/cheatsheets/recon]]. The
stage table + board below are the only checklists this file carries.

## Workflow stages (per locked vhost)

- [ ] Stage 0: vhost locked + Caido project + identities recorded
- [ ] Stage 1: surface probe + wiki/graphify context pass
- [ ] Stage 2: js-discover corpus + js-extractor lists
- [ ] Stage 3: list-fed fuzz + param mining
- [ ] Stage 4: version/CVE research lane
- [ ] Stage 5: signal-gated hunts via dispatch-queue
- [ ] Stage 6: RTL consult + pass decision

### 4a. Findings  (subsumes coverage.md: asset x class x status)
| id | asset | vuln class | arsenal | skill | tool | status | poc | poc_kind |
|----|-------|-----------|---------|-------|------|--------|-----|----------|

route by class: Skill(wiki-arsenal) -> Skill(`hunt-<class>`)
chains to impact: e.g. ssrf -> imds -> creds -> ato  -> [[imds-cloud-metadata]] [[wiki/techniques/web/account-takeover]]

### 4c. Impact
- [ ] impact demonstrated (ATO / data / RCE) + poc image
- [ ] FIND scaffolded + triaged        -> Skill(triage) then Skill(evidence)
