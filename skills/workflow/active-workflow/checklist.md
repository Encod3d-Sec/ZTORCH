# Checklist: active-workflow pass (Vhost: {{VHOST}})
Workflow-Ref: {{WORKFLOW}}

## Stage 0
- [ ] S0 caido project + identities @ ../../../ledgers/identities.md [rule:table_min_rows=1]
## Stage 2
- [ ] S2 js-lists present @ ../js-lists/api-endpoints.md [rule:all_exist="../js-lists/hidden-endpoints.md,../js-lists/tech-versions.md"]
## Stage 3
- [ ] S3 fuzz results logged @ ../js-lists/api-endpoints.md [rule:md_table_headers="method,path,params,auth_required,source_file"]
## Stage 4
- [ ] S4 version research @ ../version-research.md [rule:no_cell_contains="TBD"]
## Stage 5
- [ ] S5 dispatch queue cites rows @ ../dispatch-queue.md [rule:table_min_rows=1]
## Stage 6
- [ ] S6 RTL review recorded @ ../../../decisions.md [rule:contains_lane_id="{{LANE_ID}}"]
- [ ] S6 pass summary @ ../pass-1-summary.md [rule:no_cell_contains="TBD"]
