# Checklist: interceptor
Workflow-Ref: {{WORKFLOW}}

- [ ] T0 stack up: `bash scripts/interceptor-automation.sh up` + INTERCEPTOR_CONTEXT pinned, 19222 ESTABLISHED (WAKE LAW)
- [ ] T0b every host to visit verified in-scope in scope.md BEFORE any click
- [ ] T0c ONE managed tab: `open <url> --reuse --group <lane-label>`; own tab id recorded from `targets`
- [ ] T0d `INTERCEPTOR_PAGE=<own-tab-id>` pinned for every cdp eval/dom/netwatch (multi-tab refusal = exit 4)
- [ ] T1 session exported @ captures/export-curl.txt [rule:no_cell_contains="TBD"]
- [ ] T2 identities row @ ../../../ledgers/identities.md [rule:table_min_rows=1]
- [ ] T3 overlays dismissed BY CLICKING before any page read (POPUP LAW)
- [ ] T4 capture pair: netwatch JSONL (bodies, ground truth) + `net log` HAR drained and reconciled
- [ ] T5 teardown plan noted (logout-all + verify, or user-data-dir disposable)
