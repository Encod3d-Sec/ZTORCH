---
name: triage
description: Finding validation gate - 7-Question triage adapted for the FIND schema. Use before any FIND moves from Research to Completed; one NO keeps it in Research.
metadata:
  hermes:
    tags: [triage, gate, g1, severity]
    related_skills: [evidence, hunt-core]
---

# Triage: Finding Validation Gate

Use BEFORE moving any FIND from `Vulns/Research/` to `Vulns/Completed/`.

One wrong answer = keep the finding in Research. Move on to next test class.

---

## Wiki

Hub: [[methodology-moc]] - Primary page: [[vuln-assessment]]
Anchors: [[vulnerability-reports]], [[safe-probing-and-controls]]
**REFS:** [[vuln-assessment]]

## THE 7-QUESTION GATE

Ask in order. One NO = STOP for this finding.

### Q1: Can an attacker use this RIGHT NOW, step by step?
Complete this template:
```
Setup:   I need [own account / another user's ID / no account / internal access]
Request: [exact HTTP method, URL, headers, body -- copy-paste ready]
Result:  I can [read / modify / delete / execute] [exact data or action]
Impact:  The real-world consequence is [specific impact]
```
If you CANNOT write the Request line as a real reproducing command -> keep in Research.

### Q2: Is the impact within engagement scope?
- Does it affect an in-scope asset?
- Does the impact match the severity level being claimed?
- Not a third-party service the target merely uses?

### Q3: Is the root cause in an in-scope asset?
- Production asset (not staging/dev unless in scope)
- Not out-of-scope subsidiary or third-party

### Q4: Does it require privileged access that an attacker cannot realistically obtain?
- "Admin can do X" = not a finding
- "Non-admin can do X that only admin should do" = valid
- Pre-auth or low-auth is highest value

### Q5: Is this already known or documented?
- Check Vuln-index.md - not already listed?
- Check Deadends.md - not already investigated and closed?
- Not design-documented behaviour?

### Q6: Can you prove impact beyond "technically possible"?
- XSS -> show actual session theft or action execution, not just alert(1)
- SSRF -> confirm OOB callback (DNS/HTTP), not just URL echo in error message
- SQLi -> show actual data extracted from a real table
- IDOR -> show actual other-user data in response body, not just 200 status

**Authz gate (two-account, hard):** an access-control finding is proven ONLY by the
OTHER account's data appearing in your response. An empty 200 is NOT access (the server
may null-fill or silently drop); a 200 echoing your own request is your own data. Run
the pair: embed a unique canary as account A, request it as account B; B sees the canary
= proven. No second account available -> ask the operator for a second address (or a
test-pair provision) BEFORE downgrading or deadending the finding; "could not test
cross-account" is an unresolved row, not a negative.

### Q7: Not on the Never-Promote list?
Never promote to Completed without a chain:
```
Self-XSS only (no CSRF trigger)
Open redirect alone (no OAuth/ATO chain)
CORS wildcard without credentialed exfil PoC
SSRF DNS-only (no internal service access)
Rate limit without demonstrated impact
Version banner alone
Missing headers alone (no impact PoC)
```

Before promoting: run the chains-into check - which existing findings share a component, auth context, or data flow with this one; record the answer in the finding card.

---

## Proof gate (G1 per-finding validators)

Independent of the 7 questions: a finding moves to Completed ONLY when it
carries one of these three proof primitives, named in the FIND with a concrete
artifact reference. Artifact existence without a primitive (a screenshot of a
200, a saved response, a tool banner) is not proof; "I have a PoC" is not a
primitive. Cited practice: XBOW validators prove execution (S1); precision over
recall - the gate may hold findings back, never wave them through.

1. **execution-observed** - the payload's effect is seen in fetched or rendered
   output produced BY the payload: headless-browser render where the script
   runs, command output in the response, a template expression evaluating.
2. **diff-observed** - a controlled before/after: attack vs benign control
   request diverging on the injected branch only, or account B's response
   containing account A's canary. No negative control = no diff.
3. **sentinel-returned** - a sentinel you planted comes back on a channel you
   own: an OOB callback hitting your listener (`oob.md` row flipped to HIT), or
   an injected unique canary returning in content you later fetch.

Claiming a primitive without its artifact is `hallucination` in the drift
taxonomy. A finding that cannot carry any primitive stays in Research.

Minimum primitive per class (a stronger primitive on the row also satisfies):

