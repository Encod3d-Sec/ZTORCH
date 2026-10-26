# Checklist: fuzz
Workflow-Ref: {{WORKFLOW}}

- [ ] F1 wordlist exists @ ../js-lists/custom-wordlist.txt [rule:no_cell_contains="TBD"]
- [ ] F2 hidden endpoints probed @ ../js-lists/hidden-endpoints.md [rule:md_table_or_explicit_empty]
- [ ] F3 requests logged @ ../../../ledgers/_requests.md [rule:contains_lane_id="{{LANE_ID}}"]
