---
name: evidence
description: Evidence hygiene for a FIND heading to Completed or a report (redaction, PII black-bar, HAR sanitization, screenshot metadata strip). Use after /triage passes and before final report assembly.
metadata:
  hermes:
    tags: [evidence, redaction, har-sanitize]
    related_skills: [triage, walkthrough]
---

# Evidence: PoC Capture & Redaction Discipline

Run this BEFORE attaching any screenshot, HAR, or request/response to a finding report.

---

## Wiki

Hub: [[methodology-moc]] - Primary page: [[vulnerability-reports]]
Anchors: [[safe-probing-and-controls]]
**REFS:** [[vulnerability-reports]]

## Pre-Screenshot Checklist
```
[ ] Network tab Headers panel collapsed or out of frame
[ ] Burp Request panel hidden behind divider
[ ] No "Copy as cURL" output visible on screen
[ ] DevTools Application -> Cookies tab closed
[ ] Browser URL bar does not show a session token in query string
```

## Cookie / Token Redaction

**Must redact:**
- Session cookie value (authn, session, sid, __Secure-id, etc.)
- CSRF tokens bound to the session
- Authorization headers (Bearer tokens, JWT)
- Cookie and Set-Cookie header values for session-bearing cookies

**Safe to leave:**
- Cloudflare cookies (__cf_bm, _cfuvid)
- Analytics cookies (_ga, ajs_anonymous_id)
- Trace IDs (x-datadog-trace-id, x-request-id) - help triager correlate logs

**Redaction method:** black rectangle annotation over the cookie value in your image editor. OR use DevTools `credentials: 'include'` in fetch PoC so cookies never appear in the screenshot.

## HAR Sanitization
```bash
# Save this as ~/bin/sanitize_har
sanitize_har() {
  local input="$1"
  local output="${1%.har}.sanitized.har"
  jq '
    .log.entries |= map(
      (.request.headers |= map(
        if .name | ascii_downcase | IN("cookie", "authorization", "x-csrf-token")
        then .value = "<REDACTED>" else . end
      )) |
      (.response.headers |= map(
        if .name | ascii_downcase | IN("set-cookie") then .value = "<REDACTED>" else . end
      )) |
      (.request.cookies |= map(.value = "<REDACTED>")) |
      (.response.cookies |= map(.value = "<REDACTED>"))
    )
  ' "$input" > "$output"
  echo "Sanitized: $output"
}
# Verify:
grep -i 'authorization\|"cookie"\|set-cookie' "${1%.har}.sanitized.har" | head -5
```

## PII Black-Bar Protocol

When PoC exposes another user's data (IDOR, etc.):
- Mask: real names, email local part, phone last 7 digits, addresses, faces
- Leave: JSON key names, your own test-account UID, trace IDs, request shape

In report body: state "Real PII fields masked with black rectangles per responsible-disclosure hygiene. Unredacted version available on request."

## Screenshot Filename Convention
```
FIND-XXX-step1-pre-state.png
FIND-XXX-step2-exploitation.png
FIND-XXX-step3-post-state.png
```

## Finding Registration (index at write time)

The moment a finding write-up exists, it is REGISTERED - same step, never
later:
- report file lives at `Vulns/FIND-XXX-<SEVERITY>-<slug>.md` (XXX sequential
  per the engagement's Vuln-index.md)
- one row appended to `Vuln-index.md` under its severity table: ID, title,
  host, status.

A report sitting at the engagement root (or anywhere outside `Vulns/`) with
no index row is an UNTRACKED finding: it exists but is invisible to the
dedup gate, the operator, and close-out. The filing is not a cleanup-time
chore - an unindexed report is indistinguishable from a lost one.

MIRROR-TREE SWEEP: engagement artifacts live in BOTH the vault `targets/<eng>/`
and the VM-side working copy (VMshare mirror of the same engagement). Lanes
that run on the VM write reports, Killchain sections, and agent-reports ONLY
there. Before answering "what findings exist" or assembling any consolidated
writeup, sweep BOTH trees for `FIND-` references and reconcile them into the
vault index - a FIND that exists only in the mirror is untracked by the same
rule as one sitting at the engagement root.

LANE CWD DRIFT: a subagent told to write "Vulns/..." resolves it against ITS
cwd - usually the engagement ROOT, not `targets/<eng>/` - producing a second
`<root>/Vulns/` tree that shadows the canonical one. After any rewrite wave,
sweep the mirror for a freshly-created `<root>/Vulns/` and reconcile before
the trees diverge further; canonical FIND location is the vault
`targets/<eng>/Vulns/`.

Auto-captured `poc/NN-*-auto.md` cards are regex SIGNALS, not findings: on
web engagements GraphQL/JS brace patterns (`queryType{name}`,
`catch{return!0}`) dominate false positives - read the captured pair before
counting any card as real; only a triaged FIND goes into the index.

## Post-Capture
```
[ ] Open screenshot at full resolution -- search for cookie name substring
[ ] Confirm no internal IPs visible that shouldn't be in report
[ ] Rotate test account credentials after report submission
```

## Proxy Is Not An Archive
A Burp/Caido instance is PERISHABLE evidence storage: History gets pruned,
replay collections lose their session links, project selection drifts between
lanes, and the GraphQL API may expose no request bytes at all for older
sessions. Pull the verbatim request/response pair to disk (`raw <id> --out` or
`~/caido.sh raw`) at CAPTURE time, in the same lane that observed it. A FIND
citation whose only source is "the bytes are in the proxy" will fail an
evidence audit - search the whole instance before declaring a pair
unrecoverable, and if it is gone, demote the FIND to unverified instead of
shipping a claim whose responses cannot be produced.

## Deadends

Not applicable in the hunt sense: evidence work has no dead-end
branches - an unsanitizable artifact is escalated to the operator
(NEVER shipped redacted-by-guesswork), not deadended.
