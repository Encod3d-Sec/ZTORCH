# wiki-arsenal workflow (G1 source)

The gate-1 arsenal lookup:

1. Called with a tech/version row: query `wiki/payloads/` +
   `wiki/cheatsheets/` for the matching payload class (lex query on the tech
   name + vuln class).
2. Return the payload page names + the exact gadget lines into the lane
   output; the board's arsenal cell (G1) cites them.
3. Missing coverage -> note the gap for `wiki-gaps.py` at close-out.

## N/A escapes

- `N/A: no fingerprinted tech yet (pre-recon)`
