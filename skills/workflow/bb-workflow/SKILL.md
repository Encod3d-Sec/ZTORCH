---
name: bb-workflow
description: "Use when the operator wants the full pipeline run hands-off on a host: surface mapping -> JS corpus -> signal-based hunt-* class selection -> confirm -> triage -> report, with a hard per-stage budget so the agent never blind-runs every hunt-* skill against every host. This skill owns the concrete stage sequence INSIDE one host's run, including the selector that turns recon signals into a short, ranked dispatch list instead of running all 39 hunt-* skills. offensive.py owns the board and the across-host queue; this skill writes only a per-host lane log (bb-run.md). Assumes hunt-core lane discipline."
metadata:
  hermes:
    tags: [orchestration, pipeline, budget, selector]
    related_skills: [offensive, brain, delegate, hunt-core, js-discover, js-parser, triage, learn]
---

# BB Workflow - the per-host pipeline offensive.py dispatches into

offensive.py (orchestrate/offensive) owns the BOARD and the across-host
queue: it seeds from scope.md/state.md, folds in verified new hosts, and
drives `next`. When its lanes call for js-discover / js-parser / a test
lane on a host, this skill IS that sequence, made concrete - the stage
order, the budget caps, and most importantly the SELECTOR that decides
which hunt-* classes are even worth running, so a host doesn't eat a
full pass of all 39 hunt-* skills when the recon only supports three
of them.

