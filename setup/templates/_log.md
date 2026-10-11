---
title: "Engagement Log - {{ENGAGEMENT}}"
type: engagement-log
tags: [engagement, log]
date_created: "{{DATE}}"
date_updated: "{{DATE}}"
sources: []
---

# Log - {{ENGAGEMENT}}

Append-only, per-engagement audit trail. **All client-specific narrative goes here**, never in `session/hot.md` or `session/log.md` (those are generic + auto-loaded). engagement-init surfaces the latest entries at session start.

Newest first. One block per session.

## Run ledgers

Each dispatched lane gets `run-ledger.md` in its lane dir at dispatch
(`python3 scripts/completion-gate.py init <lane-dir> --title "<run>"`);
completion-gate verdicts are appended to this log as `Ruling:` lines.

---
