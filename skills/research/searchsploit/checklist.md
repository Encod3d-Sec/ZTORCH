# searchsploit checklist

Copy this file to `$RUN/searchsploit-checklist.md` at run start (RUN =
engagement `$ENG_DIR/research/poc/<slug>/` OR research
`raw/research/<project>/poc/<slug>/`). Work top to bottom; `- [ ]`
means not finished. Any unchecked box at stop = the pass is not done
and must be re-run from the first unchecked step. On the gate nudge,
resume at the first unchecked box - do not restart.

## Entry

- [ ] Mode + surface: (a) engagement - host in-scope on targets/<eng>/scope.md + fingerprint recorded, OR (b) research - raw/research/active.md names project + target.md pins version. No fingerprint = recon/enum first
- [ ] hunt-core (engagement) or research (project) loaded
- [ ] Fingerprint SPECIFICITY verified: product+version or CVE id ("Jenkins" alone FAILS; "Jenkins 2.414" passes)
- [ ] Toolchain preflight passed ("N/A: searchsploit absent on VM (install failed - needs apt/sudo)" only after apt attempt = web mirrors only)
- [ ] RUN defined once (absolute paths, both spellings); doctrine tree $RUN/{mirror,adapted,lab}
- [ ] Checklist copied to $RUN/searchsploit-checklist.md

## Sweep + judge

- [ ] Step 1 - Every source swept: searchsploit exact + --nmap chain, NVD refs, CISA KEV, GitHub code search, Packet Storm, Vulners, vendor advisory (affected-versions = ground truth), PoC-interval heuristic @ $RUN/sources.md
- [ ] Step 2 - Credibility read per candidate: date vs disclosure, affected-versions vs fingerprint, author record, working-vs-stub; killed rows carry reasons (a killed PoC = public path closed -> nday route) @ $RUN/credibility.md
  - ("N/A: no public exploit exists" only with every source swept + all rows killed)

## Mirror + adapt + verify

- [ ] Step 3 - Credible candidates mirrored (`searchsploit -m` / curl) AND read END-TO-END before any run (connect targets, writes, assumptions, runtime pins) @ $RUN/mirror/
  - no unread exploit is executed, ever (lab included)
- [ ] Step 4 - Adapted: ONE change at a time, each recorded; host/port ALWAYS retargeted (mirror defaults = author lab), version branch, payload format, python2/3 pin @ $RUN/adapted/ + CHANGES.md
- [ ] Step 5 - Lab verify FIRST: matched version stood up (docker/vendor binary) + adapted PoC fired at the LAB; target-config divergences recorded; unverifiable = UNVERIFIED flag handed to consumer (never silent) @ $RUN/lab/
- [ ] Step 6 - Negative control: adapted PoC against patched/mismatched version fails cleanly (version sensitivity proven)

## Exit artifact

- [ ] Step 7 - Exit rows: engagement = candidate row appended to owning class + _requests.md row (lane = searchsploit); research = findings.md `public-poc <cve>` + loop.md `SEARCHSPLOIT-PASS-DONE sources=<n> credible=<n> adapted=<n> lab=<verified|unverified|n/a>`
- [ ] Deadends rows per killed source (WHY: version range mismatch / edition mismatch / dead dependencies)
- [ ] Nothing fired at a target without scope+RoE check (engagement mode); lab evidence pairs under $RUN/lab/
- [ ] Empty-state rule: 0 credible PoCs with per-source kill notes = valid negative pass; a MISSING section = failed pass

## Stop conditions

- [ ] All steps terminal (probed | N/A with reason | killed-with-reason row)
- [ ] Every mirrored exploit read before run; every adaptation recorded
- [ ] Nothing written into the skill dir; no unchecked boxes above

## REVIEW (mandatory final step)

- [ ] REVIEW: re-read every box above; for each, confirm the artifact exists, is non-zero bytes, and matches the expected format
