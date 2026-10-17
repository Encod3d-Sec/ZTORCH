# bb-uplift review ledger (consolidated + verified)

Date: 2026-10-17 | Branch: `bb-uplift` (off `main` @ `fec7ef9`)
Spec: `docs/superpowers/specs/2026-10-17-bugbounty-workflow-uplift-design.md`
Plan: `docs/superpowers/plans/2026-10-17-bugbounty-workflow-uplift.md`
(both gitignored working docs; this ledger is the tracked record)

Method: 5 read-only flash review agents (S1-S5), one slice each; every row
re-verified in the main session by reading the cited location before it got
a verdict. Verdicts: CONFIRMED (evidence holds) or REJECTED (evidence does
not; row stays recorded). Dedupe rule: first-claimed slice owns a row.

Baseline (main @ `fec7ef9`): pytest 548 passed / 0 failed (124.52s),
offensive-doctor 29 checks / 0 FAIL / 3 WARN, check-routing 0,
lint-wiki 0 hard (13 soft em-dash pages pre-existing), check-leaks clean.
Regression bar: nothing green turns red; doctor WARN deltas with daemon
state are non-regressions.

## S1: bb-workflow skill (fixed in batch F1)

| row | location | sev | verdict | disposition |
|---|---|---|---|---|
| S1-1 | bb-workflow SKILL.md PATHS block | - | REJECTED (as donor drift) | VMshare is real on this seat: both mounts verified (`/mnt/VMshare`, `Desktop/VMshare` with double-nested `<eng>/<eng>` trees); `js-discover` SKILL.md:19-25 documents the identical layout as "historical layout, keep it". Paths kept. |
| S1-2 | bb-workflow SKILL.md:7,128,250 + checklist.md:27 | STALE | CONFIRMED | F1: `engagement-retro` -> `learn` (4 spots). |
| S1-3 | bb-workflow SKILL.md:3,18 | STALE | CONFIRMED | F1: "~30 hunt-*" -> 39 (live count). |
| S1-4 | bb-workflow stage 6 `triage` ref | - | CONFIRMED exists | `skills/workflow/closeout/triage/` exists; routing kept, no fix. |
| S1-5 | bb-workflow SKILL.md:218 | COSMETIC | CONFIRMED | F1: hunt-ics gate named correctly (SAFETY hard-stop). |
| S1-6 | all other bb-workflow citations | - | CONFIRMED clean | every cited skill/file resolves. |

F1 scope deviation from the spec: the spec's pre-approved "repoint bb-workflow
PATHS" was invalidated by S1 + main verification (mounts exist, js-discover
shares the convention). F1 shrank to text-only ref fixes. This is the plan's
Task 4 branch (audit result), recorded here as required.

## S2: dispatch chain

| row | location | sev | verdict | disposition |
|---|---|---|---|---|
| S2-1 | orchestrate/offensive SKILL.md:35 | BROKEN | CONFIRMED | `ingest-recon` in argparse-free prose: offensive.py:1877-1928 registers index/init/board/next/plan/coverage/closeout/note/done/autonomy/foothold/rebase only; grep shows `ingest-recon` nowhere in scripts/. F2: delete clause (the `ingest` skill owns parsing). |
| S2-2 | orchestrate/offensive SKILL.md:37-39 | STALE | CONFIRMED | `status`/`doctor` are standalone CLIs (scripts/status.py, scripts/offensive-doctor.py), not subcommands. F2: same edit rewords to the real invocations. |
| S2-3 | scripts/next_move.py:211-213 | STALE | CONFIRMED | `sorted(set(...))` discards coverage-classes.json's declared priority order for the [gap] floor. F2: preserve file order, append unseen chain destinations. |
| S2-4 | scripts/next_move.py:365 | COSMETIC | CONFIRMED | gap floor iterates the union `base`, leaking pentest-only destinations (`lateral`, `privesc`) into bb gap nudges. F2: iterate `CLASSES[etype]` for the floor; union stays as normalization vocab. |
| S2-5 | scripts/playbook.json login-form row | STALE | CONFIRMED | `approach: [ctf, pentest]`, no bugbounty, on the core bb auth surface. F2: add `bugbounty`. |
| S2-6 | scripts/playbook.json upload-form + LFI rows | STALE | CONFIRMED | same mistuning; `file-upload`/`lfi` are in the bb checklist. F2: add `bugbounty` to both. |
| S2-7 | scripts/coverage-classes.json bb list | STALE | CONFIRMED | omits `api`/`secrets`/`cloud` though BASE_CLASSES["bb"] seeds api+secrets on every board. F2: insert per impact order. |
| S2-8 | offensive.py vs _engagement.py type vocab | COSMETIC | CONFIRMED | `bb` vs `bugbounty` asymmetry works as shipped (init writes `bb`, templates write canonical `bugbounty`). DEFERRED: normalization inside working hook/driver code is a behavior change with no runtime break today; recorded for a future pass. |
| S2-9 | orchestrate SKILL.md hermes metadata | COSMETIC | CONFIRMED | folded into the HERMES pattern below (S2-9 + S3-3 + S4-1 are one finding). |

