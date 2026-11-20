# log.md event grammar (ASCII)

The contract for WRITERS (hooks, agents, lanes) and future readers. No parser beyond
what status.py already reads; this page is the vocabulary.

## Canonical event tokens (one per line, grep-able)

- `tool <name> ok|fail|blocked|cancelled|background` - one tool call's outcome
- `iter main <n>` / `iter sub <n>` - loop iteration markers (main agent / subagent)
- `retry <a>/<max> <kind>` - retry a of max, kind of failure (technical/environmental/conceptual/external)
- `hitl ask <id>` / `hitl decided <approve|reject|edit>` - operator decision points
- `[<lane>]` prefix at line start scopes a line to one lane
- `[lane->lane] <src> -> <dst>: <capture path> | <observable>` - one lane hands a
  proven intermediate result to a named follow-up lane; the receiving lane starts
  from the handed capture, never re-derives it (the shared-vs-private memory rule
  lives in Skill(delegate))
- `Ruling: <decision> - <why> - <cost if wrong>` - a mid-run judgment call the operator
  would rubber-stamp; lanes log it and keep going; closeout prints every `Ruling:` line.
- `fail:insufficient|disproven|capped` - the three outcome causes of a vector that
  did not confirm. Lane close blocks carry it inside the result line
  (`result: DEAD (<cause>) - <what happened>`). `insufficient` close blocks add an
  optional `objection: <why the signal was insufficient>` line - the next research
  pass on that pattern MUST seed its first query from it.
- `` `reclass: <id> discovery -> n-day (<source ref>)` `` - a freshness check
  found the finding already public (existing CVE, vendor advisory, upstream
  fix); it re-routes to n-day verification (nday gate) instead of a
  discovery/novelty claim. The reverse route (patch did not cover this
  instance) logs the same token with `n-day -> discovery`.
- `` `inject-attempt: <verbatim instruction text>` `` - fetched content (advisory,
  issue, write-up, diff) contained an instruction addressed to the agent; the
  lane recognized it as data, recorded it verbatim, and continued unaffected
  (the research skill's data-not-instructions clause). The source is tagged in
  the ledger entry.
- `` `memwrite: <target> <- <source kind> [clean|suspect|unchecked]` `` - one
  memory write (wiki-stage staging, ledger append, demote verdict) with its
  lineage. `<source kind>` is the P2 source vocabulary
  (`nvd|ghsa|osv|changelog|web|wiki|diff|eng`, where `eng` = observed live in
  this engagement/research run); the bracketed value is the inject-screen
  verdict at the write. Quarantined wiki candidates (`inject-suspect: true`
  frontmatter) stay in `wiki-candidates/` and are never promoted until the
  operator clears them.

## Lane timeline (the readable layer)

`[lane] <host> <lane-N> opened (...)` dispatch lines stay verbatim - the driver writes
them at lane-init and `lane_validate.py` reconciliation matches them against
`poc/<vhost>/lane-*/` dirs. The delegate dispatch format
(`- lane <name> ... SUCCESS = <obs> | tmux win <w> | capture <dir>`) is unchanged too -
`lane_validate.py` + drift-guard + status.py aging parse it.

On a lane's RETURN the main session appends one close block right after the lane's
opened line. A bare `[lane] ... closed (...)` one-liner is NOT enough: it buries what
the lane learned inside a parenthetical and the file reads as lifecycle noise. The
close block is the useful layer:

```
## lane-N close: <one-line goal label> (<skill>)
- goal: <what the lane set out to do>
- result: <COMPLETE|PARTIAL|DEAD> - <what actually happened, board rows touched>
- key finding: <the one thing the next reader must know>
- capture: poc/<vhost>/<lane-N>/
```

Keep the block ASCII, one bullet per label, angle-bracketed values backticked
(Obsidian-safe). `assumptions updated: ...` summary lines keep their existing role
(the threat-model gate greps them); dedupe repeated driver `opened` lines when
restructuring a log by hand, but never drop the one line per lane dir.

## Audit line convention (framework events)

`<TS> | <category> | <action> | <result> | <detail>`

category enum: scope, roe, tool, finding, lane, wiki, oob, cleanup. Hook telemetry
writers use this shape for their human-readable log.md lines; the JSONL telemetry
(`.events.jsonl`) stays as is (machine shape).

Imported external findings log `finding | import` with the row outcome counts:
`2026-11-16 | finding | import | ok | run-x: 5 rows, 3 new, 1 dupes, 1 fix | ingest/_imports/ |`
(the finding-import.py summary prints this line ready to paste; `fix-required` replaces
`ok` when rows were refused for missing fields).

## Render-side noise rules (any log tail / status reader)

- Drop heartbeat/diagnostic rows.
- Collapse consecutive duplicate lines by fingerprint (same event + same subject).

## Violation vocabulary (drift taxonomy)

- `hallucination` - a claim with no test behind it
- `gave-up` - blocked and not switched (incl. `gave-up-by-repetition`: same blocked
  conditions retried twice unchanged)
- `omission` - creds in hand, never sprayed/reused
