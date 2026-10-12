---
title: "Port spec: hermes self-improvement loop"
type: docs
tags: [docs, port-spec, hermes, skills]
date_created: "2026-10-12"
sources: [raw/git/hermes-agent]
---

# Self-improvement port spec (from hermes-agent source audit)

## What hermes does (file:line evidence in raw/git/hermes-agent)

- skill_manage tool: create/edit/patch/write_file/remove_file/delete; name regex ^[a-z0-9][a-z0-9._-]*$ <=64; frontmatter name+description required; new-skill desc <=60 chars (routing signal); SKILL.md <=100k; support files only under references/ templates/ scripts/ assets/; atomic under per-skill flock; append-only ledger; delete requires absorbed_into; refuses delete of pinned/essential; batch ops all-or-rollback.
- In-session trigger (SKILLS_GUIDANCE): "When you work out a non-trivial workflow, record it with skill_manage for future reuse."
- Nudge: counter each tool iteration; at 10 (skills.creation_nudge_interval) without a skill write, turn-end background review: "Be ACTIVE - most sessions produce at least one skill update... A pass that does nothing is a missed learning opportunity". Signals: user corrections FIRST-CLASS, non-trivial technique/fix, loaded skill proved wrong. Preference: patch loaded skill > patch umbrella > add support file > create new class-level umbrella. Never delete mid-session.
- Curator: no daemon; idle + interval 168h gates; O_EXCL claim lock. Lifecycle pure-function: anchor = max(last_used,last_viewed,last_patched,created); active -> stale at 14d -> archived (dir moved to .archive/, recoverable) at 30d; use again reactivates; pinned + cron-referenced exempt; never-used-young never archived. LLM consolidation opt-in (default off), fork with skills toolset ONLY (no terminal), umbrella-building prompt, absorbed_into mandatory, archive-not-delete.
- /learn: ordinary prompt turn; inventory sources; check existing skill first; workflow = one tight SKILL.md, prose = lean index + per-chapter references/; authoring standards (desc one sentence <=60, version 0.1.0, body order Title/When to Use/Prerequisites/How to Run/Quick Reference/Procedure/Pitfalls/Verification, 100-200 lines).
- Validation: skills_guard ~90 regex threat patterns (exfil, injection, destructive, persistence incl AGENTS.md/CLAUDE.md rewrite detection, network, obfuscation, supply chain, creds, bidi unicode); lint advisory (desc length/marketing, missing sections, dangling refs); dedup: create refuses existing name, ambiguous display-name refuse, restore refuses shadowing.
- Telemetry: sidecar .usage.json (use/view/patch counts + timestamps + patch_generation reuse signal), never frontmatter; bumps from slash-command fire + skill_view resolve + every mutation.

## Native ZTORCH port (design)

(a) scripts/skill_manage.py (stdlib): create/patch/write_file/delete with hermes guards (name regex, frontmatter, desc<=60, allowed subdirs, no traversal, atomic write, refuse existing, absorbed_into on delete). Patch refuses without --from-read sha256 from a prior view (read-before-write).
(b) Nudge hook: count tool iterations; >=10 without skill write -> inject one-line nudge naming skill_manage.py; umbrella-first preference order.
(c) scripts/curator.py: no daemon, SessionStart-invoked when .curator_state.json last_run_at >7d. Lifecycle frontmatter in SKILL.md (state/created/last_used/pinned/created_by); git mv to skills/.archive/ as the ledger+rollback; 14d stale / 30d archive; triggers.json-referenced + pinned exempt; never-used-young exempt; LLM consolidation off by default.
(d) Telemetry: tool-telemetry.py appends skill_use/skill_patch events to .events.jsonl; curator derives last_used/use_count from it; frontmatter carries only what events cannot.

Skipped: batch ops, guard scanner (vault operator-owned), write-approval staging (hooks gate), profiles.
