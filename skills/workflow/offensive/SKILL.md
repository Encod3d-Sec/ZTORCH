---
name: offensive
description: Autonomous offensive-engagement driver. Runs a pentest, bug-bounty programme, or CTF box end to end with no operator approvals - the deterministic driver (scripts/offensive.py) owns the coverage board, enforces the gates, and prints the exact next action (which Skill + which tool) every turn. Use when starting or resuming any offensive engagement, "work this target", "work this scope/CIDR", "root this box", "hunt this program", "own this host", or when handed a scope/IP/domain to reach an objective. Single agent, wiki-first, tool-first. Flavor is a --type pentest|ctf|bb flag.
---

# offensive

The driver is the plan. Run one command, do exactly what it prints, record the result, repeat. You
never decide the next move by hand and you never ask the operator - `scripts/offensive.py` computes
the cursor, walks the gates, and prints the single next action.

## The loop

```
python3 scripts/offensive.py --eng <name> next
python3 scripts/offensive.py --eng <name> note <row> --arsenal <slug>
python3 scripts/offensive.py --eng <name> done <row> --poc <img> --kind req   # | --kind burp|web | --dead | --park
```

`next` prints the row it wants worked and the exact Skill/tool to run. Do that. Then record the
outcome with `note` (arsenal card consulted) and `done` (closed with evidence, dead, or parked).
Re-run `next`. That is the whole cycle.

## Start / resume

1. `python3 scripts/offensive.py init <name> --type pentest|ctf|bb` - scaffolds `targets/<name>/`
   (state.md, scope.md, loot.md, Killchain.md, Deadends.md, oob.md, decisions.md, Approach.md).
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
- **G3 typed evidence.** `done --poc <img>` needs exactly one typed disposition: `--kind req|burp|web`.
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

## Autonomy

No approvals, ever. The driver is deterministic and self-directing: run `next`, do exactly what it
prints, record with `note`/`done`/`foothold`/`park`, repeat. Any decision you cannot make on the spot
is parked to `decisions.md` (G7) and the loop continues - you do not block on the operator.

## OPERATING REQUIREMENT (G2 depends on this)

G2 (skill-first) is only ENFORCED when two conditions hold:

1. The `tool-telemetry.py` PostToolUse hook is registered, so every `Skill(...)` call is appended to
   the active engagement's `.events.jsonl`.
2. Your `--eng` matches the ACTIVE engagement in `targets/active.md` - the hook writes to the active
   engagement's file, and the driver reads `.events.jsonl` under the `--eng` you pass. If they
   diverge, the driver looks in the wrong place.

If the telemetry file is absent, G2 **fails open** (advisory only): `next`/`done` allow the action
with a warning rather than blocking. So: keep the telemetry hook registered and keep `--eng` pointed
at the active engagement, or G2 silently degrades to advice. G1/G3/G4/G8/G9 do not depend on the hook.

## Close-out

Objective landed (target-severity finding, or both flags) -> set `## STATUS: SOLVED` in `state.md`,
then `python3 scripts/offensive.py --eng <name> closeout`. It prints the per-type Skill chain
(pentest/bb: triage -> evidence -> walkthrough -> learn; ctf: walkthrough -> learn). Run it in the
printed order; the chain lives only in `CLOSEOUT_CHAINS` (`scripts/offensive.py`) - don't restate it
elsewhere, ask the driver.

## If the driver is unavailable

Manual fallback: read `Approach.md`, take the top open row, run its arsenal lookup then its hunt
skill, capture typed evidence, mark `[x]`; on exhaustion write one `Deadends.md` line and mark `[!]`.
