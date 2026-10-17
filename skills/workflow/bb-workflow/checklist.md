# bb-workflow checklist

Copy this file to `$RUN/bb-workflow-checklist.md` at Stage 0, for THIS
host's run. `- [ ]` means not finished. Any unchecked box at stop = the
host's pipeline is not done; resume at the first unchecked box on the next
tick, never restart Stage 0.

## Entry

- [ ] Active engagement confirmed, scope.md read
- [ ] hunt-core lane discipline active
- [ ] Dispatch source confirmed: offensive.py/brain-dispatched | standalone single-host run
- [ ] bb-run.md row created for this host with per-stage budgets (defaults or operator-supplied); NO second board.md created (offensive.py state.md stays THE board)

## Stages

- [ ] Stage 1 - Surface mapping run (cheapest tool first: fuzz/browser before burp/caido before interceptor); bb-run.md updated
- [ ] Stage 2 - js-discover run, REVIEW passed; js-parser run, REVIEW passed; bb-run.md updated
- [ ] Stage 3 - Signal table applied; dispatch-queue.md written with class + corroborated signal(s) per row; bb-run.md updated
  - artifact check: every row in dispatch-queue.md has >= 1 signal listed; no class queued on a single low-confidence signal alone
- [ ] Stage 4 - Capped class list dispatched through offensive.py `next` / brain lanes (no parallel dispatch authority); each lane's own entry gate/checklist/REVIEW tracked independently; bb-run.md updated with classes run + leads found
  - artifact check: dispatched class count <= this host's Stage 4 cap, unless operator explicitly raised it
- [ ] Stage 4b - Retry ladder: every clean-miss class either closed as a deadend (boundary named) or retried once with a named pivot logged as `retry_of`/`pivot` in dispatch-queue.md - no retry with an unnamed or repeated pivot, no class retried more than the configured cap
- [ ] Stage 5 - Confirm/exploit run only for lanes that marked a LEAD (never speculative); bb-run.md updated with confirmed FINDs
- [ ] Stage 6 - Triage run, ranked finding set written; bb-run.md updated
- [ ] Stage 7 - Report drafted for confirmed FINDs only (N/A if none); bb-run.md updated
- [ ] Stage 8 - Closeout (learn + evidence) run; bb-run.md final row stamped for this host

## Budget discipline

- [ ] Any stage that hit its budget cap recorded a partial result + reason in bb-run.md (not a silent continuation)
- [ ] No stage exceeded its declared budget without an explicit bb-run.md note explaining why

## Exit / handoff

- [ ] bb-run.md row for this host is a complete terminal state (closed out | budget-exhausted | deadend)
- [ ] Control handed back to offensive.py `next` for the next pending host (or run ends, if standalone)
- [ ] Nothing written into skill dirs (skills/workflow/bb-workflow/ stays untouched)

## REVIEW (mandatory final step)

- [ ] REVIEW: every dispatched class in dispatch-queue.md traces to a corroborated signal
- [ ] REVIEW: bb-run.md and dispatch-queue.md agree on which classes ran and their outcomes
- [ ] REVIEW: no unchecked boxes above
