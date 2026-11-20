---
name: research
description: "Use for the vuln-research loop toward a novel CVE ('research', 'find a cve', 'analyze this binary', 'audit this code for vulns'). raw/research/{project} state tree; findings deepen, dead-ends pivot."
metadata:
  hermes:
    tags: [research, cve, loop, fuzzing, audit]
    related_skills: [nday, wiki-recon, research-ingest, disclosure]
---

## Wiki

Hub: [[methodology-moc]] - Primary page: [[vuln-assessment]]
Anchors: [[fuzzing]], [[nday-patch-diffing]], [[binary-exploitation]]
**REFS:** [[vuln-assessment]]

# Research: CVE Discovery Loop

Find and prove **one novel vulnerability** in a target (binary, library, web app/API, firmware, protocol, or source repo). The loop is persistent, resumable, and anti-loop: findings deepen it, dead-ends pivot it, and every step is driven by the knowledge base.

This skill is the research analog of the engagement framework: `raw/research/<project>/` is to research what `targets/<eng>/` is to an engagement.

---

## 0. Setup (once per target)
1. Identify target **type + version + source**. Get the code/binary: repos via WSL clone (`wsl -d kali-linux -u kali -- git clone <url> /home/kali/<name>`), releases by download.
2. Scaffold: `bash setup/new-research.sh <project_name>` -> `raw/research/<project>/{target,surface,findings,deadends,loop}.md + poc/` (also sets it active in `raw/research/active.md`, so SessionStart surfaces its status).
3. zg covers clones automatically - the standing vault index includes `raw/git/`, so `zg query` reaches the repo (AGENTS.md Search rule). No per-clone index step: `zg index` climbs to the enclosing workspace root, per-clone workspaces are not a thing.
4. Build/run it where possible - a runnable target unlocks dynamic testing + fuzzing.
5. Fill `target.md`: what it is, version, language, build/run commands, trust boundaries.

## 1. State-first (EVERY iteration, MANDATORY)
Read `raw/research/<project>/{loop.md, deadends.md, findings.md}` before acting. Never re-run a logged dead-end without new input. Resume from the last iteration. This is the anti-loop rule - the same discipline engagements use. Run `python3 scripts/research_status.py` for the current phase + ranked next move (also auto-surfaced at SessionStart from `raw/research/active.md`). Also read the research ledger `raw/research/<project>/.research.json` (agent-written, driver-read): a `settled` topic is REUSED, never re-fetched; `research_status.py` prints ledger stats + DEDUP warnings.

## 2. Attack-surface map (`surface.md`)
`mcp__wiki-search__query` the target's tech/language/framework first, then map by type:

| Target type | First moves | Knowledge base |
|---|---|---|
| **binary / executable** | `checksec`, `strings`, RE entry + parsers, identify input handling | [[reverse-engineering]] [[ghidra]] [[radare2]] [[binary-exploitation]] [[memory-safety-bugs]] [[fuzzing]] [[aflplusplus]] [[gdb-gef]] |
| **C/C++ library** | grep dangerous APIs, build a fuzz harness, map public API | [[memory-safety-bugs]] [[fuzzing]] [[libfuzzer]] [[aflplusplus]] [[static-code-analysis]] [[semgrep]] [[codeql]] |
| **web app / API** | map routes, auth, sinks; diff vs known framework CVEs | web hunt skills (sqli/idor/auth/injection/deser/ssrf/upload) + [[source-audit-checklist]] [[static-code-analysis]] |
| **firmware** | `binwalk -Me`, extract rootfs, then treat components as binary/web | [[firmware-hardware]] [[binwalk]] |
| **protocol / network service** | RE the parser/state machine, fuzz the wire format | [[protocol-attacks]] [[fuzzing]] [[aflplusplus]] [[reverse-engineering]] [[ghidra]] |
| **source repo (any lang)** | audit + dependency CVE review + secret/history scan | [[source-audit-checklist]] [[static-code-analysis]] [[semgrep]] [[codeql]] [[trivy]] [[secret-hunting]] [[git-exposure]] + the matching vuln-class page |

Record in `surface.md`: entry points (attacker-controlled input), parsers/deserializers, dangerous sinks, privileged ops, dependencies with CVE history.

## 3. Hypothesize (ranked, in `loop.md`)
From the surface + knowledge base, write hypotheses as **`<input/location>` + `<bug class>` = `<expected primitive>`**. Rank by: reachable from an attacker boundary, attacker-controlled, lands in a dangerous sink, historically buggy area, weak/old dependency. Pick the highest-value **untested** hypothesis (skip anything in `deadends.md`).

## 4. Investigate (loop body)
Apply the matching technique + hunt skill + tool to the chosen hypothesis. Bound the effort up front (e.g. fuzz N hours / M execs; audit this component once; sweep this payload class once).
- **memory-safety:** audit sinks with [[memory-safety-bugs]], then build/point a fuzzer at the parser ([[aflplusplus]] / [[libfuzzer]], always with a sanitizer), triage crashes ([[crash-analysis]]), RE the root cause in [[ghidra]].
- **web/logic (source available):** work the [[source-audit-checklist]] (sources -> sinks), then invoke the matching `hunt-*` skill (auth/idor/injection/deser/ssrf/upload/bizlogic/smuggling) to confirm with the payload arsenal.
- **injection/parse:** malformed/oversized/encoded inputs at each parser; the relevant payload page.
- **dependency:** [[trivy]] for known-CVE deps -> prove reachability from input.

## 5. Evaluate the result
- **FINDING** (crash, leak, anomaly, logic flaw): record it in `findings.md` with class + location. **Continue looping from the finding -> go to 6. Do NOT stop at the first anomaly.**
- **NOTHING** after the bounded effort: append the approach + why-exhausted to `deadends.md`, then **go to 3 and pick a different hypothesis/approach.**

