# workflow-brain workflow

## Fleet (5 slots)

- Slots 1-2: `Skill(osint-workflow)` lanes, tier glm-5.3-flash, completely
  passive, run until OSINT exhausts.
- Slots 3-5: active lanes on the LOCKED vhost only. Tier: mechanical lanes
  glm-5.3-flash, analysis lanes glm-5.3, RTL consults and exploit-dev
  glm-5.3-max.

## Loop

1. Preflight: `python3 scripts/offensive.py vhost status`, read
   `state.md`, `Approach.md`, `Deadends.md`, `targets/active.md`.
2. No locked vhost? Pick the first QUEUED row of `lists/inscope-hosts.md` and
   `python3 scripts/offensive.py vhost lock <host>`.
3. Per stage of active-workflow: `python3 scripts/offensive.py lane-init
   --vhost <host> --skill <name>`, dispatch the subagent with the lane's
   `brief.md`, collect the 15-line envelope.
4. Merge envelopes into state files (single-writer: only the brain writes).
5. Wall protocol: 2 verified-hash misses or a dry streak on one direction ->
   `Skill(redteamlead)` over finds + deadends; record 2-4 ranked directions +
   STOPs in `decisions.md`.
6. Wiki at sink-research moments: before dispatching any new attack-path
   lane, query the wiki (qmd first; graphify only for multi-hop chaining or
   large source-map AST graphs).
7. Lane return: verify with `python3 scripts/completion-gate.py check
   <lane>/checklist.md --strict` (never trust the envelope's self-verdict),
   then `python3 scripts/offensive.py done ...` (G10 re-checks).
8. Pass close: `vhost pass-done`, RTL consult, stage re-entry per
   active-workflow pass focus; vhost closes only via `vhost unlock`.

## Hard rules

- Lanes never read `ledgers/cmdlog/`; neither does the brain (stallcheck +
  human inspection only).
- Every lane directive carries verbatim: the full-read mandate, the
  Obsidian-safe backtick rule, the no-list-edits rule.
- Budget: bounded stop conditions per vector still apply (OOB sink ~30-40
  payloads, spray matrix once); rotate within the pass, never grind.

## N/A escapes

- `N/A: fewer than 2 disjoint rows (serial fallback per AGENTS.md)`
- `N/A: osint exhausted before first wave`