Verified clean in slice: bb -> bugbounty type flow end to end (init `bb` ->
`_engagement` normalize -> next_move/template vocab), board seed, privesc
suppression, closeout chain, all 121 playbook fingerprints' approach values,
chains.json edges + gates, all cited scripts/skills exist.

## S3: hunt classes (39 skills)

| row | location | sev | verdict | disposition |
|---|---|---|---|---|
| S3-1 | all 39 SKILL.md `## Paths` VMshare blocks | BROKEN | REJECTED | Evidence claim "nonexistent Desktop/VMshare mount" is false: mounts verified (see S1-1). The blocks match js-discover's binding corpus convention (js-discover:31-32 carries the same "never in targets/" doctrine); the port review repointed Transport/cd anchors deliberately while leaving artifact locations. No fix. |
| S3-2 | 39 SKILL.md:3 description lines | STALE | CONFIRMED | text after the closing quote (invalid as strict YAML; picker renders quoted part only), and the AD experts carry the mapper's tail copy. Count: 39 files. F3: strip tails at the closing quote. |
| S3-3 | 39 SKILL.md:5 `hermes:` frontmatter key | COSMETIC | CONFIRMED | folded into HERMES pattern below. |
| S3-4 | hunt-xss family, 16 links / 7 files | STALE | CONFIRMED | `[[techniques/web/xss]]` lacks the `wiki/` prefix sibling links use. F3: add prefix. |
| S3-5 | hunt-ad SKILL.md:51,162 | COSMETIC | CONFIRMED | donor-lab subnet `192.168.1.x`. F3: genericize. |
| S3-6 | 19 hunt files `# seat side (Windows):` | COSMETIC | CONFIRMED | siblings say `(wsl)`; path given is the WSL spelling. F3: relabel. |

Verified clean in slice: cd/Transport anchors (all 38 vault-pointed), zero
HermesTORCH/session_search/engagement-retro tokens, all cited scripts (20),
wiki pages, Skill() targets (47 incl. triggers.json routes), references/
files, payload arsenals, 16 ESC pages exist.

## S4: surface + report chain

| row | location | sev | verdict | disposition |
|---|---|---|---|---|
| S4-1 | 12 surface SKILL.md `metadata: hermes:` | COSMETIC | CONFIRMED | HERMES pattern below. |
| S4-2 | interceptor SKILL.md donor-named tool tree | STALE | CONFIRMED (fact), fix REJECTED | tree exists and works; renaming risks the verified stack (NM host manifest, local-patches export, memory/script refs) for zero function. Keep. |
| S4-3 | js pair VMshare anchors | STALE | CONFIRMED (fact), fix REJECTED | intentional layout, same adjudication as S3-1. |
| S4-4 | closeout/learn SKILL.md:18,28 | COSMETIC | CONFIRMED | refs sit inside the deprecated donor block the seat-note (lines 8-13) already quarantines; `engagement-retro/` dir removal is an operator call (never destructive-delete). No fix. |
| S4-6 | learn SKILL.md:195-196, hunt-burp SKILL.md:24 (+ AGENTS.md) | STALE | CONFIRMED | cite `mcp__wiki-search__qmd_query`/`qmd_search`; live server exposes `query`/`get`/`multi_get`/`status`. F3: reword (incl. AGENTS.md, same drift). |
| S4-7 | hunt-burp SKILL.md:108 | STALE | CONFIRMED | `FIND-XXX-SEVERITY-<class>-<host>` vs the tree convention `FIND-NNN-SEVERITY-title` (page-types:115, TARGETS.md:26). F3: fix naming line. |
| S4-8 | disclosure SKILL.md:68 advisory path | COSMETIC | CONFIRMED (fact), no fix | research-skill flow saves to `raw/research/<project>/`; convention overlap, by design. |
| S4-9 | caido SKILL.md:293 | BROKEN | CONFIRMED | `vm.sh 'tee ...' < scripts/caido.sh` truncates the VM copy: vm.sh does not forward stdin (documented at browser/screenshot SKILL.md:111-113). F3: base64-into-command pattern. |
| S4-10 | js-discover SKILL.md:224-276 (Step 2b) | BROKEN | CONFIRMED | teaches the donor real-Chrome / `-Spider` / already-logged-in Interceptor model this vault's hook-enforced BROWSER LAW forbids; lines 255-259 only partially self-correct. F3: rewrite Step 2b to the Edge automation-instance stack. |
| S4-11 | js-discover SKILL.md:37-40 | STALE | CONFIRMED | donor Windows-seat `wsl.exe -d kali-linux -u root` transport (this seat: plain `bash scripts/vm-ssh.sh`); "lands as user tz (NOT root)" contradicted by vm-ssh.sh:13-27 (key-based root). F3: reword. |

