# Framework Proposal Registry

Standing registry of framework mechanisms proposed but not built (the
"proposed-not-built" ledger from the 2026-11-01 framework-effectiveness pass,
`docs/superpowers/specs/2026-11-01-framework-effectiveness-design.md`, WS8).

**Doctrine (binding):** every retro sweep updates this registry. Any item
reaching 2 recurrences gets scheduled; 3 forces it into the next improvement
pass. A row taken by a landed pass moves to the dedup note at the bottom with
the commit that closed it; it never silently disappears.

Threshold status legend: `parked 1/2` = proposed once, waiting for a second
recurrence; `scheduled 2/3` = at threshold, plan a slot; `FORCED` = recurrence
bar met, must land in the next improvement pass unless the operator rules it out.

| proposal | what | where recorded | date | recurrences | threshold status |
|---|---|---|---|---|---|
| qmd repo apply | Ready-to-apply changes to the external qmd source repo (Phase 2.2 + 3 of the retrieval pass); plan document complete, execution pending against `/root/qmd` plus reindex + battery | `docs/superpowers/plans/2026-07-21-qmd-retrieval-followup.md` | 2026-07-21 | 1 | parked 1/2 |
| analysis engagement type | `init --type analysis`: a board with no attack-surface seeding and no streak counting on N/A closes (DFIR-style rooms); the dry-streak exemption (WS3) landed, the full type did not | `docs/superpowers/harness-retro.md` (2026-09-05, 2026-09-06 rows; also research-retros I2) | 2026-09-05 | 5 | FORCED (met the 3 bar 2026-09-06) |
| vhost prelock | A `prelock` state admitting lanes to queued vhosts without advancing the pass counter; operator-directed run-ahead cannot be board-represented today | `docs/superpowers/plans/2026-11-01-framework-effectiveness/research/research-retros.md` (I14) | 2026-10-26 | 1 | parked 1/2 |
| parser consolidation (F18) | Five markdown table parsers with divergent ragged-row behavior (`_parse_table`, `_parse_table_text`, `_engagement._parse_table`, `completion-gate._md_tables`, two inline cell-splitters); consolidate into one parser with warnings | `docs/superpowers/plans/2026-11-01-framework-effectiveness/research/research-driver.md` (F18) | 2026-11-01 | 1 | parked 1/2 |
| prose contract lint (C5) | A lint that catches doc/skill text drift vs the live tree (subcommands, flags, paths, names that do not exist); C5 is the densest recurring failure class across both 2026-10-17 review ledgers; extendable to string literals in scripts (I6) | `docs/superpowers/plans/2026-11-01-framework-effectiveness/research/research-retros.md` (C5) | 2026-10-17 | 2 | scheduled 2/3 |
| transport contract (C4) | A seat-layer transport contract for the WSL/Windows/VM plumbing (stdin forwarding, interop routing, silent-failure signaling); the same stdin-truncation class recurred 2026-06-30 and 2026-10-17 | `docs/superpowers/plans/2026-11-01-framework-effectiveness/research/research-retros.md` (C4) | 2026-06-30 | 2 | scheduled 2/3 |
| HERMES rename | Vault-wide frontmatter rename of the donor-era `metadata: hermes:` schema key (~60 files); zero functional impact, mechanical, rides the next skills-tree pass | `docs/bb-uplift-2026-10-17/review-consolidated.md` | 2026-10-17 | 1 | parked 1/2 |
| doc split vault-vs-root | The same doc set exists in two repos (vault tree and `/root` repo) and citations drift between them; pick one home or add a sync check | `docs/superpowers/plans/2026-11-01-framework-effectiveness/research/research-retros.md` (class 5 note) | 2026-11-01 | 1 | parked 1/2 |
| per-seat MCP drift (wiki-search provisioning) | skill-map dispatches `mcp__wiki-search__query` but that MCP is provisioned per-seat by bootstrap; seats without it silently lose the documented dispatch | `docs/superpowers/plans/2026-11-01-framework-effectiveness/research/research-wiring.md` (per-seat MCP drift) | 2026-11-01 | 1 | parked 1/2 |
| remaining single-proposal retro items (I19) | The assorted once-proposed helper gaps (PowerShell delivery helper, recon time-box pivot, vm-scan quoting, sqlmap stdin advisory, proxy-advisory on mutating POSTs, seat VM preflight, and the rest of the I19 list); each parked until it recurs individually | `docs/superpowers/plans/2026-11-01-framework-effectiveness/research/research-retros.md` (I19) | 2026-09-08 | 1 each | parked (per-item 1/2) |

## Closed by later passes (dedup)

| proposal | closed by |
|---|---|
| driver append guards, lane-to-board binding, advisory fingerprint-dismiss pool, in-process helpers, verify-layer contracts, coverage wiring, strix absorption, board-staleness doctor check | the 2026-11-01 framework-effectiveness pass (WS1-WS7 + WS8 doctor check) |
