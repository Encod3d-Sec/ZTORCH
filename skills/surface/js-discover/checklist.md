# Checklist: js-discover
Workflow-Ref: {{WORKFLOW}}

- [ ] J1 corpus manifest @ ../../js/{{VHOST}}/manifest.sha256 [rule:sha256_pass]
- [ ] J2 beautified tree @ ../../js/{{VHOST}}/beautified/external [rule:dir_count_matches=../../js/{{VHOST}}/raw/external]
