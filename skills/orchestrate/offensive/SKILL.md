---
name: offensive
description: Autonomous offensive driver - offensive.py owns the board, gates, and exact next action every turn. Use to start/resume any engagement, "work this target", "root this box", "hunt this program", or when handed a scope/IP/domain.
metadata:
  hermes:
    tags: [driver, orchestration, board]
    related_skills: [brain, engage, hunt-core, triage]
---

# offensive

The driver is the plan. Run one command, do exactly what it prints, record the result, repeat. You
never decide the next move by hand and you never ask the operator - `scripts/offensive.py` computes
the cursor, walks the gates, and prints the single next action.

## Wiki

Hub: [[methodology-moc]] - Primary page: [[multi-agent-campaign-orchestration]]
Anchors: [[pentest-methodology]]
**REFS:** [[multi-agent-campaign-orchestration]]

## The loop

```
python3 scripts/offensive.py --eng <name> next
python3 scripts/offensive.py --eng <name> note <row> --arsenal <slug>
python3 scripts/offensive.py --eng <name> done <row> --poc <img> --kind req   # | --kind burp|web | --dead | --park
```

`next` prints the row it wants worked and the exact Skill/tool to run. Do that. Then record the
outcome with `note` (arsenal card consulted) and `done` (closed with evidence, dead, or parked).
Re-run `next`. That is the whole cycle.

Auxiliary subcommands, when you need them: `plan` (dry-run top-N of `next`; writes nothing),
`autonomy` (set the advisory L0-L3 autonomy envelope in scope.md), `rebase` (re-point a rotated
asset value across the engagement). Two standalone CLIs, NOT subcommands:
`python3 scripts/status.py` (read-only board/cursor/spend banner - `next` burns a serve even
to look) and `python3 scripts/offensive-doctor.py` (one-shot seat health:
state/index/telemetry/RoE/board; exit 0 healthy / 1 sick). Raw ingest parsing is the
`ingest` skill's job, not a driver subcommand.

Precedence rule: when `plan`/next_move.py rankings and the driver's `next` cursor disagree,
the CURSOR governs - rankings are suggestions to feed into `note`/`done` reasoning, never an
alternative execution path.

Default posture (2026-09-08): once the board has 2+ open assets, run the loop under
`Skill(brain)` - the driver, gates, and board stay in the brain; each `next` action's
execution is dispatched to one of 2-3 concurrent disjoint-lane subagents per brain's
tier table. `next` prints a `PARALLEL` line when this applies. Plain single-agent
execution is the fallback below 2 open assets, not the default.

**Fresh-context wave pattern (bug-bounty / operator-AFK runs):** for discovery passes
the operator's standing posture is WAVES of fresh-context subagents (up to 5 concurrent,
re-dispatch any that die to rate limits) with each agent's context carrying ONLY scope.md
+ RoE + transport + evidence contract - deliberately NOT the Deadends/board history - so
they explore without the exhaustion bias; the main session (driver + triage) adjudicates
every returned lead against the deadend record itself. Lane themes that worked: per-surface
creative passes (gateway behaviors, auth flows end-to-end with disposable test accounts,
money-flow business logic stopped at the payment boundary). An authed lane that needs test
accounts should be dispatched to CREATE them; park dependent board rows on it
(`done <row> --park "consumes <lane>'s accounts"`) so the next wave consumes them.
Build each lane's context from `templates/lane-agent-context.md` (scope-first ordering,
b64 transport law, ethics ceilings, teardown-as-schema-field, verdict-per-surface).

Lane lifecycle discipline (per wave):
- Every authed lane ENDS with verified teardown (logout-all + token-replay 401 check as a
  schema field); an unverifiable leftover session becomes a hygiene task that rides along on
  the NEXT lane using that account - never left for the operator.
- Test accounts are engagement assets: record them in identities.md with the mailbox method
  (which disposable-email service actually delivers), and point follow-up lanes at the
  existing account instead of minting duplicates - registration flows burn rate budget and
  every new account is new RoE surface.
- Adjudicate every wave in one log.md entry (per lane: verdicts, corrections to prior
  deadends, follow-ups) so the Deadends/board stay the single machine-readable record -
  agent narratives live in agent-reports/<lane>/ only.
