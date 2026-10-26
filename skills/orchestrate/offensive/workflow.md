# offensive workflow

The driver is the plan. `python3 scripts/offensive.py <cmd>`:

1. `index` then `board`: compile + write the 4a matrix. With a locked vhost,
   board scopes to it (~20 rows).
2. `next`: follow its output literally. Locked vhost prints a
   `LOCKED: <vhost> pass N` banner; only that vhost's rows are served.
3. `vhost lock/list/status/pass-done/unlock`: one-vhost-at-a-time lifecycle.
   Unlock refuses below 2 passes or without an RTL review in decisions.md.
4. `lane-init --vhost <host> --skill <name>`: scaffold a gated lane.
5. `done`: G1-G10 gates; G10 runs completion-gate --strict on the lane
   checklist and refuses on any failure.
6. Gates: G1 wiki-arsenal cell, G2 skill-fired, G8 tool-first, G10 strict
   checklist (new). Full list: SKILL.md.
7. `closeout`: triage -> evidence -> walkthrough -> learn -> engagement-retro.

## N/A escapes

- `N/A: unlocked global mode (pre-lock engagements)`
