---
name: nday
description: "Use when a vendor-shipped fix needs a pre-patch PoC (n-day, patch diff, bindiff) or variant analysis extends it to a fresh bug candidate. Diff, root cause, trigger, variant. Consumes research-loop state; hands PoCs/candidates to disclosure."
metadata:
  hermes:
    tags: [nday, patch-diffing, bindiff, variant-analysis, exploit-dev]
    related_skills: [research, searchsploit, hunt-pwn, disclosure, triage]
---

# N-day / Patch Diffing

Turn a patched vulnerability into a working PoC, or surface a
silently-patched bug. Runs INSIDE a research project - the research
skill owns the loop; this skill owns the patch-diff methodology.

## Wiki

Hub: [[exploit-dev-moc]] - Primary page: [[nday-patch-diffing]]
Anchors: [[binary-exploitation]], [[ghidra]], [[codeql]],
[[crash-analysis]], [[fuzzing]]
**REFS:** [[nday-patch-diffing]]

qmd on hint only: "patch diff bindiff Diaphora version tracking
silently patched variant analysis" - the nday page first.

## Paths (binding - inside the research project tree)

    # seat side (WSL):
    PROJ=/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/raw/research/<project>
    RUN=$PROJ/nday                          # this pass's artifacts
    # VM side (WHERE binary diffing runs, same repo through the share):
    PROJ=/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/raw/research/<project>
    RUN=$PROJ/nday

Both-version trees land under $RUN/versions/{vuln,fixed}/; diff
exports under $RUN/diffs/; PoC under $PROJ/poc/ (research-tree
convention, scaffolded by new-research.sh).

## Transport

Every VM-native command block ships through ONE documented transport:

    wsl.exe -d kali-linux -u root bash -c "cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch && bash scripts/vm-ssh.sh '<command>'"

- vm-ssh lands as user tz (NOT root); one argument per call; quotes
  ship as base64 (`echo <b64> | base64 -d | bash`).
- Source trees and vendor binaries download via
  /opt/scope-shim/bin/curl; a research project has no scope.md
  hostlist, so UNKNOWN-host ADVISORYs default to DENY for target
  infrastructure (vendor mirrors/GitHub are fine).
- BinDiff/Diaphora pair runs happen inside Ghidra/IDA on the seat;
  exports are files, never screenshots.

## Entry gate

All four must pass; each is falsifiable:

1. A research project EXISTS and is active:
   `raw/research/active.md` names <project> (or `bash
   setup/new-research.sh <project>` first). No project = the research
   skill owns scaffolding, not this one.
2. A patch EXISTS and is identified: CVE id / advisory / fix commit
   hash / fixed-version number recorded in $PROJ/target.md. A vague
   "something changed between 1.2 and 1.3" is NOT an entry - version
   pinning happens in the research loop first.
3. Producer verified: both versions are ACQUIRABLE (vendor repo,
   release assets, distro packages, firmware blobs) - a one-command
   acquisition probe per side recorded in $RUN/versions/probe.txt.
   One side unobtainable = deadend row, not a run.