- A lane that disproves a prior deadend CORRECTS the deadend row in place ( reopen-if cell
  or evidence addendum) - a stale deadend that masks a live surface is worse than no
  deadend (single-shot PQNF verdicts are the canonical example).

## Start / resume

1. `python3 scripts/offensive.py init <name> --type pentest|ctf|bb` - scaffolds `targets/<name>/`
   (state.md, scope.md, loot.md, Killchain.md, Deadends.md, oob.md, decisions.md, Approach.md).
   decisions.md is scaffolded by init and self-created on demand by Skill(redteamlead) and
   `done --park`; both are true (either path works when the file is absent).
   Refuses a dir that already holds driver state (`.offensive.json`) -- re-init on a live
   engagement re-scaffolds over it; pass `--rebase` for the rotated-IP / repair flow (state
   file untouched, `targets/active.md` repointed).
2. `python3 scripts/offensive.py --eng <name> index` - compiles the vault routing table to `.offensive-index.json`.
   The board and gates read this cache; a stale one is refused by G9.
3. Feed recon into `state.md` (assets/services), then
   `python3 scripts/offensive.py --eng <name> board` - writes the Approach.md 4a coverage matrix from
   the index (one row per asset x vuln-class, each pre-loaded with an arsenal hint + tool + hunt skill).
4. Enter the loop. Pass `--eng <name>` on every command; keep it pointed at the ACTIVE engagement
   (see G2 below).

## --type: what the flag swaps

`--type` sets the engagement flavor and changes three things deterministically:

- **recon / base vuln-class set** seeded onto the board (`pentest` leans AD/Windows/host + web;
  `bb` is the broad web/API OWASP set; `ctf` is the lean foothold set).
- **close-out chain** the driver prints at the end (below).
- **4b post-ex classes** seeded after a foothold.

Pick it once at `init`; everything downstream follows from it.

## Vector workflow (board seeding)

`board` seeds 4a rows in a fixed order, not just the flat fingerprint+base union: an OSINT
pre-pass keyed to the engagement name, then per-asset fingerprint-implied classes, then that
asset's matched vector baseline(s) in **web > ad_windows > linux** priority (plus narrow
fingerprint-gated exceptions), then `BASE_CLASSES[etype]` fallback. Full mechanics:
`Skill(vector-workflow)`.

## Gates (enforced by the driver)

The driver ENFORCES these - `next` withholds an action until its gate is satisfied, and `note`/`done`
refuse (non-zero) on violation. You do not judge them; you satisfy them.

- **G1 arsenal-first.** No exploit action until the row has a consulted arsenal card. `next` emits
  `Skill(wiki-arsenal)`; release the gate with `note <row> --arsenal <slug>`.
- **G2 skill-first.** The mapped `Skill(hunt-*)` must have fired before the tool runs. `next` emits
  the skill; `done` refuses if it did not fire. (See the operating requirement below - G2 fail-opens
  when telemetry is unavailable.)
- **G3 typed evidence.** `done --poc <path>` needs exactly one typed disposition: `--kind req|burp|web|cli`
  (`cli` for a command-execution finding - RCE shell, AD dump, privesc - capture.sh's default PoC-card
  mode; `web` only for a class actually distinguishable in a rendered screenshot). The path must exist.
  `web` is only accepted for visual classes; an exploit request wants `req`/`burp`.
- **G4 deadend-first.** An exhausted vector is closed `--dead` (one Deadends.md line); the driver
  suppresses that (asset, class) pair from ever being served again. Never re-run a dead row.
- **G5 depth-first.** The cursor is sticky - it finishes the asset in progress before moving on,
  so you drive one host to exhaustion rather than skimming the whole scope.
- **G7 no-ask.** The driver never prints a question. An unresolved judgment call is deferred with
  `done <row> --park "<note>"`, which records it to `decisions.md` and moves on. You do the same:
  run `next`, obey, park what you cannot resolve, never stop to ask the operator.
