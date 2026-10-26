# Checklist: js-extractor (Vhost: {{VHOST}})
Workflow-Ref: {{WORKFLOW}}

## Entry Gate
- [ ] Step 0.1 - js-discover manifest intact @ ../../../js/{{VHOST}}/manifest.sha256 [rule:sha256_pass]
- [ ] Step 0.2 - source ledger populated @ ../../../ledgers/source-ledger.md [rule:table_min_rows=1]

## Execution
- [ ] Step 2 - every first-party file read @ ../../../ledgers/source-ledger.md [rule:no_cell_contains="read: no"]
- [ ] Step 3 - API endpoints table @ ../js-lists/api-endpoints.md [rule:md_table_headers="method,path,params,auth_required,source_file"]
- [ ] Step 4 - hidden endpoints table @ ../js-lists/hidden-endpoints.md [rule:md_table_or_explicit_empty]
- [ ] Step 5 - third-party links @ ../js-lists/third-party-links.md [rule:md_table_or_explicit_empty]
- [ ] Step 6 - tech versions @ ../js-lists/tech-versions.md [rule:md_table_headers="tech,version,evidence"]
- [ ] Step 7 - sink tables written @ ../js-lists/sinks-dom.md [rule:all_exist="../js-lists/sinks-xss.md,../js-lists/sinks-sqli.md,../js-lists/sinks-cmdi.md"]

## Exit Gate
- [ ] Step 8 - requests logged with lane id @ ../../../ledgers/_requests.md [rule:contains_lane_id="{{LANE_ID}}"]
- [ ] Step 9 - custom wordlist @ ../js-lists/custom-wordlist.txt [rule:no_cell_contains="TBD"]