## 6. Deepen the finding (the loop continues from here)
A finding spawns its own mini-loop - each question is an iteration, and a dead-end here pivots *within* the finding before abandoning it:
1. **Root cause** - the exact flawed code/logic.
2. **Reachability** - is it triggerable from a real attacker boundary (not just an internal call)?
3. **Exploitability** - is the primitive controllable (overwrite what / leak what / which state)?
4. **Impact** - RCE / memory corruption / info leak / DoS / privesc / auth bypass.
5. **Variants** - is the same bug pattern present elsewhere (zg or grep the codebase)?

## 7. Prove + tiered novelty-check (the research ladder)
- Minimal reproducible **PoC / trigger** in `poc/`.
- **Severity + CVSS**; **affected versions** (`git blame` / changelog for when introduced).
- **Novelty = the research ladder.** EVERY research pass (surface mapping, hypothesis investigation, novelty check, objection-seeded requeues) runs it, Tier 1 first, ALWAYS:
  - **Tier 1 (exact, cheap):** does a CVE/CWE/advisory exist for THIS component + version? `mcp__wiki-search__query` the wiki first, then NVD/GHSA/OSV, the project changelog, vendor advisories. Budget: at most 3 distinct queries. A hit ENDS the pass.
  - **Tier 2 (widen):** runs only if Tier 1 exhausted its budget without settling. Sibling functions, related CVEs in the library family, forked/vendored copies carrying the pattern, same bug class in the framework/runtime. Budget: at most 5 distinct queries or one 15-minute sweep. Escalate only on pattern-present-but-unresolved.
  - **Tier 3 (deep):** only on Tier 2's pattern-present-but-unresolved verdict. Diff every tagged release for silent (un-CVE'd) fixes (the nday skill's methodology), conference talks / CTF write-ups for the technique class, academic literature for the pattern's general form. Budget: one declared deep pass per hypothesis; a second needs new input (same rule as deadend re-opens).
- **Route the result:**
  - Tier 1 finds the finding ALREADY PUBLIC (existing CVE, vendor advisory, upstream fix commit covers it) -> reclassify `n-day (CVE-<id> or upstream-fix)`, log `` `reclass: <id> discovery -> n-day (<source ref>)` `` in `loop.md`, hand off to `Skill(nday)` entry path 3. A failed n-day trigger (the patch does not cover this instance) routes the finding BACK to the discovery path with a log line.
  - Nothing settles it -> genuinely new + reachable -> **candidate CVE** (section 8 unchanged).
- **Source-tag every fact:** ``(source: <kind> <ref>, fetched <date>)`` on one line, recorded in the ledger entry and in `findings.md`/`surface.md` prose where the fact is used.
- **Research ledger (dedup, MANDATORY):** before ANY fetch, check `raw/research/<project>/.research.json`. A `settled` entry on the topic ENDS the question: reuse its verdict + sources, never re-fetch. A `pattern-open`/`nothing` entry allows ONE re-query per higher tier. The objection-seed queries are exempt (they always run). After the pass, append the entry (topic = component + version + question class, lowercase english):
```json
{"topic": "<component> <version> <question class>", "tier": 1,
 "verdict": "settled|pattern-open|nothing",
 "sources": [{"kind": "nvd|ghsa|osv|changelog|web|wiki|diff",
              "ref": "<url or page or commit>", "fetched": "<iso date>"}],
 "used_by": ["<hypothesis or row id>"], "ts": "<iso datetime>"}
```
Missing/corrupt ledger = write the first entry, never an error.

## 8. Write up (CVE-grade)
Promote the proven finding in `findings.md` (or a dedicated FIND file): title, affected versions, root cause, PoC, primitive/impact, CVSS, remediation, disclosure note. Then **feed the reusable technique/pattern back to the wiki** (`wiki/techniques/` or `wiki/payloads/`) via the `research-ingest` skill - so the next project starts ahead.

---

## Loop control (the state machine)
```
setup -> surface-map -> hypothesize -> investigate -> evaluate
   evaluate: finding  -> deepen -> prove -> writeup -> (variants? back to hypothesize)
   evaluate: nothing  -> deadend -> hypothesize (different approach)
   all hypotheses exhausted -> step back: re-map a different component (2),
                               try a new target-type angle, or note the target looks hardened.
```
- Log **every** iteration to `loop.md` as `Iter N (date): <approach> -> <result> -> <next>`. Update `findings.md` / `deadends.md` before you stop. State persists across sessions - a later session resumes the loop from `loop.md`.
- Stop conditions: a proven novel vuln (success), or all current hypotheses exhausted (record the frontier + suggested new angles).
- Objection seed (WS1): when the target pattern has a Deadends.md entry with
  cause `insufficient` carrying an `objection:` line, that objection is the
  FIRST query of the pass (translated to English search terms; original-language
  values stay in the finding). A research pass that skips an available
  objection seed is a miss - lane briefs carry this clause verbatim.
- Research ladder in every brief (P2): lane briefs carry the tier ladder + ledger rule verbatim, the same contract as the objection-seed clause. A research pass that skips Tier 1 or re-fetches a `settled` ledger topic is a miss.

## Output every iteration
`Iter N: <approach> -> <result> -> <next move>`, plus which files you updated. Keep the human in the loop on each pivot and each finding.

## Deadends (format)

One row per dead-end, appended the iteration it dies:
`- [ ] <project> -- <approach> died because <evidence>; revisit when <trigger>.`
Never re-run a logged dead-end without the named trigger firing
(anti-loop rule). deadends.md is read BEFORE acting, every session.
