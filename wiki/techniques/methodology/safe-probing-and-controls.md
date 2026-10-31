---
title: "Safe Probing and Controls"
type: technique
tags: [methodology, testing, evidence, false-positives, sensitive-data, web]
phase: exploitation
date_created: 2026-08-04
date_updated: 2026-10-31
sources: [github-usestrix-strix]
---

## What it is

Techniques for testing destructive or sensitive surface without touching real records, and for making a
negative result mean something. The theme: **make the probe safe by construction rather than by care**,
and **fire a control before believing anything**.

Most apply anywhere. They matter most on production systems holding real people's data, where "I was
careful" is not an acceptable answer if a probe lands.

## Probe destructive surface with an identifier proven not to exist

To test whether `DELETE`/`PUT`/`PATCH` routes enforce authorization, you do not need a real record.
Establish an identifier that resolves to nothing (a high id whose absence you have already demonstrated
on a read route), then use it everywhere.

The classification still works, and is arguably cleaner:

| Response | Meaning |
|---|---|
| `401` / `403` | Gate fires before the lookup. Holds |
| `404` naming the ORM's resolver | Lookup ran before authorization - the finding |
| `405` | Verb not routed here |
| `400` / `422` validation error | **Controller reached. Gate did not hold** |
| any `2xx` | Impossible by construction. STOP, capture once, report |

Because no record exists at that address, a missing gate cannot damage anything. This converts "do not
test write verbs on production" into "test all of them, safely".

**The residual gap, and state it rather than papering over it:** you only ever observe the
*absent-record* branch. Whether authorization blocks the write against a *real* id is unproven, and
proving it would mean sending a destructive verb at a live record. On sensitive systems that trade is not
worth making - disclose the limit as an inference instead of quietly implying you tested it.

**Unparameterised creation routes have no such protection.** A `POST /api/thing` with no id in the path
cannot be aimed at a nonexistent record. Probe those last, one at a time, with a body that cannot
validate (empty object first), and halt the whole sweep on any `2xx` rather than continuing down the list.

## Structurally impossible identifiers for identity-keyed routes

Routes keyed by a national identity number, tax id or similar are more sensitive than row-id routes: the
oracle answers "is this named person enrolled", not "does row 500 exist". You still need to reach the
controller, and the route's own regex forces the format.

Use a value that **satisfies the format but cannot belong to a human**. Most national identifier schemes
make this easy:

- a leading digit encoding century/gender with a restricted range - use a value outside it
- an embedded date - use an impossible month or day
- a checksum digit - deliberately wrong

Example shape: for an 11-digit code whose first digit is always 1-6, `00000000000` matches `\d{11}`,
reaches the controller, and corresponds to nobody.

**Never construct a valid one, never increment toward one, never search for one.** If you find yourself
computing a checksum, stop. And accept the consequence: you can prove reachability and the absent-branch,
but the exists-branch is unprovable without a real person's identifier. Say so rather than implying
coverage you do not have.

## The functional control: prove the endpoint works before trusting a negative

An endpoint returning empty for every payload looks like a clean negative. It looks identical to an
endpoint that is broken, filtered, or silently rejecting your input.

Before recording the negative, send a value you know should MATCH and confirm real data comes back.

```
GET /api/address/x4hd2k9pq   -> 200 []      # sentinel: no match
GET /api/address/Vilniaus    -> 200 [...]   # FUNCTIONAL CONTROL: endpoint genuinely works
GET /api/address/Vilniaus'   -> 200 []      # quote collapses a real match -> parameterised query
```

The third line is only meaningful because the second exists. Without it you know only that the endpoint
returns empty, which proves nothing about injection. **A negative without a functional control is an
assumption wearing a result's clothes.**