- **G8 tool-first.** `next` emits the installed tool invocation (nmap/ffuf/nuclei/sqlmap/nxc/...),
  never a hand-rolled curl/`/dev/tcp` loop. Exploit-shaped rows also emit a Burp Repeater capture
  line so the load-bearing request is operator-visible.
- **G9 index-fresh.** `next` checks index freshness first and refuses on a stale routing table -
  re-run `index` if it complains.

## Post-foothold

When a shell lands, record it: `python3 scripts/offensive.py --eng <name> foothold <asset> --win <n>`
(or ride it on the closing find with `done <row> --win <n>`). The `--win` is the tmux window running
the session. The driver flips the asset to `access=foothold`. `foothold <asset> --win <n>` (or `done <row> --win <n>`)
seeds the 4b privesc/lateral rows (pspy/linpeas auto + the manual checklist) for that asset directly;
`board` only refreshes the 4a matrix. `next` then routes the post-ex work off those 4b rows. `coverage` shows any base class still untested per asset.

- At board time, list the attacks the scope implies that no board row exercises,
  cross-checked against the Approach.md 4a coverage table; a gap gets a row or a
  Ruling for why not.

## Autonomy

No approvals, ever. The driver is deterministic and self-directing: run `next`, do exactly what it
prints, record with `note`/`done`/`foothold`/`park`, repeat. Any decision you cannot make on the spot
is parked to `decisions.md` (G7) and the loop continues - you do not block on the operator.

The scope.md frontmatter carries a CAI-style `autonomy:` envelope (L0 passive-only, L1 active
non-destructive, L2 exploit attempts allowed, L3 full; missing = L2). It is advisory: `next` prints
the level in its banner and, at L0/L1 on an exploit-class row, one advisory line. It never blocks -
the RoE flags (`no_bruteforce`/`no_dos`/`passive_only`) remain the enforcement layer.

## OPERATING REQUIREMENT (G2 depends on this)

G2 (skill-first) is only ENFORCED when three conditions hold:

1. The `tool-telemetry.py` PostToolUse hook is registered, so every `Skill(...)` call is appended to
   the active engagement's `.events.jsonl`.
2. Your `--eng` matches the ACTIVE engagement in `targets/active.md` - the hook writes to the active
   engagement's file, and the driver reads `.events.jsonl` under the `--eng` you pass. If they
   diverge, the driver looks in the wrong place.
3. The mapped skill has a DESKTOP junction (`%LOCALAPPDATA%/hermes/torch-skills/<name>` -> the repo
   ring dir) - `skill_view`/Skill events can only fire for skills the desktop can see. A repo-ring
   skill without a junction fails G2 on every row it maps, forever. On repeated G2 refusals for a
   repo skill, check the junction set FIRST; after any skill-tree rework or new ring, re-run the
   junction sweep: `scripts/junction-sweep.ps1` under this skill (idempotent, junctions every
   `skills/*/*/SKILL.md` directory). Legacy Hermes GUI seat only -
   under the wsl claude cli seat, skills load straight from the repo ring, no
   junction exists or is needed; G2 condition 3 is N/A there and telemetry gate
   stays advisory.

If the telemetry file is absent, G2 **fails open** (advisory only): `next`/`done` allow the action
with a warning rather than blocking. So: keep the telemetry hook registered and keep `--eng` pointed
at the active engagement, or G2 silently degrades to advice. G1/G3/G4/G8/G9 do not depend on the hook.

## Close-out

Objective landed (target-severity finding, or both flags) -> set `## STATUS: SOLVED` in `state.md`,
then `python3 scripts/offensive.py --eng <name> closeout`. It prints the per-type Skill chain
(Run it in the printed order; the chain lives only in `CLOSEOUT_CHAINS`
(`scripts/offensive.py`) - don't restate it elsewhere, ask the driver.)

## Exit artifact

The driver's STATUS line (state.md `## STATUS:`) + the closeout chain above
are this skill's exit contract: a run is DONE when the chain the driver
printed has fired and STATUS reflects it - never on narrative.

## If the driver is unavailable

Manual fallback: read `Approach.md`, take the top open row, run its arsenal lookup then its hunt
skill, capture typed evidence, mark `[x]`; on exhaustion write one `Deadends.md` line and mark `[!]`.
