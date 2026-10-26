# engage workflow

1. Entry preflight (see SKILL.md): active.md, scope.md, index freshness,
   inscope list.
2. Parallel launch: `Skill(workflow-brain)`. Never hand-execute the first
   recon yourself; the brain owns dispatch.
3. Mid-pass routing map: stage output -> next skill, exactly the
   active-workflow stage table. Consult it whenever between phases.
4. If the operator interjects a one-off ask: satisfy it, write the result to
   the state files via the brain (envelope), resume the stage.

## N/A escapes

- `N/A: ctf engagement (ctf tree routing applies)`
