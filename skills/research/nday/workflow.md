# nday workflow

Silent-patch detection and diffing:

1. Trigger: stage 4 finds a CVE fixed quietly, or version jumps with no
   advisory (compare vendor changelogs via wigolo).
2. Diff the versions (vendor diff, source map, or binary diff as available);
   isolate the fix commit; derive preconditions.
3. Output rows to `poc/<vhost>/version-research.md`; a candidate exploit goes
   to the dispatch-queue with the evidence row cited.

## N/A escapes

- `N/A: no silent patch signal this pass`
