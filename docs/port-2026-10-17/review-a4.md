# A4 review: documentation + wiki pointer consistency (port 7ffe4c9)

Total 19 findings: 17 BROKEN, 1 INTENTIONAL, 1 UNCLEAR. Biggest risk: the wholesale skills/ mirror silently deleted ZTorch's vendored caido-mode SDK CLI (21 files, donor lacks it); every caido command in the skill, the wiki page, and skill-map still points at the now-missing directory. Second: the ported walkthrough skill and the harness disagree on the close-out chain (engagement-retro vs learn), and learn's Hermes deprecation banner is now operative against a harness that mandates learn.

Method: read-first pass over docs/skill-map.md, docs/auto-triggers.md, docs/layout.md, docs/conventions.md, docs/page-types.md, docs/setup.md, docs/sharing.md, docs/workflows.md, docs/virtual-machine.md, AGENTS.md, README.md, skills/skills-setup.md, skills/report/disclosure/SKILL.md, skills/report/walkthrough/SKILL.md, skills/workflow/closeout/learn/SKILL.md; grep used only to locate `skills/` path references across docs/, AGENTS.md, README.md, wiki/ (6 wiki hits, all read in context); every candidate path then verified against the live tree; diffs taken against commit `7ffe4c9^` (pre-port) and the HermesTORCH donor for provenance; wiki-gaps.py run live.