A terminal rewriting output with carriage returns is SUPPRESSING content,
not returning empty: force a raw capture to file (pipe through `cat -v`,
or use the tool's raw-output flag) and read the file before concluding
anything about the response. CR-overwritten lines hide exactly the output
the probe was sent to collect.

## The opposite-payload pair

For any boolean-oracle claim (SQLi, existence checks, filter bypasses), send semantically OPPOSITE
payloads and compare byte-for-byte:

```
...?filter=1=1   ->  200, 2 bytes
...?filter=1=2   ->  200, 2 bytes     # byte-identical -> NO ORACLE
```

Uniform responses across opposite payloads mean a rejected parameter, or an edge filter answering for the
origin. It means "no oracle here", never "vulnerable". One of the most common false positives in web
testing, and trivially avoidable.

## Both branches, or it is not a differential

Any claim of the form "X behaves differently from Y" requires observing **both X and Y yourself, live, in
the same session**. A differential inferred from one observed branch plus an assumption about the other is
not a differential.

This applies to existence oracles, auth bypasses, cache behaviour and signature checks alike - for a
signed-fragment endpoint, "no signature" and "wrong signature" are two different tests and neither
substitutes for the other.

## Byte size is the discriminator, not status

Where several mechanisms produce the same status code, record **exact byte size with every request** and
build a table of known signatures before hunting. Status alone routinely conflates:

- a framework's "route not registered" versus "route exists, lookup failed"
- an application error page versus a CDN/WAF block page
- a rate-limit page versus a rule-based deny

Byte size separates them instantly and cheaply. Build the table first, from live requests, and treat any
size not in it as worth classifying from first principles rather than assuming.

## Watch for artifacts you manufactured yourself

Several "findings" are produced by the tester's own request options:

- Forcing `Accept: application/json` can produce a `406` on routes that behave completely differently
  without it. Re-issue with no added headers before recording.
- Non-canonical HTTP verb casing may be rejected at the edge and never reach the origin - a *more*
  restrictive result, not a bypass.
- Headers like `X-Original-URL` / `X-Rewrite-URL` are often blocked by the edge on the header NAME, so
  the block says nothing about the application.
- A one-shot response that will not reproduce (an interstitial, a waiting-room page, a challenge) is not
  evidence. Re-issue before recording anything.

When a probe's result depends on an option you added, that option is part of the finding - or it is the
whole finding, and there is nothing else there.

## Do not generalize a route/verb signature across a host

Two independent shapes of the same mistake:

- **Verb generalization.** Proving "validation runs before the authorization check" on one verb
  (e.g. DELETE, using a real owned record) does not establish the same for a sibling verb (e.g.
  PATCH) on the same resource. Separately attached handlers can carry different validation
  pipelines even when the URL looks identical. Re-test the auth-order question per verb.
- **Route generalization.** A method-existence heuristic (which status means "route exists but
  wrong verb" vs "route absent") learned on one path prefix can be INVERTED on a sibling prefix of
  the same origin, when two different frameworks/proxies front different paths. A random-path
  control plus the response's `Allow:` header settles it, not the pattern learned elsewhere.

Treat every route x verb combination as needing its own control, even after a signature is
confirmed elsewhere on the same host.

## Timing oracles need a live baseline, not a fixed threshold

A `SLEEP(3)`-style payload can return in about 1.1 seconds against a plain baseline that itself
ranges from roughly 0.6 to 12 seconds across the same test session (shared/noisy hosting, or an
edge queueing requests). Reading a fast response as "definitely no injection" is wrong; the correct
read is "inconclusive by noise" and the case should close on a cleaner signal instead (e.g.
response-size arithmetic) if one is available.

Never compare a time-based payload's response time against an absolute number pulled from memory or
a single earlier request. Resample a same-session, same-conditions baseline immediately before and
after the payload request, on hosts where response time is not already known to be stable.

## Automated recon must gate on real requests, not on strings in displayed content

An automated hook that watches command output for "newly discovered hosts" and auto-launches
recon/scanning against them is a scope hazard if it cannot distinguish a host actually REQUESTED
from a hostname that merely appears inside content the agent read and printed (a vendor's own
example URL in leaked documentation, a string in a downloaded file). Reading a document must never
be able to trigger outbound traffic to a third party named inside it.

This failure mode is not theoretical: it has fired via a leaked vendor guide's example request URL
and via a stale scope pointer, each time causing an automated scanner to fire against a host never
in scope.

Fix: gate the auto-recon trigger on the URL/host actually being the target of a command that made a
network request, and separately hard-check the candidate host against the written scope list before
launching anything, do not rely on a general scope filter alone if a different code path can bypass it.

## Test a suspected disclosure endpoint with an empty input to rule out an echo

A response that appears to disclose server configuration (an install directory, a resolved file
path, a base URL) from a request parameter you control is not proof of disclosure by itself. Some
endpoints just concatenate the caller's own value with a static prefix/suffix and return that.

Resend the same request with the suspect parameter set to EMPTY. Two outcomes:
- the reply changes to exactly the static text alone, with no earlier "resolved" value surviving ->
  it was an echo of your own input the whole time, and every earlier response was your own guess
  handed back to you, not real information.
- the reply still contains a full, unrelated value -> genuine server-side disclosure, now confirmed.

Do this before citing any single-request "disclosure" as evidence; a plausible-looking path
assembled from a guess plus a real-looking suffix is easy to mistake for a resolved server path on
one read.

## Three-state closure: a candidate is closed only by naming the control

Every opened candidate ends its life in exactly one explicit state: **confirmed**, **ruled_out**, or
**open_proof_gap**. "I moved on" is not a closure state. Silently dropping an uncertain candidate is
mislabelling an open_proof_gap as ruled_out, and that is how real bugs get missed.

`ruled_out` has a mechanical test, not a feeling. You must be able to write one sentence of the form:

`This is safe because <control> at <file:line or observed behavior> <does what> before <sink>, on every path an attacker can reach.`

If you cannot fill in every slot, the candidate is not ruled out. The standard non-rulings:

- **"It looked fine" / generic library trust.** A helper or framework being generally reputable is
  not counterevidence for one call site.
- **A safe sibling.** A correctly parameterized query three lines above a concatenated one proves
  the developer knew better; it proves nothing about the concatenated one.
- **Missing information.** No caller found, cannot tell whether it is deployed or exposed, could
  not stand up the service, build failed: each is an open_proof_gap, never a reason to mark a
  candidate clean. Missing information is not proof of safety; difficulty is a reason to defer,
  not to suppress.
- **Being internal.** Internal-only, admin-only, or authenticated-only reduces severity; it does
  not make the finding unreal. Downgrade it; do not delete it.

A negative control strengthens a closure: send the payload that SHOULD work if the bug were real
and show it is blocked, while a benign variant succeeds (the functional-control pattern above is
the special case). "Blocked where it should pass, passes where it should" beats "returned an
error" every time.

ZTorch mapping: a Deadends.md row IS a ruled_out and must carry the named-control sentence;
anything you could neither confirm nor rule out stays on the board (open row or needs_follow_up
below), never a deadend line.

## Argue the other side before filing: counterevidence, confidence, severity

Before a candidate is filed as a finding, spend real effort building the strongest case that it is
NOT exploitable, and record the result as the counterevidence field. Two companions travel with it:

- **confidence**, on a ladder: high only with an executed PoC against the live target or a complete
  source-to-sink trace; strong evidence you could not fully execute is medium WITH the gap named;
  plausible with a material unresolved gap is low. Do not inflate; an accurate medium is more
  useful than a high that fails triage.
- **severity_change_conditions**: the one concrete piece of evidence that would raise or lower the
  rating. "If an admin interface were internet-facing" or "if the same request worked
  unauthenticated". This is what makes a later re-rating a response to evidence instead of mood.

Severity is a conclusion, not an opening position: calibrate AFTER reachability and the
counterevidence pass, never before. Missing evidence about deployment or exposure lowers your
confidence, not the severity floor. Score only the impact the PoC demonstrates; never score
speculative pivots that require another unverified vulnerability. Two calibration rules that
correct most drift:

- Session-management weaknesses that require the attacker to already hold a victim secret are
  usually low/medium: the acquisition of that secret is not free, and unless the same finding
  shows how to obtain it, it does not carry that weight.
- The acceptance test is "would you defend this rating in a client debrief / would serious audit
  triage accept it at this band".

Related filing rule (revise vs delete): a finding that turns out real but weaker than filed is
REVISED with the reasoning updated, never deleted; deletion is for things that were never
vulnerabilities at all. And when a rating changes, the old rationale must not survive beside it;
stale reasoning next to a new severity is how a report contradicts itself.

## Coverage rows carry outcomes, and the outcome gates evidence

Record every surface you assess, including the ones that came back clean; a report that only lists
findings cannot say what was reviewed and cleared. Each row ends in one of five outcomes:

- `reported` - a finding was filed for this surface
- `no_issue_found` - tested, nothing wrong
- `ruled_out` - you had a specific candidate and disproved it (named-control sentence required)
- `not_applicable` - the class cannot apply here (reason required)
- `needs_follow_up` - unresolved; what is still missing (named)

`ruled_out`, `not_applicable` and `needs_follow_up` REQUIRE an evidence/reason cell; "evidence is
required for outcome ruled_out - name the specific control, the reason it does not apply, or what
is still missing". Never use `no_issue_found` or `ruled_out` to close something you were simply
unsure about: that is `needs_follow_up`. Unsure is a status, not a clean result.

One row per surface. When the conclusion changes, UPDATE the row (the superseded outcome and
author stay visible as history); never record a second row beside the first. Two rows for one
surface leave the report showing a stale conclusion next to its replacement.

## Proxy error pages are never target behavior

An interception proxy under load returns its own error HTML (Caido observed: a roughly 9KB page
carrying the proxy product's own title/status markup under 502/500), and curl, python, or a
browser will print it as if it were the target's content. This is the tooling-manufactured
artifact family above with a new manufacturer: NEVER treat such a page as a finding, as evidence,
or as a WAF fingerprint. Recognize the shape (proxy branding, boilerplate body, status that
matches a proxy failure, not an application route) and re-verify through a healthy proxy or
direct before recording anything derived from it.

## Related

- [[bug-hunting-methodology]] - where these fit in an overall test plan
- [[vulnerability-reports]] - stating limits and inferences honestly in a write-up
- [[access-control]] - the class most write-verb probing targets
- [[multi-agent-campaign-orchestration]] - the fleet-level closure census and dedupe boundary
- [[agentic-harness-patterns]] - strix framework distillation and the absorption map

<!-- promoted-slug: safe-probing-and-controls -->

<!-- promoted-slug: a-behavioral-or-authorization-signature-confirmed-on-one-rou -->

<!-- promoted-slug: a-timing-oracle-result-must-be-compared-against-a-fresh-same -->

<!-- promoted-slug: automated-recon-scan-hooks-must-trigger-only-on-hosts-actual -->

<!-- promoted-slug: an-endpoint-that-appears-to-disclose-a-server-side-configura -->

## An unobservable exfil channel produces false negatives

Before reading "no callback" as "payload failed", verify the observation channel itself: an
exfil webserver whose output goes to a tmux pane that captures empty (or a log you are not
reading directly) turns every real hit into an apparent miss, and the vector gets written off as
dead. Run the listener with file redirection (`> /tmp/hits.log 2>&1`) from the start and read
the file; treat any zero-hit conclusion drawn from an unobservable channel as unproven.

<!-- promoted-slug: oob-listener-observability -->

## Equal size, different md5: CDN challenge injection is not server variance

Two same-status responses of EQUAL byte length that hash differently: diff before recording "identical". A CDN (Cloudflare observed) injects a per-request inline challenge script into page bodies:

```text
<script>window.__CF$cv$params={r:'<per-request ray id>',t:'<base64 timestamp>'}</script>
```

The ray id and timestamp change every request, so body LENGTH stays constant while the md5 moves. When the diff shows this marker (or the CDN's equivalent) as the ONLY delta, record "identical modulo CDN challenge injection" and move on; any other delta line at equal size is real server-side variance and worth reading line by line.

<!-- promoted-slug: cf-challenge-injection-identical-modulo-correction -->

## Never install a non-scoped intercept rule on the agent seat

A root-scoped `iptables -t nat -A OUTPUT -p tcp --dport 443 -j REDIRECT` on a WSL2 host also redirects the API stream of any LLM-agent CLI running on that same host, killing the session mid-run: agent traffic to its own provider matches the same rule.

Rule: never install a non-uid-scoped intercept rule on the seat an agent session runs on. Prefer passive capture (tcpdump for plaintext SNI) and offline data pulls (app cache tar) when the analysis seat and the agent seat are the same machine. If active interception is unavoidable, scope the rule to the target app uid and exclude agent traffic first.

<!-- promoted-slug: wsl-iptables-redirect-kills-agent-session -->
