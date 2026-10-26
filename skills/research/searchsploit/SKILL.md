---
name: searchsploit
description: "Use when public exploits/PoCs are needed for a fingerprinted product+version or CVE id ('searchsploit', 'find a poc', 'public exploit for X'). Exploit-DB + mirrors lookup, credibility read, PoC mirror + adaptation, lab-first verify. Hands armed PoCs to hunt-rce/nday."
metadata:
  hermes:
    tags: [searchsploit, exploitdb, poc, cve-research, adaptation]
    related_skills: [research, nday, hunt-rce, metasploit, wiki-arsenal]
---

# Searchsploit: public-exploit research + PoC development

The Exploit-DB methodology skill: find every public exploit for a
fingerprinted surface, judge which one is real, mirror it, adapt it to
the target, and verify the adaptation BEFORE it is fired at the target.
The brain's Research lane archetype dispatches this as its
Exploit-DB leg; this skill owns the depth (search syntax, credibility
read, adaptation checklist, lab-first rule).

**Division of labor:** wiki-arsenal answers "what technique/tool for
this class" from the wiki; THIS skill answers "what PUBLIC WORKING
CODE exists for this exact version/CVE" from the internet, then makes
it fireable. hunt-rce owns the in-engagement verdict; this skill
delivers the armed PoC.

## Wiki

Hub: [[methodology-moc]] - Primary page: [[vuln-assessment]]
Anchors: [[network-discovery]] (searchsploit --nmap chain),
[[nday-patch-diffing]], [[responsible-disclosure]]
**REFS:** [[vuln-assessment]]

qmd on hint only: "searchsploit exploitdb mirror poc adaptation" -
the service-enumeration page carries live syntax examples.

## Paths (binding - define once at the top of the run notes)

    # engagement mode (seat side, WSL; tree DOUBLE-NESTED in VMshare):
    ENG_DIR=/mnt/c/Users/Lenovo/Desktop/VMshare/<eng>/<eng>
    RUN=$ENG_DIR/research/poc/<slug>
    # research-project mode:
    PROJ=/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/raw/research/<project>
    RUN=$PROJ/poc/<slug>
    # VM side (WHERE searchsploit runs, same tree(s) through the share):
    (engagement) RUN=/mnt/VMshare/<eng>/<eng>/research/poc/<slug>
    (research)   RUN=/mnt/c/.../raw/research/<project>/poc/<slug>

Mirrored exploits land under $RUN/mirror/; adapted builds under
$RUN/adapted/; lab output under $RUN/lab/. NEVER mirror straight into
targets/<eng>/poc/ (that dir is curated evidence only).

## Transport

Every VM-native command block ships through ONE documented transport:

    wsl.exe -d kali-linux -u root bash -c "cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch && bash scripts/vm-ssh.sh '<command>'"

- vm-ssh lands as user tz (NOT root); one argument per call; quotes
  ship as base64 (`echo <b64> | base64 -d | bash`).
- searchsploit lives on the Kali VM (package `exploitdb`); DB refresh
  `searchsploit -u` when the last result set looks stale (pre-2024
  CVE missing). Internet fetches of PoC mirrors (GitHub/Packet
  Storm/Vulners) via /opt/scope-shim/bin/curl.
- Lab builds (gcc/go/python) run VM-side; long compiles detached
  (vm-bg.sh).

## Entry gate

All four must pass; each is falsifiable:

1. A TARGET SURFACE exists, either mode:
   (a) engagement: active engagement + the host on
   targets/<eng>/scope.md in-scope AND a fingerprint (product+version
   or CVE id) recorded in state.md/loot.md;
   (b) research: raw/research/active.md names the project AND
   target.md pins the version.
   No fingerprint = recon/enum lane first (searchsploit without a
   version is noise).
2. hunt-core loaded in engagement mode (scope gate, confirmation
   gate); research skill loaded in project mode (loop discipline).
3. Producer verified: the fingerprint is SPECIFIC (product+version or
   CVE id) - `Jenkins` alone fails; `Jenkins 2.414` or `CVE-2024-23897`
   passes.
4. Toolchain preflight (fails LOUD; install-on-demand per the
   operator rule):

       command -v searchsploit >/dev/null \
         || { sudo apt-get install -y exploitdb 2>/dev/null; } \
         || echo "N/A: searchsploit absent on VM (install failed - needs apt/sudo) - web mirrors only"

## Checklist (mandatory)