| File | Line | Class | Evidence (verbatim) | Proposed fix |
|---|---|---|---|---|
| skills/surface/caido/SKILL.md | 17 | BROKEN | `1. **caido-mode CLI** (primary API surface): vendored at `skills/surface/caido/caido-mode/`` | Restore caido-mode from git history: `git checkout 7ffe4c9^ -- skills/caido/caido-mode` then move under skills/surface/caido/ (21 files incl. caido-client.ts, lib/, package.json; donor HermesTORCH has SKILL.md only, so the wholesale replace dropped ZTorch's vendored copy; adapt-log-sa3 marked surface/caido "copy whole" with no notice; L49, L90 ("git carries" it - it no longer does, deleted in 7ffe4c9), L129 all depend on it; scripts/caido.sh L5/L14 still cite the old `skills/caido` path) |
| wiki/tools/caido.md | 28, 47 | BROKEN | `cd skills/surface/caido/caido-mode && npx tsx caido-client.ts search 'req.host.cont:"example.com"' --compact   # SDK CLI, seat-side` | Same restore as the skills/surface/caido/SKILL.md row; the two command blocks on this page are dead until the vendored dir exists |
| docs/skill-map.md | 70 | BROKEN | `Standalone: `wiki/`, `research/`, `disclosure/`, `caido/` (headless Caido driver; caido-mode SDK CLI vendored + helper `scripts/caido.sh`)` | After restoring caido-mode this line is half-true; rewrite the whole Vault-local skill layout block (L52-72) to the new tree |
| skills/report/walkthrough/SKILL.md | 28 | BROKEN | `AGENTS.md execution loop runs `Skill(walkthrough)` (then `Skill(engagement-retro)`).` | Revert to `Skill(learn)`: AGENTS.md L64, scripts/offensive.py L79-81 closeout chains, skills/hooks/close-out.py L422-426, and docs/auto-triggers.md L38 all say walkthrough then learn; nothing in AGENTS.md/offensive.py/close-out.py names engagement-retro |
| skills/workflow/closeout/learn/SKILL.md | 3, 8-22 | BROKEN | `DEPRECATED on Hermes - use Skill(engagement-retro) plus Hermes-native memory instead.` + `Cross-session facts -> Hermes `memory` tool` + `"Have we hit this before" -> Hermes `session_search`` | Annotate the banner for this seat the way adapt-log-sa4 did for engagement-retro (Phase 0 -> Skill(engagement-retro), memory -> project memory/CLAUDE.md, session_search -> transcript recall): the harness still mandates this skill (close-out.py calls the chain "not optional", offensive.py ships it) while the file says do-not-run and routes to Hermes-only tools that do not exist on the wsl claude cli seat |
| docs/skill-map.md | 56-58 | BROKEN | ``skills/workflow/` holds the two engagement entry points at its root, `offensive` (the driver) and `engage` (the router), plus `brain` (subagent dispatch mode over the driver)` | Reword: offensive/engage/brain live in `skills/orchestrate/`; skills/workflow/ holds bb-workflow, closeout/, ctf/, nightmare, recon/ |
| docs/skill-map.md | 61 | BROKEN | `- `closeout/` -- `triage`, `evidence`, `learn`, `walkthrough`` | Actual skills/workflow/closeout/: engagement-retro, evidence, learn, triage; walkthrough moved to skills/report/walkthrough |
| docs/skill-map.md | 62 | BROKEN | `- `recon/` -- `wiki-recon`, `nday`, `research-ingest`, `wiki-arsenal`, `ingest`` | Actual skills/workflow/recon/: ingest, research-ingest; wiki-recon, nday, wiki-arsenal moved to skills/research/ |
| docs/skill-map.md | 63 | BROKEN | `- `exec/` -- `delegate`, `metasploit`, `redteamlead`, `fuzz`` | Actual skills/exploit/exec/: delegate, metasploit, redteamlead (no fuzz; fuzz is skills/surface/fuzz) |
| docs/skill-map.md | 65 | BROKEN | `- `env/` -- `kali-seat`, `chrome-devtools-browser`, `screenshot`` | No env/ dir exists: kali-seat is skills/orchestrate/kali-seat; chrome-devtools-browser and screenshot are skills/surface/browser/ |
| docs/skill-map.md | 56, 70-71 | BROKEN | `(not a loop step), promoted to its own top-level directory` + `Standalone: `wiki/`, `research/`, `disclosure/`, `caido/`` + ``agents-md-improver/` is the offline instruction-file reviewer` | Nothing in skills/ is standalone top-level anymore: platform/wiki, research/research, report/disclosure, surface/caido, platform/agents-md-improver; vector-workflow is nested under surface/ |
| docs/layout.md | 52-63 | BROKEN | ``skills/`                      <- wiki/ research/ disclosure/ agents-md-improver/ (offline instruction-file reviewer)` + ``hunt/`                    <- hunt-* vuln-class skills (27) + hunt-core (shared discipline) + triggers.json`` + ``workflow/`                <- offensive (driver) + engage (router) + brain (subagent dispatch) + nightmare ... at root`` | Whole skills/ block (L52-63) describes the pre-port tree: no top-level hunt/ (now exploit/hunt with 39 dirs + triggers.json), no vector-workflow/ top level, no burp/ top level, no env/; closeout/recon/exec lists stale as in the skill-map rows; redraw from the live tree (exploit/ orchestrate/ platform/ report/ research/ surface/ workflow/ + hooks/ + skills-setup.md) |
| AGENTS.md | 100 | BROKEN | ``skills/` (hunt/ workflow/ burp/ + standalone + hooks/)` | Update the top-level listing to `exploit/ orchestrate/ platform/ report/ research/ surface/ workflow/ + hooks/` |
| README.md | 82 | BROKEN | `skills/      hunt-* (one per vuln class), vector-workflow/, workflow/ (the offensive driver + process skills)` | Update to the categorized tree; the offensive driver is orchestrate/offensive, hunt-* is exploit/hunt/hunt-* |
| docs/auto-triggers.md | 89 | BROKEN | `51 triggers total (37 vuln-type + 14 attack-surface).` | Update to 56 total (39 vuln-type + 17 surface): the port swapped in the Torchv2 superset triggers.json but left the old count; verified with the doc's own recount command |
| skills/skills-setup.md | 19, 24 | BROKEN | `"env": { "QMD_VAULT": "/mnt/c/Users/{user}/Documents/ObsidianVaults/ZTorch" }` (L52 on the same page spells it `ObisidianVaults`) | Fix the spelling to `ObisidianVaults` (the real directory name); the L19 config example points at a nonexistent dir; pre-existing (skills.bak provenance, not port-introduced) |
| skills/skills-setup.md | 112-142 | BROKEN | `## Third-party skill intake (hard rule)` appears twice, verbatim (L112-125 and L129-142) | Delete one copy; pre-existing duplication carried through the port untouched (SA5: "no diff") |
| skills/report/disclosure/SKILL.md | 4-7 | INTENTIONAL | `metadata:\n  hermes:\n    tags: [disclosure, cve, cna, timeline]` | Keep: inert YAML metadata namespace, adapt-log-sa1 documents the decision ("Left unchanged (verified non-breaking)"); same block in skills/report/walkthrough/SKILL.md L4-7 |
| skills/report/walkthrough/SKILL.md | 123-124 | UNCLEAR | `A ` - `/`-` in prose is replaced with a comma, semicolon, colon, or a rewrite` | The em-dash/en-dash example glyphs render as plain hyphens, so the two examples are identical and the rule is self-referential; same mangling in skills/report/disclosure/SKILL.md L50 (`NO em-dashes (- or -) anywhere`); inherited verbatim from the donor (HermesTORCH copies show the same bytes), so either fix both glyphs upstream-and-here or accept as-is |

## Task 5 note: report-category skills

Both read end-to-end. ZTorch mechanics survived the port (these are ZTorch versions enriched with Torchv2 additions, not donor replacements): walkthrough keeps `scripts/capture.sh ev`, `scripts/build-walkthrough.py`, `poc/` + `poc/scripts/` conventions, the PoC-as-.md-with-fence rule, and the Skill(screenshot)/Skill(evidence) handoffs; disclosure keeps the ZTorch body and gains the Torchv2 report-shape bar. No find-lint gate was lost because neither pre-port file referenced find-lint.py (the gate lives in evidence/AGENTS.md). The only wiring defect is the walkthrough close-out chain row above.

## Task 4: wiki-gaps.py raw output

Run from vault root, `python3 scripts/wiki-gaps.py` (RC=0):

```
active-directory-certificate-esc-attacks
active-directory-certificate-services
active-directory-gpo
aws-identity-access-management
azure-attacks
cicd-azure-devops
cookie-attacks
hardcoded-secrets-enumeration
hash-overpass-the-hash
hash-pass-the-key
internal-kerberos-relay
kerberos-tickets
network-pivoting-techniques
network-pivoting-tools
reverse-shell-cheat-sheet
source-code-analysis
x
```

Attribution (`-v` run): all 17 resolve to archived FIND/cmdlog files under `targets/` (thm_juicy, thm_moebius, thm_gla, thm_precision 1, THM_Exam, one client engagement). Zero are cited by any ported skill (grep over skills/ for each slug: no hits), so per the task rule none produce BROKEN rows; they are pre-existing stale wikilinks in git-ignored client dirs.

## Verification notes

- All other `skills/` path references checked out valid: skills/exploit/hunt/triggers.json (AGENTS.md L33, docs/auto-triggers.md L10/L89, docs/conventions.md L29, docs/workflows.md L55), skills/hooks/ incl. eng-ckpt.py and zg-nudge.py, skills/platform/caveman/ and graphify/ (docs/setup.md), skills/surface/burp/ (docs/setup.md L112), wiki/tools/caido.md L15/L54, wiki/tools/zvec-grep.md L45, README.md L52.
- Name-only skill mentions in AGENTS.md/page-types.md (engage, offensive, brain, redteamlead, delegate, metasploit, hunt-burp, caido, kali-seat, learn, triage, evidence, wiki-recon, wiki-arsenal, nday, ingest, research-ingest, nightmare, fuzz, graphify, wiki, disclosure) all resolve to basenames in the new tree.
- docs/skill-map.md task rows L11-49 all reference existing skills/scripts; the stale content is confined to the Vault-local skill layout section.
- docs/conventions.md, docs/page-types.md, docs/setup.md, docs/sharing.md, docs/workflows.md, docs/virtual-machine.md: no stale skills/ paths beyond those tabled.
