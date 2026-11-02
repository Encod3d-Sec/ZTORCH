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

## Render-side noise rules (any log tail / status reader)

- Drop heartbeat/diagnostic rows.
- Collapse consecutive duplicate lines by fingerprint (same event + same subject).

## Violation vocabulary (drift taxonomy)

- `hallucination` - a claim with no test behind it
- `gave-up` - blocked and not switched (incl. `gave-up-by-repetition`: same blocked
  conditions retried twice unchanged)
- `omission` - creds in hand, never sprayed/reused
