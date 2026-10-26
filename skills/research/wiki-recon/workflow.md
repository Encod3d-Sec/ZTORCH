# wiki-recon workflow

Starting-recon context layer:

1. Before dispatching any new attack-path lane: lex+vec query for the tech
   stack + each fingerprinted component; hyde for odd stacks.
2. Feed hits into the lane brief (known defaults, prior tells, playbook
   fingerprints); record the queries in the lane capture.
3. Extends playbook.json rows as patterns are learned.

## N/A escapes

- `N/A: first touch of an unknown stack with zero wiki coverage`
