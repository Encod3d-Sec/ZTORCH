---
title: "Port spec: hermes memory + session search"
type: docs
tags: [docs, port-spec, hermes, memory]
date_created: "2026-10-12"
sources: [raw/git/hermes-agent]
---

# Memory/session-search port spec (from hermes-agent source audit)

## Hermes mechanics (evidence in raw/git/hermes-agent)

Data model: two stores, MEMORY.md (agent/environment notes, 2200-char budget) + USER.md (user profile, 1375-char budget), entries joined by a delimiter, profile-scoped. Rendered as a fenced block with a [N% - c/limit] header.

Write path: memory tool add|replace|remove|batch; add idempotent; over-limit add rejected with a "retry as ONE batch that removes/shortens AND adds - limit checked on batch final state" error; batch may not empty the store. Selection heuristics (from the tool schema): only facts that apply to EVERY session regardless of task; SKIP trivial/rediscoverable/raw dumps/task progress/completed-work/TODO (session search owns those); reusable procedures belong in SKILLS not memory. Declarative facts not instructions to self ("User prefers X" yes, "Always do X" no). A fact stale within a week belongs in session history.

Read path: builtin = FROZEN load-time snapshot in the system prompt (mid-session writes hit disk, never the prompt; reload only on compaction rebuild). External providers = per-turn prefetch fenced as <memory-context> with a system note marking it reference-data-not-user-input, byte-dedup per section, spill-to-disk at 10k chars.

Nudges: counter every user turn (interval 10); fires AFTER the response is delivered; forks a background review with the two-store routing prompt: USER.md = who the user is (persona, preferences, style, expectations); MEMORY.md = environment facts (tool quirks, conventions, config gotchas, paths). One fact one store, never both; "Nothing to save" is a valid outcome. Skill-review nudge runs in parallel (tool iterations, interval 10).

Session search: FTS5 (BM25) + trigram twin over messages; session_search tool with 4 shapes (query discovery / scroll around message / read session / browse); demote automation (cron/subagent/tool sources) BELOW interactive turns before dedup (recall-blindness fix); lineage dedup; top-result-only full hydration; 2000-char/message read cap; compaction markers excluded; rebuild-percentage surfaced so thin results are not ground truth.

User modeling (Honcho): external server-side dialectic (LLM derives user insights each 2 turns, 3-depth reconciliation, per-peer profiles). Derived-vs-recorded distinction. DROP for port (external API, single-operator vault).

Failure guards: consolidation retry cap 3/turn then "stop retrying, leave memory unchanged"; success response omits entries (kills fix-loops); staged replace/remove pinned to matched_entry with stale refusal + 3 closest entries on zero match; typography-folded matching; threat scan on write AND load (hits render [BLOCKED:], raw kept on disk); drift detection (.bak + refuse if entry > whole limit); unreadable file refuses write; atomic temp+rename under flock; recall fences stripped from streamed output; provider faults isolated per try/except.

## Native ZTORCH port (design)

Storage: session/memory.md with TWO sections (## Operator - who they are; ## Environment - tool quirks, conventions, gotchas, paths), `- ` bullet entries, char budgets 2200/1375 rendered with a percent line. Frozen snapshot semantics: SessionStart injects it (same pattern as session/hot.md); mid-session writes land on disk for NEXT session, never hot-injected.

Store: scripts/memory.py (stdlib): add|replace|remove|batch with hermes semantics verbatim (idempotent add, batch-final-state budget check, no-empty-store, old_text locator, stale-refusal with 3 closest on zero match, typography folding, atomic write under flock, threat-scan advisory on write/load, drift .bak guard).

Nudge: Stop-hook counter every 10 user turns -> one-line nudge with the two-store routing text; background-review fork maps to the existing learn flow at close-out (no per-10-turn subagent).

Session search: qmd/zg wrapper scripts/session-search.py over targets/<eng>/log.md + state.md + session/log.md: query/scroll/read/browse shapes, lane/automation lines demoted below operator lines, lineage dedup (lane line + its VERIFIED append = one hit), top-hit-only full hydration, 2K-char/message cap. Client boundary: results printed, never copied into tracked files.

Drop: Honcho dialectic, provider plugin plumbing, api_content sidecar, spill-to-disk, FTS5/trigram machinery (qmd provides BM25).