4. Toolchain preflight (fails LOUD; install-on-demand per the
   operator rule):

       for t in git /usr/bin/python3; do
         command -v "$t" >/dev/null || { echo "MISSING TOOL: $t"; exit 1; }
       done
       command -v diaphora >/dev/null \
         || { git clone -q --depth 1 \
                https://github.com/joxeankortesi/Diaphora.git /tmp/diaphora; } \
         || echo "N/A: diaphora absent on VM (install failed) - BinDiff/seat-side Ghidra VT only"

## Checklist (mandatory)

Copy run-protocol.md (this skill's dir) to
`$RUN/nday-checklist.md` at run start. Unchecked at stop = UNCHECKED
pass, re-run from the first unchecked step. SKILL.md and the run-protocol
header agree byte-for-byte on that copy target. (checklist.md is the
machine-gate lane template `offensive.py lane-init` materializes per lane -
never copy it by hand.)

## Nudge

Review-skill re-injection text (pinned; NOTE: completion-gate emits
its own generic nudge - both mean: resume at the first unchecked box):

    Your work was just reviewed by the review skill and it was found
    that you either missed a step of analysis, or didn't generate an
    artifact of sufficient proof. Look at the markdown based checklist
    and the output for each step, find what you missed, and complete
    that step.

## Confirmation gate

**NOT confirmation:** a diff exists; a changed-function list; a
hypothesis ("the patch adds a bounds check so the old build must be
overflowable"); a PoC that crashes a build you compiled differently
from the shipped vulnerable one.

**IS confirmation:** the trigger EXECUTES the pre-patch unchecked
path on the SHIPPED vulnerable build in a realistic config (crash with
register control / auth bypass / info leak observed), the FIXED build
rejects the same input, and both reproduce from your own written
steps. A variant candidate is confirmed when the same flawed pattern
is shown in UNPATCHED code with a second working trigger - otherwise
it is a candidate row, never a CVE claim.

## Methodology

### Step 1 - Acquire both versions @ $RUN/versions/

git tags, release assets, distro packages (.deb/.rpm from
snapshot/archive mirrors), vendor firmware. Record sha256 of each
artifact in $RUN/versions/probe.txt. Match build flags/config where
possible - a differently-compiled pair poisons the diff.

### Step 2 - Diff @ $RUN/diffs/

- Source: `git log <fixtag>~5..<fixtag>` (find the real fix commit -
  vendors sneak fixes into unrelated commits) then
  `git diff <vulntag> <fixtag>` over the suspect path.
- Binary: BinDiff / Diaphora / Ghidra Version Tracking; open functions
  flagged CHANGED (not merely recompiled - recompile noise dominates
  without symbols; similarity < 1.0 with matched names is the signal).

### Step 3 - Root cause @ $RUN/analysis/root-cause.md

What the patch ADDS (bounds/auth/sanitization check) reveals what was
missing. Trace the now-checked value BACK to attacker input: which
parser entry, which field, which config gate. State the primitive in
one line: <input> reaches <sink> unchecked = <primitive>.

### Step 4 - Trigger @ $PROJ/poc/

Craft input that reaches the pre-patch unchecked path. Reproduce on
the vulnerable build; CONFIRM reachability in a realistic config (the
default config, not a debug build with the feature compiled in).
Fuzzing shortcut when hand-crafting stalls: [[fuzzing]] with a
sanitizer build narrows the input shape.

### Step 5 - Variant analysis @ $RUN/analysis/variants.md

Grep / [[codeql]] for the same flawed pattern the patch did NOT touch
(sibling functions, copy-pasted handlers, other transports feeding the
same sink). Each hit = candidate row (location + why it matches the
pattern), NOT a finding. New variant -> hand off to Skill(disclosure).

### Step 6 - Exit

findings.md row (`n-day CVE-<id>` or `candidate`), affected/fixed
versions + exact patch commit, PoC path, deadends for dead branches
(WHY: version unobtainable, diff inconclusive, trigger unreachable in
realistic config). `NDAY-PASS-DONE cve=<id> trigger=<works|blocked>
variants=<n>` appended to $PROJ/loop.md.

## Chaining

- Public-path PRE-CHECK: Skill(searchsploit) sweeps public PoCs FIRST;
  a dead public path (no credible PoC) is this skill's primary trigger -
  patch-diff builds what nobody published.
- Fresh CVE hunt from a target surface: Skill(research) owns the loop;
  this skill is its patch-diff step-7 novelty instrument.
- Memory-corruption trigger engineering: Skill(hunt-pwn) once the
  primitive is in hand.
- Disclosure (CVE filing, 90-day): Skill(disclosure).

## Validation

- Proof = vulnerable build executing the path + fixed build rejecting
  it, same input, both from clean state (re-run recorded commands).
- Negative control: the trigger input with the offending field
  neutralized runs clean on the vulnerable build.

## False Positives

- Diff noise: recompiled-but-identical functions; refactors that look
  like security fixes; hardening that postdates the actual fix.
- Reachability assumed: the unchecked path exists but no realistic
  config reaches it (dead code / debug-only).
- Variant candidate promoted without a second working trigger.
- PoC against a self-compiled build whose flags differ from the
  shipped vulnerable artifact.

## Severity

Rate per triage once confirmed: memory corruption with control =
CRITICAL/HIGH; auth bypass = HIGH; info leak = MEDIUM. Candidates
carry no severity until triggered.

## N/A escapes

- "N/A: binary pair unobtainable" (one side not acquirable - recorded
  in versions/probe.txt)
- "N/A: diaphora absent on VM (install failed)"
An N/A tick is a claim with a reason, never a silent pass. Identical
strings in SKILL.md and checklist.md.

## Bitter-pill variant

Freehand pass: skip checklist + numbered steps, one freehand pass
over the diff, output ONLY $RUN/analysis/bitter-pill.md (tried/found/
dismissed, every claim carries evidence). The trigger-on-shipped-build
gate survives freehand. Declare with a loop.md row (pass =
nday-bitterpill).

## Exit artifact + handoff

$RUN/{versions,diffs,analysis,nday-checklist.md}, findings.md row,
loop.md NDAY-PASS-DONE pointer. Consumers: research loop (next-move
ranking), disclosure (variant candidates). Distill: `python3
scripts/wiki-stage.py --kind technique --slug <slug> --target-page
techniques/exploit-dev/nday-patch-diffing.md`.

## Stop conditions

All steps terminal (probed | N/A with reason | deadend row); no
unchecked boxes above REVIEW; nothing written into skill dirs;
research-loop stop conditions (deadend discipline, budget) fire
unchanged.
