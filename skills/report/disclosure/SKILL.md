---
name: disclosure
description: Responsible disclosure path from a found vulnerability to a published CVE (packaging, vendor contact, private report, timeline, advisory). Use when asked to "disclose", "request a cve", or "report this to the vendor".
metadata:
  hermes:
    tags: [disclosure, cve, cna, timeline]
    related_skills: [nday, research]
---

# Disclosure: Finding -> CVE

Turn a proven, novel vulnerability into a coordinated disclosure and a published CVE. Pairs with the `research` skill (a finding in `findings.md`) or an engagement FIND. Read [[responsible-disclosure]] first.

## Gate (READ FIRST)
- The finding must be **proven + reproducible** (minimal PoC, affected versions, impact) and **novelty-checked** (not an existing CVE). If not, go back to the `research` skill.
- Confirm you are **authorised / in safe-harbor** for the target. No authorization -> do not proceed (CFAA / Computer Misuse Act). Research on public software you can lawfully analyze is fine; testing live third-party systems needs permission.

## Procedure
1. **Package the report** from the finding: title, affected + fixed/tested versions, CWE class, CVSS vector + score, clear repro steps, minimal PoC, impact, suggested remediation, your contact. Redact any real data.

   **Report shape (the operator's standing bar - no filler, no hedging, no AI-slop prose):**
   - Pull every request/response byte VERBATIM from the evidence files on disk - never
     paraphrase or retype a response; read the artifact file and quote it. A report whose
     responses were reconstructed from memory is not reportable.
   - ROOT-CAUSE PROSE FIRST: one paragraph explaining the exact mechanism in named terms
     (op names, resolver behavior, state fields - or function/file/line for code) BEFORE
     any evidence or steps. The triager must understand WHY before HOW. (H1 #4030333 model:
     staff praised exactly this + the reproducer.)
   - PRECONDITIONS SPLIT trigger-vs-exploitation: "X triggers the flaw; Y is additionally
     needed to weaponize." Severity negotiation lives on this split - overclaiming costs
     credibility, and stating the constraints yourself beats staff finding them.
   - Section order: Summary (root-cause paragraph + the key facts table) -> Impact (ONE
     blunt sentence, then numbered concrete impact; constraints live here, not hedged
     into the impact line) -> "what we verified is NOT possible" (closes the adjacent
     escalation paths so severity is never overstated - vendors triage on this) ->
     Reproduction (copy-pasteable commands, exact headers, an EXPECTED-OUTCOME line in
     every step block - a triager must never wonder whether it worked - then the verbatim
     response with its properties annotated) -> Remediation (ordered, actionable, and
     INCLUDE the suggested fix - we have the code understanding; collaborators file
     patches, not tickets) -> Evidence-pack index (artifact table) -> Boundary-testing
     appendix (test/request/result table) + annotated request/state timeline with the
     authz/state boundary crossing labeled at the exact step (web analog of the call tree).
   - Include a PURGE LIST: every test artifact identifier written or minted (canary
     object keys, created resources), split into "confirmed written" vs "minted but
     never used" - the vendor's cleanup crew needs it, and it proves test discipline.
   - State the testing bounds explicitly (bounded counts, own-accounts-only, what was
     deliberately NOT fired) in one closing paragraph - it is part of the evidence.
   - MECHANICAL FORMAT LAW (operator 2026-10-14): one paragraph = ONE source line - never
     break a sentence across source lines (lists/tables/headings/code fences excepted);
     markdown flows at render. NO em-dashes (- or -) anywhere: use ' - ' (plain hyphen) or
     restructure with a comma/colon. Before filing, sweep the draft for both.
   - DELEGATED WRITES ARE VERIFIED, NEVER TRUSTED: when a subagent (or any delegated
     writer) produces report files, run your own mechanical sweep over the finished
     files (wrapped-paragraph detector outside code fences + em-dash grep) instead of
     accepting "formatting applied" claims - a writer under iteration pressure wraps
     prose inconsistently and self-verification misses it. Evidence gaps get explicit
     TODO-evidence markers, never invented bytes; a report is fileable only when the
     sweep is clean and every TODO is either closed or consciously accepted.
   - Verdict tables over prose wherever a table fits; every claim carries its artifact
     name. No 'consider', no 'might', no restating the summary in new words.
2. **Find the contact** (in order): `/.well-known/security.txt`, `SECURITY.md`, `security@<vendor>`, vendor PSIRT, a bug-bounty platform if they run one, GitHub private vulnerability reporting for OSS, else CERT/CC.
3. **Report privately** over that channel; PGP-encrypt if a key is published. Professional, specific, non-extortive. Offer to validate the fix.
4. **Coordinate a timeline** - propose ~90 days; track it; escalate to CERT/CC if the vendor goes dark past the deadline.
5. **Request the CVE:** vendor CNA assigns it; for OSS open a GitHub Security Advisory (GitHub issues the CVE); otherwise MITRE CVE request form (CNA of last resort). Supply product, versions, CWE, impact, reference.
6. **Publish the advisory** after fix/deadline: CVE ID, affected/fixed versions, CWE, CVSS, description, PoC, impact, remediation, timeline, credit. Mirror to the researcher's blog/GitHub for the portfolio.

## Output
- A ready-to-send **disclosure report** (draft) and a **public advisory** (draft) saved under the project: `raw/research/<project>/advisory.md` (and the contact + timeline tracked in `findings.md`).
- Update the finding status: candidate -> reported -> `CVE-<id>` -> published.

## Wiki feedback
Reusable disclosure lesson (vendor process quirk, CNA tip) -> update [[responsible-disclosure]]. The vuln technique itself -> the matching `wiki/techniques/` page via `research-ingest`.

Report: report + advisory drafts, contact channel, and the disclosure timeline.