Copy run-protocol.md (this skill's dir) to `$RUN/searchsploit-checklist.md`
at run start. Unchecked at stop = UNCHECKED pass, re-run from the first
unchecked step. SKILL.md and the run-protocol header agree byte-for-byte
on that copy target. (checklist.md is the machine-gate lane template
`offensive.py lane-init` materializes per lane - never copy it by hand.)

## Nudge

Review-skill re-injection text (pinned; NOTE: completion-gate emits
its own generic nudge - both mean: resume at the first unchecked box):

    Your work was just reviewed by the review skill and it was found
    that you either missed a step of analysis, or didn't generate an
    artifact of sufficient proof. Look at the markdown based checklist
    and the output for each step, find what you missed, and complete
    that step.

## Confirmation gate

**NOT confirmation:** searchsploit returned rows; a mirror downloaded;
a PoC that compiles; a PoC that fires against YOUR lab copy while the
target's build/config differs materially; a blog post claiming the
exploit works.

**IS confirmation:** the ADAPTED PoC produces its primitive against
the actual target surface (engagement: through the scope-shim, RoE-
legal, evidence pair captured) or against a faithful lab replica
(product+version matched, config matched - differences recorded);
reproduced from your own written steps. The primitive observed must
match the claim class (RCE = code exec evidence, not a crash;
auth-bypass = the bypassed action succeeding).

## Methodology

### Step 1 - Sweep every source @ $RUN/sources.md

    searchsploit <product> <version>       # exact match first
    searchsploit --nmap <nmap-xml>         # version-annotated service map
    searchsploit -m <id>                   # mirror a hit into cwd

Cross-check beyond Exploit-DB (one row per source, credibility noted):
NVD refs tab, CISA KEV (exploitation status), GitHub code search
(`"<cve>" language:python`), Packet Storm, Vulners, vendor advisory
(affected-versions table is ground truth), PoC-interval heuristic
(public PoC usually lands 0-90 days post-disclosure).

### Step 2 - Credibility read @ $RUN/credibility.md

Per candidate: publication date vs disclosure date; affected versions
vs YOUR fingerprint (exact > range > "may affect"); author track
record (known researcher > throwaway); working proof vs
proof-of-concept stub; EOL/patched-in vs your target's build.
Kill rows carry their reason - a killed PoC is DATA (tells you the
public path is closed -> nday patch-diff instead).

### Step 3 - Mirror + read @ $RUN/mirror/

`searchsploit -m` or curl the mirror. READ THE CODE END TO END before
running (delegate read-first mandate): what it connects to, what it
writes, what it assumes (target path, hardcoded host, version branch,
dependency versions). A PoC you have not read is untrusted code with
a CVE number on it.

### Step 4 - Adapt @ $RUN/adapted/

Copy mirror -> adapted; change ONE thing at a time and record each:
target host/port (ALWAYS - mirror defaults point at 127.0.0.1 or the
author's lab), paths, version branch selection, payload generation
(msfvenom formats per Skill(metasploit) when a stager is needed),
language runtime pinning (python2 vs python3 is the classic breaker).
Note every divergence from the original in $RUN/adapted/CHANGES.md.

### Step 5 - Lab verify FIRST @ $RUN/lab/

Stand up the matched version locally (docker pull <product>:<ver>,
or vendor binary) when feasible; fire the adapted PoC at the LAB. A
PoC that cannot be lab-verified AND whose target differs from the
tested config carries an UNVERIFIED flag into handoff - the consumer
(hunt-rce lane) owns that risk decision, never this skill silently.

### Step 6 - Exit

$RUN/{sources,credibility}.md + mirror/ + adapted/ + lab/ complete;
engagement mode: candidate row appended to the owning class
candidates (hunt-rce vector) + _requests.md row (lane =
searchsploit); research mode: findings.md row (`public-poc <cve>`
adapted=<works|unverified>) + loop.md pointer
`SEARCHSPLOIT-PASS-DONE sources=<n> credible=<n> adapted=<n>
lab=<verified|unverified|n/a>`.

## Chaining

- Public path dead (no credible PoC) -> Skill(nday): patch-diff the
  fix and build the trigger yourself.
- Armed PoC vs engagement target -> hunt-rce owns the verdict + G1;
  metasploit owns execution when a module exists.
- Fresh pattern found while reading PoC code -> research loop
  (variant candidate), disclosure if novel.

## Validation

- Proof = the adapted PoC's primitive observed (target or faithful
  lab), evidence pair under $RUN/lab/ or probes/raw/.
- Negative control: the PoC against a PATCHED/mismatched version
  fails cleanly (confirms version sensitivity, not a scanner-true).

## False Positives

- Version-range match ("affects < 2.5" vs your 2.4.1-hotfix2).
- PoC for a different product edition/component (CE vs EE, plugin vs
  core).
- Compiles-but-dead: dependencies unresolved at runtime after build.
- Metasploit module rank "normal" treated as verified (check the
  module's disclosure date vs relDate of the installed DB).
- Scanner-style PoC (banner check) reported as exploit-capable.

## Severity

Inherits the CVE's class severity via triage; this skill produces
armed vectors, not verdicts.

## N/A escapes

- "N/A: searchsploit absent on VM (install failed - needs apt/sudo)"
  (web-mirror workflow still runs)
- "N/A: no public exploit exists" (sources.md shows every source
  swept + credibility rows all killed - then route to nday)
An N/A tick is a claim with a reason, never a silent pass. Identical
strings in SKILL.md and checklist.md.

## Bitter-pill variant

Freehand pass: skip checklist + numbered steps, one freehand sweep
over the sources, output ONLY $RUN/bitter-pill.md (tried/found/
dismissed, every claim carries evidence). The read-before-run rule
and lab-first rule survive freehand. Declare with a row (lane =
searchsploit-bitterpill / loop.md row).

## Exit artifact + handoff

$RUN/{searchsploit-checklist.md, sources.md, credibility.md,
mirror/, adapted/ (+CHANGES.md), lab/}; consumer handoff named in the
exit pointer (hunt-rce lane / research loop). Distill reusable
adaptation tricks: `python3 scripts/wiki-stage.py --kind technique
--slug <slug> --target-page wiki/tools/searchsploit.md`.

## Stop conditions

All steps terminal (probed | N/A with reason | killed-with-reason
row); every mirrored exploit READ before any run; nothing fired at a
target without scope+RoE check (engagement mode); no unchecked boxes
above REVIEW; hunt-core / research-loop stop conditions fire
unchanged.
