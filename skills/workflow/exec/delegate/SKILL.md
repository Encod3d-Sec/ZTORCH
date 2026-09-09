---
name: delegate
description: Sub-agent hand-off for a fully-specified exploit/escalation run, behind a false-root guardrail, main agent stays on strategy. Use for "delegate", "hand this to a sub-agent", "spin a flash", or foothold + working vector found.
---

# Delegate: sub-agent exploit-run

Hand a fiddly, fully-specified exploit-compile or escalation run to a cheap sub-agent so the main
agent stays on strategy and the board.

## When to delegate / when NOT

Delegate when a foothold plus a WORKING escalation vector is identified, or the step itself is a
fiddly fully-specified multi-step compile/run: compile a C PoC, deliver and run an ELF, drive
`su`/`sudo`/`screen -r`, msfvenom + `multi/handler` catch. Keep on the main agent: recon, judgement-
heavy vector selection, anything not fully specified. An unconfirmed vector is not a delegation, it
is a guess wearing a checklist.

## Model choice

(Pin a tier via your Agent tool only if your ZCode build exposes per-agent model selection;
otherwise the tier guidance below still tells you WHAT to hand off.)

the CHEAP TIER (glm-5.3-flash) is the DEFAULT for a fully-specified mechanical or wait-heavy run: compile-and-run a known
exploit, deliver an ELF, decrypt a credential store, a pspy/tcpdump watch window, a fixed-payload
flag-read. On CTF and RoE-approved pentests the safety bar for a cheap model executing an exploit is
already cleared, so lean into the cheap tier there and keep the main model on strategy. Step UP to the mid/high tier
only for a genuinely judgement-heavy multi-step run (a JS-heavy per-route-CSRF authed backend RCE).

NEVER delegate DISCOVERY or judgement to a cheap model: route/endpoint/token discovery, "is this
surface empty or am I querying it wrong", vector selection. A cheap model hardens a wrong negative
into a fact -- it reports "empty/dead" from a query mistake and you inherit it as a hard exclusion (a
real miss: a delegated agent called a UCP voicemail "empty" because it hit the AJAX endpoint, not the
dashboard widget that rendered the secret; that fossilized into a wrong "rabbit hole" and cost an
hour+). If the run is not fully specified, it is not a delegation, it is a guess wearing a checklist,
keep it on the main model. Re-verify any NEGATIVE a sub-agent returns before it becomes a Deadend.

## The checklist (a delegation is only as good as its checklist)

Every delegation needs all eight slots filled. Under-specify one and the sub-agent flails; that is the
usual failure mode, not a weak sub-agent.

- **(a) confirmed access/primitive**, spelled out; don't make the sub-agent rediscover it. Alongside
  the primitive, state the assumption set: what must hold true for the run to make sense (access
  still valid, file still at that path, version match); a wrong assumption then surfaces as a
  reportable mismatch, not a silent miss.
- **(b) exact copy-paste commands**, real IPs/paths inline, no `$VAR`; the sub-agent cannot watch a
  live terminal to sanity-check a substitution. Each command block pairs with its expected
  observable, step -> verify form, so drift is caught at the step, not at lane end. Lane code
  discipline: code the lane writes is minimum-code (stdlib / platform-native first, no frameworks,
  no scaffolding for later); the lane never improves target code beyond its checklist and flags
  anything unrelated it notices in the report instead of acting on it.
- **(c) egress/port constraints**, an egress-tested LPORT, not a guess at 4444.
- **(d) the false-root guardrail** (next section), non-negotiable.
- **(e) fragile-box discipline** if applicable: serial requests, long timeouts, no fuzzers.
- **(f) report-back contract**: return the primitive/creds/flag plus evidence path; REVERT any state
  the run changed (a group membership added, a registry key set) before reporting back; do not pivot
  further without the main agent. Structure the return as the lane envelope: Scope (what was
  attempted) / Result (verdict + the raw observable) / Key files (capture paths) / Issues
  (blockers). The main model writes `SUCCESS = <exact observable>` into the
  prompt BEFORE dispatch (for example: `hostname` = the target AND `id` = the expected uid, plus
  the session log path); the lane returns that observable RAW plus the capture path.
  For investigation (not fully-specified-run) dispatches, the prompt also carries a
  REQUIRED-OUTPUT list naming which commands' full output the envelope must append, and a
  claim budget (Result verdict <= 150 words) so the claim cannot bury the evidence. Stats in
  the envelope (commands run, duration) are computed by the MAIN agent from the capture dir,
  never self-reported by the lane. A lane that produced nothing returns an explicit
  `no output captured` marker, never silence. Terminal-status-first: the lane writes its
  status + raw output into the capture dir BEFORE any post-processing, so a lane killed
  mid-analysis still leaves the raw evidence on disk. Lane ownership: a lane NEVER edits a
  shared file (state.md, a wiki page) in place; a change to a shared file comes back as a
  paste-able diff block in the envelope that the main agent reviews and applies.
- **(g) anti-give-up + no-guess**: run the FULL specified window (a 5-minute pspy watch is 5 minutes,
  not 2); if blocked, report the RAW output/errors and STOP, never guess or substitute a value and
  never invent a result. The lane runs until the (f) criterion holds or the specified window
  expires, and reports raw output either way; a narrative verdict without the observable is the
  existing forbidden guess. A cheap model's instinct is to quit early and guess a token/flag, forbid
  both explicitly in the prompt.
