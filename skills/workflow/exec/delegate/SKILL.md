---
name: delegate
description: Sub-agent hand-off for a fully-specified exploit/escalation run, behind a false-root guardrail, main agent stays on strategy. Use for "delegate", "hand this to a sub-agent", "spin a flash", or foothold + working vector found.
---

## Sections
- [[#When to delegate / when NOT]]
- [[#Model choice]]
- [[#The checklist (a delegation is only as good as its checklist)]]
- [[#Lane mandate battery (verbatim)]]
- [[#Brief template (skeleton)]]
- [[#False-root/hostname guardrail (MANDATORY every delegation)]]
- [[#Write-back and interrupts]]
- [[#Main-agent discipline]]
- [[#Mechanism]]
- [[#Worked examples]]
- [[#Client-data boundary]]

state: active
created: 2026-10-12
last_used: 2026-10-12

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
already cleared, so lean into the cheap tier there and keep the main model on strategy. Step UP to
the mid tier (glm-5.3) for a genuinely judgement-heavy multi-step run (a JS-heavy per-route-CSRF
authed backend RCE, a live-surface hunt lane), and to the max tier (glm-5.3-max, `opus`) for RTL
consults, exploit development, and exploit-chain construction (clinical verify/confirm framing; a
`[cyber]` safeguard failure redispatches on haiku, never dropped; operator 2026-10-06).

DISCOVERY (route/endpoint/token enumeration) delegates at sonnet/opus ONLY, never the cheap tier,
and a discovery lane's negative is re-verified on the main model before it becomes a Deadend.
Vector selection and "is this
surface empty or am I querying it wrong" stay on the main model. A cheap model hardens a wrong negative
into a fact -- it reports "empty/dead" from a query mistake and you inherit it as a hard exclusion (a
real miss: a delegated agent called a UCP voicemail "empty" because it hit the AJAX endpoint, not the
dashboard widget that rendered the secret; that fossilized into a wrong "rabbit hole" and cost an
hour+). If the run is not fully specified, it is not a delegation, it is a guess wearing a checklist,
keep it on the main model. Re-verify any NEGATIVE a sub-agent returns before it becomes a Deadend.

## The checklist (a delegation is only as good as its checklist)

Every delegation needs all eight slots filled. Under-specify one and the sub-agent flails; that is the
usual failure mode, not a weak sub-agent.

- **(a) confirmed access/primitive**, spelled out; don't make the sub-agent rediscover it.
  The 4-field gate (cyberstrikeai L4): the dispatch prompt is INVALID unless it carries
  all of (1) target identifier (URL / `IP:port` / domain+path), (2) in-scope boundary
  (what is fair game this round, what is not), (3) single subgoal for this round, (4)
  success criteria (deliverable shape). Any missing field means do NOT dispatch; fill it
  or ask the operator. Subagent mirror: if any required field is missing from your
  prompt, STOP and return a MISSING-FIELDS list naming them; never guess, never reuse a
  target from memory. Alongside the primitive, state the assumption set: what must hold
  true for the run to make sense (access still valid, file still at that path, version
  match); a wrong assumption then surfaces as a reportable mismatch, not a silent miss.
- **(b) exact copy-paste commands**, real IPs/paths inline, no `$VAR`; the sub-agent cannot watch a
  live terminal to sanity-check a substitution. Each command block pairs with its expected
  observable, step -> verify form, so drift is caught at the step, not at lane end. Lane code
  discipline: code the lane writes is minimum-code (stdlib / platform-native first, no frameworks,
  no scaffolding for later); the lane never improves target code beyond its checklist and flags
  anything unrelated it notices in the report instead of acting on it. Lane CLI discipline:
  verify uncertain flags with `<tool> -h` before first use and re-check
  after any failure that suggests memorized syntax is stale; the same flag means different
  things per tool (`-p`: port in nmap, password in hydra), so never copy a flag across tools
  and never invent an output flag the tool's own help does not document; when output must be
  parsed or piped, request the tool's structured format (nmap `-oX`, or a `-json`/`-jsonl`
  flag) instead of parsing free text; quote shell metacharacters; minimize at the source
  (`msfconsole -q`, `nmap --open`) so captures stay small; maximum 2 install attempts before
  switching tools.
- **(c) egress/port constraints**, an egress-tested LPORT, not a guess at 4444.
- **(d) the false-root guardrail** (next section), non-negotiable.
- **(e) fragile-box discipline** if applicable: serial requests, long timeouts, no fuzzers.
- **(f) report-back contract**: return the primitive/creds/flag plus evidence path; REVERT any state
  the run changed (a group membership added, a registry key set) before reporting back; do not pivot
  further without the main agent. Structure the return as the lane envelope: Scope (what was
  attempted) / Result (verdict + the raw observable) / Key files (capture paths) / Issues
  (blockers). A negative Result also carries `failure-class: technical | environmental | conceptual |
  external` (tool/arg mechanics broke | seat/VM/network flaked | the vector class itself is
  wrong for this surface | target-side change such as a WAF rule or patch). The main model writes `SUCCESS = <exact observable>` into the
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

## Lane mandate battery (verbatim)

The fixed mandate block the brain pastes into every lane prompt. Paste this block
byte-identical into every dispatch prompt; no paraphrase, no dropping a line the dispatcher
finds obvious (a cheap lane model gets the intent only from the named failure modes).

```text
READ-FIRST: cat each file in full, zg/grep only to locate; the vector hides in what a narrow grep skips.
ANTI-GIVE-UP: run the FULL specified window; if blocked, report the RAW output/errors and STOP.
NO-GUESS: never guess or substitute a value, never invent a result; a verdict without the raw observable is a failed lane.
ENVELOPE: return Scope / Result (verdict + raw SUCCESS observable) / Key files / Issues; 15 lines or fewer.
OBSIDIAN-SAFE: any angle-bracketed value you write into a `.md` is wrapped in inline backticks; bare angle brackets break the page.
CONTEXT RULES: you see ONLY this brief and the files it names by path - no board, no sibling lanes' state, no prior turns; shared background is repeated per lane, never assumed.
```

## Brief template (skeleton)

Every dispatch brief follows this fixed shape; fill every field, no free-form drift.

- **Goal**: one sentence, the single subgoal for this round (slot a, field 3).
- **Context**: only the background THIS lane needs - primitive, constraints, assumption
  set (slots a, c, e). No engagement narrative beyond need-to-know; the lane's context is
  the brief, not the board: no history, no sibling-lane state, no pasted wiki bodies;
  name paths, not bodies.
- **Files**: every path the lane may read or write, capture dir included.
- **Budget**: claim budget + REQUIRED-OUTPUT list when investigation-shaped (slot f).
- **Window**: the exact run window / watch duration (slot g runs it in full).
- **SUCCESS**: the exact observable (slot f), returned RAW plus the capture path.

## False-root/hostname guardrail (MANDATORY every delegation)

A returned `uid=0`/root (Linux) or `nt authority\system` (Windows) is trusted ONLY if `hostname`
matches the target AND the expected uid holds.
Otherwise the shell died back to the Kali box, which runs as root; `$(...)`/backticks there substitute
LOCALLY, the false-RCE trap. The fix is re-pop, not celebrate. The sub-agent MUST report `hostname`
alongside any `id`/`whoami` output, every time, no exceptions.

### Verifier lanes

One cheap fresh-context read replaces a second full session re-deriving evidence.
Input: the package file from `bash scripts/capture.sh pkg FIND-NNN`.

- Scope fence: read ONLY the package file; never re-test the target.
- Verdict per finding: CONFIRMED / NOT CONFIRMED / UNVERIFIABLE, each citing the exact
  package line that decided it. UNVERIFIABLE routes to Skill(triage) as a named operator
  check, never silently dropped.
- Claims-extraction pass: list every factual, process, and quality claim in the lane
  report; check each against the package; a claim no package line covers is UNVERIFIABLE.
- Critique the assertion: for each check, answer "would this pass on a wrong result?";
  if yes, the check is weak; say so in one line.
- Fix-loop scope: re-reviews verdict only each prior finding ADDRESSED or NOT ADDRESSED
  in the new capture range; attempted is not addressed.

## Write-back and interrupts

- **PENDING-WRITE**: a lane that cannot write shared state (no file tools, read-only
  seat) ends its return envelope with a `PENDING-WRITE` block - one entry per finding:
  key, one-line summary, body bullets. The brain applies them to state.md/loot.md before
  the next dependent move; a PENDING-WRITE never silently evaporates.
- **STOP-REASON**: redirecting a running lane sends a message whose first line is
  `STOP-REASON: <one line>`. The lane treats it as mid-task correction, incorporates the
  reason into its next action, and does not restart from zero.

## Main-agent discipline

Keep driving the board while the sub-agent works. Dispatch ONE sub-agent at a time, serial; never
duplicate its target in parallel. Before dispatch, append one lane line to `targets/<eng>/log.md`
(`- lane <name> (<asset>) in flight @<HH:MM>: SUCCESS = <observable> | tmux win <win> | capture <dir> | handle <agent-id>`)
so a compaction mid-lane re-surfaces it via the log's newest block AND the lane's agent handle
survives the compaction (the `Resume with context` rule needs it); the `<asset>` + `@<HH:MM>` cells
let `scripts/status.py` age open lanes and flag a RE-SERVE against the driver's last move. On
return, close the line with the
result: APPEND the verdict to the lane line itself (`... | handle <agent-id> -> VERIFIED: <capture ref>`
or `-> NOT VERIFIED: <why>`) and drop `in flight`. A verdict written only as a separate line above
leaves the lane line reading `in flight` forever (the lane regex keys on the appended verdict, so
SessionStart's post-compact re-inject and close-out's sweep would keep re-surfacing a closed lane).
WAIT for completion before the next move. On return, persist the
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
- **Type the failure before the next move.** technical -> adjust args or tool; environmental
  -> one recovery-ladder retry, else switch seat; conceptual -> pivot vector class entirely
  via `offensive.py next`; external -> park with a reopen-if trigger in Deadends. Two
  failures of the same class on the same row = switch class, not a third identical attempt
  (this types the existing 3-fail switch rather than replacing it).
- **Three same-class failures on one lane = switch, not a fourth.** Route the lane's row
  through `offensive.py next` for a different vector; grinding a 4th attempt of the same
  class is the doom-loop the driver exists to break.

### Dispatch hygiene (context economy)

- Artifacts are file paths: the brief and the report are paths, never pasted bodies;
  the lane writes its full report to the named path.
- Return envelope is 15 lines or fewer: status, pointers, one-line summary, concerns.
- A worker never spawns its own subagent; a felt need for a reviewer is returned as a
  concern instead.
- Every lane slot carries an explicit `model:` field. Transcription-shaped work (exact
  commands handed over) runs the cheap tier; judgment or review runs the mid tier; the
  cost metric is turn count, not token price (a cheap model taking 2-3x the turns costs
  more than the tier it saved).
- Batch same-shape briefs: N identical-shape items go in
  one brief enumerating every item; verification is per item;
  a listed item with no capture is a Missing finding
  regardless of the rest of the batch.

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
