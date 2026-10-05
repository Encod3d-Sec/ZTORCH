---
title: "Engagement State - {{ENGAGEMENT}}"
type: engagement-state
engagement_type: bugbounty
tags: [engagement, state, bugbounty]
date_created: "{{DATE}}"
date_updated: "{{DATE}}"
sources: []
---

# State - {{ENGAGEMENT}}

Asset / endpoint inventory. Drop raw recon (subfinder/httpx/nuclei) in `ingest/`, then synthesize.

`access`: none / recon / tested / vuln

| asset | url | endpoint | param | tech | access | notes |
|-------|-----|----------|-------|------|--------|-------|

## Status

Close-out marker goes HERE, below the table, so a mid-engagement edit can never split the
asset table again.

`## STATUS: COMPLETE` (also accepts SOLVED/OWNED/ROOTED) marks the engagement done -- all
in-scope findings triaged to Completed and reported/submitted -- and is the trigger the
close-out reflex, walkthrough auto-assembly, and learn harvest all watch for. Without this
marker a finished programme never auto-triggers Skill(walkthrough)/Skill(learn).

## Facts

One line per fact: key | confidence | summary. Summary must carry what + where + how to
verify. Body lives on demand in the poc/ card or loot entry the key names. Deprecation is
strike + date, never delete. Negative results are facts ("tested X, no exploitable vuln")
and prevent retries exactly like Deadends.md.

| key | conf | summary |
|---|---|---|