- **(h) output-landing contract**: every load-bearing command's full request+response
  lands in the lane's capture dir (VM `/home/tz/<eng>/<lane>/` via `tee`, or
  `targets/<eng>/poc/<lane>/`); evidence-worthy tool runs execute inside a named tmux
  window (`vm-scan.sh --win <lane>` / `vm-bg.sh` / `vm-rsh.sh --create --win <lane>`),
  never foreground one-shot SSH; confirm-worthy request/response pairs are returned RAW
  so the main agent can push them to Burp Repeater. A lane that returns only a one-line
  verdict with no capture path is a failed lane.

Every delegation prompt also carries the read-first mandate verbatim: `cat each file in full, zg/grep only to locate`. A cheap model grep-mines by default; the prompt is its only law.

## False-root/hostname guardrail (MANDATORY every delegation)

A returned `uid=0`/root (Linux) or `nt authority\system` (Windows) is trusted ONLY if `hostname`
matches the target AND the expected uid holds.
Otherwise the shell died back to the Kali box, which runs as root; `$(...)`/backticks there substitute
LOCALLY, the false-RCE trap. The fix is re-pop, not celebrate. The sub-agent MUST report `hostname`
alongside any `id`/`whoami` output, every time, no exceptions.

## Main-agent discipline

Keep driving the board while the sub-agent works. Dispatch ONE sub-agent at a time, serial; never
duplicate its target in parallel. Before dispatch, append one lane line to `targets/<eng>/log.md`
(`- lane <name> in flight: SUCCESS = <observable> | tmux win <win> | capture <dir> | handle <agent-id>`)
so a compaction mid-lane re-surfaces it via the log's newest block AND the lane's agent handle
survives the compaction (the `Resume with context` rule needs it); on return, close the line with the
result. WAIT for completion before the next move. On return, persist the
primitive/creds/flag to `state.md`/`loot.md`/`Killchain.md` before doing anything else. On return,
verify the capture against the stated criterion (`python3 scripts/lane_validate.py <eng>` runs the
check mechanically); a claimed success whose criterion observable is
absent from the capture is a failed lane (sibling of the existing one-line-verdict-without-capture
rule in slot (h)).

Returned-lane processing (in order):

- **Verdict above the claim, always.** Your verification one-liner (`VERIFIED: <capture ref>`
  or `NOT VERIFIED: <why>`) is written into the log line ABOVE the lane's own claim; a lane
  claim filed with no verdict of your own is the over-claim leak-through (sub-agent claims are
  hypotheses until you check the raw capture).
- **A pending lane is status, not guess.** While in flight the lane line says `in flight`;
  never record a silent lane as failed, and never peek at its partial output to guess progress.
- **Partial results are recovered, not discarded.** A killed/errored lane still returns its
  commands + raw output + `KILLED/FAILED at step N`; that partial capture dir is referenced in
  the Deadends line (a half-run often names the actual blocker) instead of vanishing.
- **Resume with context, not a respawn.** A follow-up on the same lane re-enters the SAME
  agent (its handle/id) carrying the prior raw output, so it continues from what it proved;
  a fresh respawn redoes discovery and re-fires the same dead ends.
- **Three same-class failures on one lane = switch, not a fourth.** Route the lane's row
  through `offensive.py next` for a different vector; grinding a 4th attempt of the same
  class is the doom-loop the driver exists to break.

## Mechanism

Dispatch via the Agent tool: `subagent_type` general-purpose, `model` per the choice above, the
checklist as the prompt, an explicit return/report contract written into the prompt itself. This
skill's invocation IS the standing authorization to use the Agent tool mid-engagement; no separate
approval needed.

## Worked examples

Each uses placeholder tokens only.

**(1) Catch a meterpreter as a service account**
Confirmed: RCE via the admin panel upload field on `<target>`. Egress-test the LPORT first (80/443
before 4444). Start `multi/handler` on the Kali VM, then deliver an inline base64 ELF payload through
the panel RCE. SUCCESS = `hostname` = `<target>` AND `id` = the expected uid, plus the session log path.

**(2) `ssh2john` -> crack -> `ssh-keygen -p` strip -> SSH chain**
Confirmed: a private key at `<path>` protected by a passphrase. Run `ssh2john <path> > <hash-file>`,
crack with the standard wordlist, then `ssh-keygen -p -f <path>` to strip the passphrase, then
`ssh -i <path> <user>@<target>`. Report the cracked passphrase and the resulting shell's
`hostname` + `id`.

**(3) sudo `screen -r <name>` -> `Ctrl-A c` root**
Confirmed: `sudo -l` shows `screen` unrestricted and a root-owned session `<name>` is running. Run
`sudo screen -r <name>`, then send `Ctrl-A c` to spawn a new window inside the root screen. Report
`hostname` + `id` from inside that window before touching anything else; the guardrail applies here too.

**(4) openssl-caps `.so` constructor root**
Confirmed: the `openssl` binary carries `cap_setuid+ep`. Compile a `.so` with a constructor that execs
a shell, run it via `openssl req -engine <path-to-so>`, then confirm `hostname` + `id` inside the new
shell before reporting root.

Once a working checklist and guardrail confirm a primitive, hand the box's actual next step to
`Skill(metasploit)` when the run is msf-shaped (handler catch, module-driven exploit); this skill
covers the delegation pattern itself, not the msf mechanics.

## Client-data boundary

Worked examples use placeholders only; never put a real target IP, hostname, or credential into this
skill file.
