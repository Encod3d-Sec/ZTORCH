---
name: workflow-brain
description: Main-session engagement brain. Mandatory from move 0 (no open-asset
  precondition). Owns the driver loop, board, all state-file writes, and triage;
  dispatches 2 osint + up to 3 active lanes on the locked vhost and never
  executes lanes itself. engage routes straight here.
---

# workflow-brain

Supersedes `brain` (which stays until cutover). The brain is the single writer
of `state.md`, `Approach.md`, `Deadends.md`, and `lists/*.md`; lanes return
envelopes and the brain merges between waves. Read `workflow.md` before the
first dispatch.
