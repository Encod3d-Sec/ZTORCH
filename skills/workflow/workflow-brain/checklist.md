# Checklist: workflow-brain
Workflow-Ref: {{WORKFLOW}}

## Wave open
- [ ] Driver status read @ {{vault_dir}}/state.md [rule:no_cell_contains="TBD"]
- [ ] Locked vhost confirmed or locked @ {{vault_dir}}/.paths.json [rule:contains_lane_id="{{ENG}}"]

## Wave close
- [ ] Lane strict-gate verified before done @ {{vault_dir}}/log.md [rule:contains_lane_id="{{LANE_ID}}"]
- [ ] Envelopes merged into state @ {{vault_dir}}/state.md [rule:no_cell_contains="TBD"]