This skill writes zero new exploitation logic. Every hunt-*, surface/*,
exec/*, and report/* skill keeps its own entry gate, checklist, and
REVIEW gate exactly as written - bb-workflow never shortcuts another
skill's own discipline. What it adds is the thing that was missing: a
reason, grounded in this host's actual recon, for dispatching a class
at all.

## Paths (binding - same engagement tree as every other skill)

    # seat side (WSL via /mnt/c; ported 2026-10-17) - engagement tree is
    # DOUBLE-NESTED in VMshare:
    ENG_DIR=/mnt/c/Users/Lenovo/Desktop/VMshare/<eng>/<eng>
    RUN=$ENG_DIR/js/<host>            # js-discover's own convention, reused here
    # Kali VM side (same tree through the VMware share):
    ENG_DIR=/mnt/VMshare/<eng>/<eng>
    RUN=$ENG_DIR/js/<host>

BOARD OWNERSHIP: offensive.py's state.md board is THE board - the
operator's single check-in file with the exact next action. This skill
writes ONLY `$RUN/bb-run.md`, a per-host lane log. Never create a
second board.md.

## Why signal-based dispatch (the "sharp, no random burn" part)

Running every hunt-* skill against every host is exactly the token/time
burn the operator asked to avoid. Instead, Stage 3 below reads what
Stage 1 (surface mapping) and Stage 2 (js-discover + js-parser's
endpoints.jsonl / site-summary.md) actually found, and emits a RANKED,
CAPPED list of classes to run - skipping any class with zero supporting
signal rather than running it "just in case." A hunt-* lane's own
N/A-escape ("N/A: no signal") is cheap, but the point of Stage 3 is to
make that the rare case, not the default outcome of blind dispatch.

## Signal -> class map (the selector's lookup table)

Each row needs at least one CORROBORATED signal (an endpoint hit in
endpoints.jsonl AND a matching symbol/context in the per-file analysis
notes, not a bare keyword match on a single low-confidence string) before
it queues a class. A signal sourced only from a file js-parser already
flagged low-confidence (test/fixture paths, webpack virtual sources)
counts as half a signal - needs a second, independent corroboration to
queue.

| Signal in site-summary.md / endpoints.jsonl | Unlocks |
|---|---|
| API surface with path/query params | hunt-api, hunt-idor |
| id/uuid/sequential value in a path or param | hunt-idor |
| Login form, session cookie, JWT, or OAuth/OIDC token | hunt-auth |
| File upload field or endpoint | hunt-upload |
| Server-side fetch of a user-controlled URL (webhook, preview, import-by-url) | hunt-ssrf |
| Reflected input in an HTML response, or a DOM sink (`innerHTML`, `eval`, etc.) in js-parser's per-file notes | hunt-xss-reflected / hunt-xss-dom / hunt-xss-stored / hunt-xss-blind (pick by sink type, not all four) |
| SQL-shaped param (search/filter/sort/id) with no visible ORM guard | hunt-sqli (base lead only; the `-boolean`/`-time`/`-union`/`-oob`/`-error` variants fire ONE AT A TIME, only once hunt-sqli's own base pass names which confirmation technique the response supports - never all five blind) |
| SAML/OIDC/SSO endpoint | hunt-federation |
| GraphQL endpoint | hunt-api (+ hunt-idor if object ids are arguments) |
| Serialized blob (Java/.NET/PHP serialized, pickled Python) in a param or cookie | hunt-deserialization |
| CI/CD webhook, Actions/Jenkins/GitLab-CI surface | hunt-cicd |
| Cloud metadata endpoint reachable, IAM role strings in JS | hunt-cloud |
| AD-domain-joined host / Kerberos ticket surface | hunt-ad (sub-skills `-acl`/`-adcs`/`-kerberos` fire only once hunt-ad's own enum names a concrete lead, not speculatively) |
| OT/ICS protocol banner (Modbus/S7/BACnet) | hunt-ics |
| LLM/chat endpoint, prompt-taking API | hunt-llm |
| MCP server endpoint | hunt-mcp |
| macOS or Windows endpoint-agent surface | hunt-macos / hunt-windows |
| VPN / SSL-VPN portal | hunt-vpn |
| Crash-prone binary target, no meaningful web surface | hunt-pwn |
| Cache-control oddities, CDN in front | hunt-cache |
| Chunked/content-length ambiguity across a multi-server chain | hunt-smuggling |
| Secrets findings rows with any candidate (js-parser already produced them) | hunt-secrets confirm/triage pass |
| Pricing/coupon/workflow-state logic visible client-side | hunt-bizlogic |

No corroborated signal for a class = that class is not queued for this
host. This table is the whole mechanism: it converts "run everything"
into "run what the recon actually supports."

## Stages (the per-host pipeline)

0. **Entry / budget declare** - confirm entry gate, write the host's
   bb-run.md row with its stage-by-stage budget (default caps below,
   operator can override per engagement in a config the operator
   maintains, not invented here).
1. **Surface mapping** - cheapest tool first: `surface/fuzz` and
   `surface/browser` before `surface/burp`/`surface/caido` (heavier,
   stateful tools) before `surface/interceptor` (only per its own
   dynamic-site trigger criteria, not by default).
2. **JS corpus** - `js-discover` then `js-parser`, already-built skills,
   unchanged. STAGE 2 RE-RUN TRIGGER: a capture class the host never had
   parsed (a new subdomain's chunk set, a first-ever authenticated-surface
   bundle pull, a post-deploy rotation) is a standalone Stage 2 trigger even
   if the host "already ran" - fresh corpus material re-opens the selector
   with new ops/call-sites/endpoints that the earlier pass could not see.
3. **Class selection** - run the signal table above against Stage 1 + 2
   output, write the ranked, capped list to `$RUN/dispatch-queue.md`
   (class, signal(s) it matched, confidence). This file is the audit
   trail for "why did we run this" - a class with an empty signal list in
   this file is a Stage 3 bug, not something that should have dispatched.
4. **Dispatch** - hand `dispatch-queue.md`'s classes to the lanes
   THROUGH the existing orchestration: offensive.py `next` / `brain`
   lane dispatch (bb-workflow never spawns its own parallel dispatch
   authority - one driver, one board). Each hunt-* lane keeps its own
   entry gate, checklist, confirmation gate, and REVIEW - bb-workflow
   only decides WHICH lanes run, never how they run.
5. **Confirm / exploit** - only for whatever a Stage 4 lane marked a LEAD
   (never speculative): `metasploit`/`redteamlead`/`delegate` as the exec
   vehicle, same confirmation-gate discipline those skills already define.
6. **Triage** - collapse every Stage 4/5 output into one ranked finding
   set (existing `triage` skill, unchanged).
7. **Report** - `report/disclosure` or `report/walkthrough` for confirmed
   FINDs only; nothing in Stage 3-6 writes a report-ready claim on its own.
8. **Closeout** - `learn` + `evidence`, final bb-run.md stamp
   for this host, hands control back to offensive.py `next` for the next
   host (or ends, if run standalone).

## Budget discipline (the "won't burn tokens" part)

- Each stage gets a declared token/time budget in bb-run.md BEFORE it
  starts (sane defaults: Stage 1-2 generous since they're one-shot per
  host; Stage 4 capped hardest since it's where blind dispatch would
  otherwise burn the most).
- Per-engagement overrides live in `$ENG_DIR/bb-budget.md` (key=value
  table the OPERATOR maintains; e.g. `stage4_class_cap = 8`). Absent
  file = skill defaults. offensive.py never stores or reads budgets.
- **Stage 4 class cap**: default max 6 hunt-* classes dispatched per host,
  ranked by signal strength + severity ceiling from the signal table, not
  alphabetically. Operator-settable higher for a host worth the spend.
- A stage that blows its budget does NOT silently keep going - it writes
  a partial result + the reason to bb-run.md and stops at the stage
  boundary. The next host in the queue still gets its own full budget;
  one expensive host never starves the rest.
- Concurrency is `brain`'s job (already exists); bb-workflow just feeds
  it the capped class list, it doesn't manage subagents itself.
- SERIALIZE LANES ON SHARED STATEFUL RESOURCES. When two dispatched
  lanes need the same logged-in browser/session/tool stack, run them
  back-to-back, never concurrently: the second lane's navigation reuses
  or rotates the first lane's managed tabs and its session churn trips
  the target's rate limiters for both. Put the serialization rule in
  each lane's brief ("you are the SOLE lane on X") and re-derive shared
  session state (fresh login) instead of trusting a sibling's session.
- BIND LANE OUTPUT PATHS ABSOLUTELY in the lane contract. Lanes that
  write to cwd-relative paths ("Vulns/...", "raw/...") resolve them
  against whatever directory the lane happens to run in, silently
  creating a parallel tree that diverges from the canonical one; the
  main session then merges by hand. State the exact absolute output
  directory per artifact class in the brief, and sweep for stray trees
  before closeout.

## Retry ladder (clean miss != deadend, but it's not a free loop either)

Two different outcomes from a dispatched class look similar but aren't:

- **N/A (no signal)** - Stage 3 never had grounds to queue this class.
  Correct, cheap, not retried.
- **Clean miss** - the class DID have signal, ran its full methodology,
  and found no lead. This is the case worth a bounded retry with a
  genuinely different approach, not a straight deadend.

A clean miss is eligible for up to **1 retry by default**
(operator-settable per engagement, not per class mid-run), drawn from the
SAME Stage 4 budget that class already spent against - a retry is not a
fresh budget grant, so this can't quietly double a host's total spend.

A retry is only valid if it names a **pivot**: a different parameter, a
different injection point, a different encoding/content-type, a different
auth context (unauthenticated vs. session-holder), or a different sink
than the first attempt targeted. Write the pivot to `dispatch-queue.md` as
a new row: `retry_of: <original row id>, pivot: <what changed>`. A retry
that re-runs the identical probe with no named pivot is not permitted to
re-tick that class's checklist box - it's the same attempt, not a second
one.

Before retrying, check the class's own `False Positives` and `Deadends`
sections for this host - if the pivot you're about to try was already
logged as ruled out there with nothing new since, don't re-spend budget
on it; that's a deadend, not a retry candidate.

Once the retry budget for a class is exhausted with no lead, it's a
deadend row in bb-run.md (same convention as everywhere else in this
library: name the boundary - which pivots were tried, what would reopen
it - not just "failed"). This ladder is per-class, not a whole-host
restart; bb-run.md tracks attempt count per class so a host with three
clean-miss-then-deadend classes still reads as three distinct, bounded
attempts, not an open-ended loop.

## Loop / hands-off mechanics

- `$RUN/bb-run.md` is the per-host lane log: one running table,
  `host | stage | classes dispatched | leads | confirmed FINDs | budget
  used | status`. The operator's check-in file remains offensive.py's
  board (state.md) - bb-run.md feeds it, never competes with it.
- Updated at the END of every stage, not just the end of the run -
  operator can check in mid-pipeline and see live progress without
  interrupting anything in flight.
- Under offensive.py: the driver dispatches a host, bb-workflow drives
  Stage 0-8 to a terminal state (closed out, budget-exhausted, or
  deadend), then hands control back to `next` for the following host.
  Standalone (operator names a single host directly): bb-workflow runs
  Stage 0-8 once for that host and stops. Both entry paths are valid.
- Nothing here pauses for operator confirmation beyond what each
  individual lane already requires (false-root guard in `delegate`, the
  SAFETY hard-stop in `hunt-ics`, a module's own confirmation
  gate). This skill doesn't lower any existing bar for speed -
  "hands-off" means the operator isn't needed to SEQUENCE the work, not
  that any safety gate gets skipped.

## Entry gate

1. Active engagement + `scope.md` exist; scope-guard is the deny, same as
   every skill in this family.
2. hunt-core lane discipline active.
3. Either offensive.py/brain has already dispatched this host, OR the
   operator named a single host directly for a standalone bb-workflow
   run - both valid.
4. Default budget values written to bb-run.md if the operator hasn't
   supplied engagement-specific ones.

## Checklist (mandatory)

Copy `checklist.md` (this skill's dir) to `$RUN/bb-workflow-checklist.md`
at Stage 0. One box per stage (0 through 8) plus a REVIEW box. Same
discipline as every lane in this library: unchecked at stop = not done,
resume at the first unchecked box, never restart the whole host.

## Wiki

Hub: [[web-moc]] | See also: [[static-code-analysis]] for the Stage 2
corpus this skill consumes, and [[methodology-moc]] for the hunt-core
discipline every dispatched class still follows.

## Handoff

Confirmed FINDs -> `report/disclosure` / `report/walkthrough`.
Closeout -> `learn` + `evidence`.
Next host -> back to offensive.py `next` (when running under the driver).

## Validation

- bb-run.md accounts for every host-stage pair that ran.
- Every class in dispatch-queue.md traces to a named, corroborated
  signal row - a dispatched class with no signal listed is a selector
  bug, not a legitimate run, and should be logged as such.

## False Positives

- A class queued off a single low-confidence signal (keyword only inside
  a test/fixture path, per js-parser's own flagging) - Stage 3 requires a
  second, independent corroboration before queueing; one weak signal
  alone downgrades the row, it doesn't dispatch it.
- A stage marked "done" because every dispatched lane returned N/A - N/A
  is a valid terminal state, not evidence the stage found nothing worth
  reporting; bb-run.md distinguishes "ran, found nothing" from "had no
  signal to run on" as two different outcomes, not one blank row.

## Deadends

A host where Stage 1 returns nothing usable (dead host, an unbreakable
bot wall) -> deadend row in bb-run.md with the specific blocker named, so
a later tick doesn't retry an unchanged wall; the driver moves to the
next host.

## Stop conditions

Stage 8 closeout stamped for this host, bb-run.md's row for it complete,
no unchecked boxes above REVIEW in `$RUN/bb-workflow-checklist.md`,
control handed back to offensive.py `next` (or the standalone run ends).
hunt-core stop conditions fire unchanged inside every dispatched class.
