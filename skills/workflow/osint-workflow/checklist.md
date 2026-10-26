# Checklist: osint-workflow lane ({{LANE_ID}})
Workflow-Ref: {{WORKFLOW}}

## Archive lane
- [ ] A1 historical URL table @ ../../osint/wayback-urls.md [rule:md_table_headers="url,year,source"]
## Infra lane
- [ ] I1 infra intel table @ ../../osint/infra-intel.md [rule:table_min_rows=1]
- [ ] I2 findings page @ ../../osint/osint-findings.md [rule:no_cell_contains="TBD"]
## Fan-in
- [ ] F1 classification rows proposed @ ../../lists/outscope-3rdparty.md [rule:md_table_or_explicit_empty]
- [ ] F2 requests logged @ ../../ledgers/_requests.md [rule:contains_lane_id="{{LANE_ID}}"]