Verified clean in slice: every cited script (zero missing), wiki page, and
Skill() name resolves; disclosure/walkthrough/learn/ingest engagement-path
claims match the `targets/<eng>/` schema and the closeout chain.

## S5: templates + hooks + docs

| row | location | sev | verdict | disposition |
|---|---|---|---|---|
| S5-1 | targets/TARGETS.md:23,35-36 | BROKEN | CONFIRMED | documents `coverage.md` + a `--with-coverage` flag that does not exist (script errors on unknown flags; coverage lives in the Approach.md 4a table per script L15-17 and _engagement.py:58-59). F4: delete row + mentions. |
| S5-2 | targets/TARGETS.md:80-82 | STALE | CONFIRMED | ctf paragraph names `Killchain.md` as the live home, contradicting lines 16/38 and the script. F4: reword to state.md `## Chain`. |
| S5-3 | targets/TARGETS.md:21 | STALE | CONFIRMED | `recon/` listed as scaffolded/self-healed; only `ingest/`+`poc/` are (STATE_DIRS). F4: annotate auto-created on first capture. |
| S5-4 | docs/page-types.md:97 | STALE | CONFIRMED | ctf upfront set includes `vuln-index`; script deliberately skips it (script L15-16). F4: remove. |
| S5-5 | docs/page-types.md:109 | STALE | CONFIRMED | "decisions.md is scaffolded by init and self-created on demand" self-contradiction; script L164-166: on-demand only. F4: drop "scaffolded by init and". |
| S5-6 | docs/page-types.md:113 | STALE | CONFIRMED | `hot.md` row in the engagement-file table; it is the framework-level session/hot.md. F4: drop row. |
| S5-7 | docs/page-types.md:115 | COSMETIC | CONFIRMED | `Vulns/` marked `(pentest)`; bb uses it too (TARGETS.md:26, close-out.py gate). F4: `(pentest/bugbounty)`. |
| S5-8 | docs/workflows.md:93 | STALE | CONFIRMED | "4a/4b coverage matrix"; the bb board has 4a/4c only (template grep). F4: "4a table (plus phase checklists)". |
| S5-9 | setup/templates/_scope.md:60-61 | STALE | REJECTED | the comment "exact in > exact out > parent out > parent in" MATCHES resolve_scope() (_engagement.py:628-640: out_any returns before in_any). The agent misread the branch order. No fix. |
| S5-10 | setup/new-engagement.sh:23-24 | STALE | CONFIRMED | header claims the script's set is self-healed; `identities`/`source-ledger`/`write-ledger` (+ `changelog`) are scaffold-only, absent from every heal set. F4: reword comment (adding heal entries would change hook behavior for no need). |
| S5-11 | docs/page-types.md:117 | COSMETIC | CONFIRMED | `scope/`/`reports/` read as scaffolded; TARGETS.md:33-35 says by hand. F4: add "made by hand when needed". |

Verified clean in slice: core file set agrees across script/heal
sets/templates on disk; bb state columns, oob table shape, Deadends header,
walkthrough stub markers match the hook parsers; all 33 hunt routes + all
non-hunt trigger routes live; all 18 registered hooks + every invoked
scripts/ file exist; 24 bb Approach wiki links resolve; zero donor tokens.

