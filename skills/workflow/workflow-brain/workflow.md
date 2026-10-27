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

- Every lane directive carries verbatim: the full-read mandate, the
  Obsidian-safe backtick rule, the no-list-edits rule.
- Budget: bounded stop conditions per vector still apply (OOB sink ~30-40
  payloads, spray matrix once); rotate within the pass, never grind.

## Speed rules (D19-D27, 2026-10-27 retro)

- **Platform-pattern memo (D20).** At move 0 create `platform-patterns.md`
  (engagement root) with the table `| pattern | class | evidence |`; after any
  lane that establishes a platform-wide negative (edge block class, authz
  gate, uniform error collapse), append the pattern with its cap citation.
  Briefs and RTL consult it and DROP probe rows whose class is refuted
  platform-wide unless the brief states the delta.
- **Anchors registry (D22).** Route-oracle / block-page anchors live in
  `state.md` under `## Anchors`:
  `| host | path | md5 | bytes | cap-cite | date |`. A consumer verifies with
  ONE request: md5 match = trust the anchor; mismatch or row older than 24h =
  full re-probe and update the row. Never re-derive a pinned anchor.
- **Sealed-gate short-circuit (D23).** Root probe hits the authz gate +
  OPTIONS returns the same gate with no `Allow` + the 404 anchor is nonsense
  on this prefix = record SEALED in `Deadends.md` and STOP at 3 probes. Same
  rule for a uniform no-upstream proxy error across paths.
- **Terminal-host suppression (D19).** Multi-host sweep briefs run
  `python3 scripts/terminal_hosts.py <eng>` first and DROP every listed host
  (no-upstream / unresolvable / NXDOMAIN / SEALED already recorded) instead
  of re-probing recorded terminal states.
- **Verifier-fanout (D24).** When 2+ lanes return in one wave, dispatch ONE
  verifier fork (cheap tier) to pre-check the returned envelopes' mechanical
  claims - md5 of cited captures, jq/line counts, exit trailers, file
  existence. It returns a pass/fail table; the brain deep-reads ONLY the
  failures and anything feeding a FIND. Lane verdicts are still never trusted
  raw - the fork narrows what the brain reads, it does not replace the read.
- **Spec-extract-first (D27).** A captured API spec or doc (OpenAPI/Redoc/
  swagger/GraphQL SDL) makes OFFLINE extraction the next lane on that
  surface - extracted routes/params seed board rows - before any live probing
  of the same surface. Extraction is free; probing spends the request budget.

## N/A escapes

- `N/A: fewer than 2 disjoint rows (serial fallback per AGENTS.md)`
- `N/A: osint exhausted before first wave`