| Class | Primitive | Proof artifact |
|---|---|---|
| XSS (reflected / stored / DOM) | execution-observed | headless render of the page: payload executes (dialog, sink side effect, DOM change) under the unique canary; screenshot + console trace |
| SQLi (error / boolean) | diff-observed | attack vs control request diverges on the injected branch only; re-run both to confirm stable |
| SQLi (blind / time) | sentinel-returned | OOB callback hit; time-based inference alone does NOT pass (hunt-core rule 4: no inference-only findings) |
| SSRF | sentinel-returned | OOB callback from the target's egress, `oob.md` row HIT; internal reach shows in the callback path |
| IDOR / access control | diff-observed | account B's response contains account A's canary data (two-account rule); an empty 200 is not a diff |
| Command injection / RCE | sentinel-returned | OOB callback fired by an executed command, or the command's own output in the response |
| SSTI | execution-observed | injected expression evaluates (arithmetic payload returns computed value) or triggers an OOB fetch |
| XXE | sentinel-returned | OOB fetch of an attacker-controlled DTD, or target content arriving in the callback |
| Deserialization (blind) | sentinel-returned | OOB callback from the first-stage gadget |
| File upload to execution | execution-observed | uploaded file fetched back and executed/rendered (webshell output, SVG XSS firing in a browser) |
| Open redirect | execution-observed | redirect followed end-to-end; canary lands on an attacker-controlled host in your own access log |
| Cache poisoning | diff-observed | a second clean unauthenticated session receives the content the attacker planted |
| Request smuggling | diff-observed | a second request through the desynced connection returns the smuggled prefix's effect |
| LFI / path traversal | diff-observed | traversal response returns known file bytes absent from the benign request |
| Auth bypass / logic | diff-observed | protected action succeeds from an unauthenticated or low-priv session while the control request is denied |
| Secrets / config exposure | diff-observed | secret validated by USE (auth succeeds, resource fetches); the leak alone is a lead, not the primitive |

Blind classes are pinned to sentinel-returned: the hunt-core OOB gate already
forbids inference-only findings and this table must not undercut it. This gate
EXTENDS Q6 and the verifier lane; it does not replace them - Q6 asks "did you
prove impact", this gate fixes the closed vocabulary of what counts as proof.

## Cross-tool correlation pass (G9)

Run ONE explicit pass before lane close whenever the run recorded 2+ findings,
ANY severity, across tools (nuclei + burp/caido + manual). Widen the chaining
pass below from lows-only to this trigger; the model does not correlate
unprompted - the pass IS the prompt.

1. Collect the run's finding records across tools: nuclei output, proxy
   history (`requests.md` rows + captures), manual FINDs in `Vulns/Research/`.
2. Pair or chain records sharing a host + parameter + data-flow link (one
   finding's output feeds another's input). Each link yields a compound
   candidate: `FIND-A + FIND-B -> chained impact`.
3. For each candidate propose a validation path: the proof primitive from the
   table above plus the concrete request sequence demonstrating the chain.
4. Append candidates to the Research queue. Correlation NEVER promotes: each
   candidate still passes its own validation path and the 7-question gate.
5. A candidate with no data-flow link or no validation path is discarded in one
   written line. Bad compound candidates cost human attention at the gate.

---

## Pre-Severity Gate (run before labelling CRITICAL or HIGH)

1. Have you validated the FULL chain to attacker-attainable impact, or only one primitive?
2. What does the attacker walk away with in one concrete sentence?
3. Have you reproduced the full chain end-to-end at least twice?
4. Is there a validation step (signature check, audience check, MFA) still gating the chain?

A "primitive confirmed" != exploitable. Downgrade until the gate is bypassed.

Independent-industry corroboration (Armada talk, HermesTORCH docs/hackbot-port.md 2.1):
"the AI drastically overrates the criticality of the vulnerability" - expect
the finding to be a class lower than the discovering agent claimed, and rate
from the demonstrated template in Q6, not the lane's adjective.

---

## Decision

| Result | Action |
|--------|--------|
| All 7 YES + Pre-Severity Gate clean + a proof primitive named (see Proof gate) | Move FIND to Vulns/Completed/ with frontmatter status CONFIRMED or EXPLOITED (DETECTED alone stays in Research). Update status in Vuln-index.md. Run `python3 scripts/find-lint.py` and fix any gaps (Description/PoC/Impact/Remediation + CVSS for HIGH/CRITICAL) so it is report-ready. Then run /evidence. |
| Any NO | Keep in Vulns/Research/. Update status to PARTIAL (reason) in Vuln-index.md. Document what is missing. |
| Q7 chain required | Move to Vulns/Research/ with note "chain required: [what is needed]". |

A scanner/tool hit without a validated PoC is DETECTED, never Completed; the find-lint gate refuses CONFIRMED/EXPLOITED without a poc/ capture reference.

Chaining pass: when an engagement records 2+ findings that each scored low,
run ONE explicit low-chain prompt before closing the class (redirect + auth
bypass + token-in-URL class chains): "combine the recorded lows into
primitives and test the chains." The model does not chain lows unprompted;
left unchained they stay breadcrumbs.