## Cross-slice patterns

- HERMES frontmatter key (S2-9 + S3-3 + S4-1, ~60 files): the
  `metadata: hermes:` nesting is the uniform schema key across the corpus;
  nothing in scripts/ or skills/hooks/ reads it programmatically (grep
  clean), so it is cosmetic donor naming only. DEFERRED as a vault-wide
  rename decision (wide diff, zero functional impact) for the operator.
- VMshare artifact convention (S3-1 + S4-3): intentional on this seat,
  documented by js-discover, mounts verified. Not donor residue.

## Batches (execution order)

- F1 (done, pre-approved): bb-workflow refs (learn x4, 39-count x2,
  hunt-ics gate) + checklist Stage 8. Commit: ledger + F1 together.
- F2 dispatch chain: S2-1/2 (offensive SKILL.md aux paragraph), S2-3/4
  (next_move.py order + gap-floor vocab), S2-5/6 (playbook approach tags),
  S2-7 (coverage-classes). Recheck: pytest + check-routing.
- F3 skill text: S3-2 (39 description tails), S3-4 (16 xss links),
  S3-5 (hunt-ad subnet), S3-6 (19 seat labels), S4-6 (qmd names + AGENTS.md),
  S4-7 (hunt-burp FIND naming), S4-9 (caido stdin), S4-10 (js-discover 2b),
  S4-11 (js-discover transport). Recheck: token greps + lint-wiki.
- F4 docs/templates: S5-1/2/3 (TARGETS.md), S5-4/5/6/7/11 (page-types.md),
  S5-8 (workflows.md), S5-10 (new-engagement.sh comment). Recheck: greps +
  lint-wiki.

## Close-out

Commits (branch bb-uplift, in order):

| batch | SHA | contents |
|---|---|---|
| F1 + ledger | `e022465` | bb-workflow ref fixes, this ledger |
| F2 | `b0a3876` | offensive SKILL aux paragraph, next_move order + gap floor, playbook bb tags, coverage-classes bb list |
| F3 | `c67dc88` | 55 files: qmd tool names repo-wide, description tails (see S3-2 amendment), xss links, seat labels, hunt-ad subnet, FIND naming, caido stdin, js-discover Step 2b + transport |
| F4 | `f56c3a1` | TARGETS.md / page-types.md / workflows.md / new-engagement.sh header |
| battery fixes | `58632ac` | S3-2 tail restore, port-ledger client-name scrub |

Final battery (bb-uplift @ `58632ac`): pytest 548 passed / 0 failed
(128.10s), offensive-doctor 29 checks / 26 PASS / 3 WARN / 0 FAIL (WARNs
are the known daemon-state trio, non-regression), check-routing 0,
lint-wiki 0 hard, check-leaks hard gate clean (advisory WARNs pre-existing).

Amendments recorded at close-out:

- **S3-2 REVERSED.** The description tails stripped per this table broke
  `tests/test_hunt_use_when.py` (the line must end unquoted `.` with the
  use-when clause in its back half; the tails are also picker text). The
  post-quote tail is the repo's intentional description format - the
  loader tolerates it. All 39 description lines restored verbatim from
  `b0a3876` in `58632ac`; every other F3 change kept. Lesson: a
  description-line edit is a contract edit, run the hunt tests before
  committing it.
- **S4-6 widened by recheck.** The dead `qmd_query`/`qmd_search` names
  were repo-wide (~45 more sites beyond the slice's 3 files: hunt
  wiki-first blocks, research/workflow/platform skills, skill-map,
  workflows, surface template). Fixed in F3 for all tracked `.md`
  instruction sites. Deferred (follow-on pass): the same names inside
  `skills/hooks/recon-capture.py` + `scripts/research_status.py` nudge
  strings (path corrected: the capture hook lives under `skills/hooks/`),
  `scripts/wiki-promote.py` docstring, and two `scripts/playbook.json`
  test strings - runtime strings, possibly test-referenced, zero agent
  routing impact.
- **Baseline correction: check-leaks.** The baseline line above said
  "check-leaks clean"; at battery time the hard gate FAILED on 5 client
  engagement names inside `docs/port-2026-10-17/` ledgers - byte-identical
  on main @ `fec7ef9`, i.e. pre-existing and missed at baseline. Scrubbed
  in `58632ac` (names live in `targets/` only). Branch is clean relative
  to a corrected baseline: nothing that was green turned red.
