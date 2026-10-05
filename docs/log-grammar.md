# log.md event grammar (ASCII)

The contract for WRITERS (hooks, agents, lanes) and future readers. No parser beyond
what status.py already reads; this page is the vocabulary.

## Canonical event tokens (one per line, grep-able)

- `tool <name> ok|fail|blocked|cancelled|background` - one tool call's outcome
- `iter main <n>` / `iter sub <n>` - loop iteration markers (main agent / subagent)
- `retry <a>/<max> <kind>` - retry a of max, kind of failure (technical/environmental/conceptual/external)
- `hitl ask <id>` / `hitl decided <approve|reject|edit>` - operator decision points
- `[<lane>]` prefix at line start scopes a line to one lane
- `Ruling: <decision> - <why> - <cost if wrong>` - a mid-run judgment call the operator
  would rubber-stamp; lanes log it and keep going; closeout prints every `Ruling:` line.

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
