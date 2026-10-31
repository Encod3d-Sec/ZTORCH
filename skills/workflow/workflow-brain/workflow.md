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
9. Standing research lane (standard, driver-fired: the `next` RESEARCH row
   emits this whenever a version is fingerprinted and the last pass is older
   than 14 days or absent)

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

## Retro rules (R1-R10, 2026-10-31 engagement retrospective)

- **Compaction step zero (R1).** After ANY compaction or restart, before the
  next action: pin absolute vault-root paths, re-check the running fleet
  (ListAgents), re-dispatch orphaned lanes (dispatched, never returned),
  re-arm watchers. Never assume pre-compaction dispatches survived.
- **Pre-dispatch premise check (R2).** Verify the lane's premises against
  captures/state before dispatch: the route exists (spec or capture), the
  auth shape is stated in the brief (none / anon bearer / user), every
  banked artifact the brief cites exists on disk. Briefs state the required
  auth shape and the exact request schema per step - a lane never guesses
  field names (one lane burned 40 min on a single wrong premise line).
- **Degraded-mode dispatch (R3).** A hard dependency failing (token endpoint
  500, seat down) means dispatch a bypass / alternate-vantage lane
  immediately; never park the whole dependent queue behind one flap.
- **Idle-board rule (R4).** Stamp-only tick + empty running set = dispatch
  the next queued board lane. Idle is a dispatch trigger, not a stop.
- **Canonical timestamps (R5).** One format, writer-stamped true UTC
  (`YYYY-MM-DD HH:MMZ`), never a hand-suffixed Z on local time (broke four
  `find -newermt` scopes in one run). Never diff by mount mtime (/mnt/c
  mtimes lie) - ledger timestamps + content hashes instead.
- **Envelope contract (R6).** The brief pins the envelope path and analysis
  filename; the lane persists the envelope to that file BEFORE returning
  (a verdict only in the return message is lost to compaction); the
  envelope's capture list matches the requests-ledger numbering.
- **FIND numbering check (R7).** Before assigning a new FIND number, look
  at `Vulns/` (or Vuln-index.md). A collision costs mv + N card edits.
- **Multi-MB bundle exception (R8).** Any brief whose lane touches a bundle
  over ~1MB carries the chunked-read + mechanical-extraction mandate
  verbatim; a full read of multi-MB bytes thrashes the lane context and
  killed lanes in two different slices.
- **Budget-override note (R9).** A lane exceeding its stated request
  ceiling logs the reason mid-flight as a ledger row, not after the fact.
- **Merges through scripts (R10).** state.md / log.md appends go through
  `scripts/merge_append.py` (newline-glue guard, duplicate/tag refuse,
  ASCII guard, read-back echo) and post-write checks through
  `scripts/disk_verify.py` - never Edit-on-prose-anchor (state.md was
  corrupted twice the same way in one run) and no ad-hoc tick-count /
  cat -A ritual per write.

## N/A escapes

- `N/A: fewer than 2 disjoint rows (serial fallback per AGENTS.md)`
- `N/A: osint exhausted before first wave`
