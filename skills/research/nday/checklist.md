# nday checklist

Copy this file to `$RUN/nday-checklist.md` at run start (RUN =
`raw/research/<project>/nday/`). Work top to bottom; `- [ ]` means not
finished. Any unchecked box at stop = the pass is not done and must be
re-run from the first unchecked step. On the gate nudge, resume at the
first unchecked box - do not restart.

## Entry

- [ ] Research project exists and active (raw/research/active.md names <project>) - or new-research.sh run first
- [ ] Patch identified: CVE id / advisory / fix commit / fixed-version recorded in target.md (a vague version gap is NOT an entry)
- [ ] Producer verified: both versions ACQUIRABLE, one-command acquisition probe per side @ $RUN/versions/probe.txt ("N/A: binary pair unobtainable" = deadend row with the probe evidence, not a run)
- [ ] Toolchain preflight passed (git/python3 hard; "N/A: diaphora absent on VM (install failed)" only after clone attempt)
- [ ] ENG/PROJ and RUN defined once at top of run notes (absolute paths; VM spelling /mnt/c/.../raw/research/<project>, seat spelling /mnt/c/.../raw/research/<project>)
- [ ] Doctrine tree created: $RUN/{versions,diffs,analysis}
- [ ] Checklist copied to $RUN/nday-checklist.md

## Diff + root cause

- [ ] Step 1 - Both versions acquired; sha256 of each artifact recorded; build flags matched where possible @ $RUN/versions/
- [ ] Step 2 - Diff produced: source (git log <fixtag>~5..<fixtag> then git diff over suspect path - find the REAL fix commit, vendors sneak fixes) or binary (BinDiff/Diaphora/Ghidra VT - CHANGED functions, not recompiled noise) @ $RUN/diffs/
- [ ] Step 3 - Root cause stated in one line (<input> reaches <sink> unchecked = <primitive>), traced back to attacker input + realistic config gate @ $RUN/analysis/root-cause.md

## Trigger + variants

- [ ] Step 4 - Trigger built: executes the pre-patch unchecked path on the SHIPPED vulnerable build in realistic config; FIXED build rejects the same input; both reproduce from written steps @ $PROJ/poc/
  - fuzzing shortcut recorded if used ([[fuzzing]] + sanitizer narrowed the shape)
- [ ] Step 5 - Variant analysis: grep/codeql for the same flawed pattern in unpatched code; each hit = candidate row (location + why), NEVER a finding without a second working trigger @ $RUN/analysis/variants.md

## Exit artifact

- [ ] Step 6 - findings.md row (`n-day CVE-<id>` or `candidate`), affected/fixed versions + exact patch commit, PoC path @ $PROJ/findings.md
- [ ] Pointer appended: NDAY-PASS-DONE cve=<id> trigger=<works|blocked> variants=<n> to $PROJ/loop.md
- [ ] Deadends rows appended per dead branch (WHY: unobtainable / inconclusive diff / unreachable in realistic config)
- [ ] Negative control recorded (trigger input with the offending field neutralized runs clean)
- [ ] Empty-state rule: no trigger + no variants with per-step notes = valid negative pass; a MISSING section = failed pass

## Stop conditions

- [ ] All steps terminal (probed | N/A with reason | deadend row)
- [ ] Nothing written into the skill dir (skills/research/nday/ stays untouched)
- [ ] No unchecked boxes above

## REVIEW (mandatory final step)

- [ ] REVIEW: re-read every box above; for each, confirm the artifact exists, is non-zero bytes, and matches the expected format
