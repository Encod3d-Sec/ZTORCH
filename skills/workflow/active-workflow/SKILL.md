---
name: active-workflow
description: Per-vhost deep-dive engine. Stages 0-6 (lock+caido, context,
  JS full-read, list-fed fuzz, version research, signal-gated hunts, RTL pass
  review), 2-3 full passes per vhost before unlock. workflow-brain dispatches
  these stages as lanes.
---

# active-workflow

One vhost at a time, fully deep-dived, nothing left on the table. The
workflow.md stage table is the contract; each stage's entry gate checks the
previous stage's outputs (machine-verified). Pass 2 and 3 focus areas are
listed in workflow.md stage 6.
