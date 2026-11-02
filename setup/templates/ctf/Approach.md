---
title: "Approach - {{ENGAGEMENT}}"
type: engagement-approach
engagement_type: ctf
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

Stage-by-stage recon/weaponize/deliver routing lives in Skill(engage) + the
hunt skills; per-technique tooling in [[wiki/cheatsheets/recon]]. The board
below is the only checklist this file carries.

### 4a. Foothold  (subsumes coverage.md: asset x class x status)
| id | asset | vuln class | arsenal | skill | tool | status | poc | poc_kind |
|----|-------|-----------|---------|-------|------|--------|-----|----------|

cred attacks:  sqlmap / hydra / medusa / john / hashcat
  -> [[wiki/tools/sqlmap]] [[wiki/tools/hydra]] [[medusa]] [[wiki/tools/john]] [[wiki/tools/hashcat]] [[password-attacks]] [[wordlists]] [[default-credentials]]
route by class: Skill(wiki-arsenal) -> Skill(`hunt-<class>`)

### 4c. Objective
- [ ] user flag / initial objective
- [ ] root flag / DA / target impact

### 4b. Post-foothold (privesc / lateral)

Filled by `offensive.py` (seed_4b) on the first foothold; rows land here as a
table. Do not hand-add checklist items - the driver owns this section.
