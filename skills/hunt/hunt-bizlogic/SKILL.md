---
name: hunt-bizlogic
description: Business-logic hunting - workflow/state bypass, price tampering, negative values, coupon abuse, mass assignment, logic races. Top-paying class, no scanner coverage. Wiki-first, FIND output. Use when checkout/pricing/coupon/workflow state or a race condition is in play.
---

# Hunt: Business Logic

> Current emphasis (update on wiki harvest): negative-amount tampering on two-
> legged transfers and single-packet race bursts over coupon re-redemption
> classics - models over-index on over-represented old methods; the newest
> harvested technique leads the checklist until superseded.

**Assumes `hunt-core`** for the scope gate, two-account rule, confirmation gate, enumeration limits, stop conditions, wiki protocol, FIND output, and Deadends. Do not re-derive any of that here.

## Wiki

Hub: [[web-moc]] · Primary page: [[business-logic]] · No payload arsenal (manual reasoning, zero scanner coverage)
Anchors: [[race-conditions]], [[access-control]]
**REFS:** [[business-logic]], [[race-conditions]]

qmd_query "business logic flaw workflow state bypass price quantity tampering coupon refund race condition" via wiki-search MCP - ONLY when you have a concrete hint the map above
doesn't cover (a specific sink/version/CVE, an observed escape); not a blanket first step.

## No scanner finds these

This is the top-paying bug class and the one with **zero scanner coverage** - it is all manual reasoning. Find an assumption the developer made and break it: that steps happen in order, that values are positive, that the client cannot change a field, that an action cannot be repeated. Map the intended workflow first (read the feature, the happy path, every state transition); the flaw is always the gap between that and what the server actually enforces.

## Attack surface - rank before testing

**APPROACH:** Map the intended workflow, then break a developer assumption: client-supplied price/total at checkout, refund/coupon re-redemption and negatives, step skip/replay/reorder, quantity overflow, and out-of-state transitions; bounded concurrent burst for check-then-act races.
**AVOID:** An odd value accepted, a 200 on a tampered request, the field echoed back, or a wrong total that only DISPLAYS is NOT confirmation - the unintended end-state must be realized and verified downstream (balance moved, order captured at the tampered price).

Money and state-machine endpoints pay; cosmetic ones do not. Work them in this order:

1. **Checkout / payment** - client-supplied price, total, tax, currency, shipping, anywhere the server should recompute a value and instead trusts it.
2. **Refund / coupon / gift card / store credit** - re-redemption, stacking, negative amounts, a refund exceeding the purchase.
3. **Multi-step workflows** - checkout, transfer, signup, KYC, password reset, subscription: skip, replay, or reorder a step.
4. **Quantity / price fields** - negative, zero, overflow, decimal and rounding.
5. **State transitions** - an action valid only in one state performed from another (ship before pay, use before verify).

## Methodology

**Setup:** two accounts per `hunt-core` where the flaw is cross-actor; one account suffices for pure value or state tampering. Drive the load-bearing requests through **Burp Repeater** for operator visibility.

1. **Map the flow.** Enumerate every step and state of the target feature. Note each parameter and which server check governs it. The flaw is a check the client can reach around.

2. **Step / state bypass.** Skip a step (POST straight to the final endpoint), replay an earlier step, run steps out of order, reuse a one-time token, reach step N without completing N-1.

3. **Value tampering.**
```
quantity = -1            # negative -> credit / refund
price / amount = 0.01    # client-supplied price
currency swap            # pay in a weaker currency, credited in a stronger one
integer overflow / very large qty
decimal / rounding (0.001 * 1000)
```
On a two-legged transfer, a negative amount flips BOTH legs (sender gains, recipient debited) and
passes the insufficient-balance check by construction; re-read both balances afterward as the
impact proof. [[business-logic]]

4. **Repetition / limits / logic race.** Apply a coupon twice, redeem a gift card twice, exceed a per-account limit. When the limit is a check-then-act with no lock, fire a **small concurrent burst** at the single endpoint (logic [[race-conditions]]) so several requests pass the check before any commits. Keep the burst bounded: a handful of parallel requests is the proof, honor `no_dos`, never a sustained flood. Per `hunt-core` this is a bounded active proof, not object enumeration, so the 5-to-20 identifier ceiling does not apply, but the RoE rate cap does. Send the request to **Turbo Intruder** via `send_to_intruder` / the Burp MCP and fire it with a single-packet or synchronized-gate script so the operator watches the race live; a hand-rolled parallel `curl` loop hides it. Read the negative before re-racing: a final state of exactly `start - successes*unit`, or bursts that land at the cap with only TRAILING completions accepted, prove a serialized check-then-write; record the class closed and switch vectors ([[race-conditions]]).

5. **Mass assignment / parameter injection.** Add fields the UI never sends (`isAdmin`, `role`, `balance`, `verified`, `discount`, `userId`) to JSON or form bodies; observe a privilege or state change.

6. **Trust-boundary confusion.** Values the server should compute but trusts from the client (total, tax, role, KYC status, account tier); flags re-sent and re-trusted on a later request.

7. **Identity / authorization logic.** An action allowed for the wrong account state (an unverified user performing a verified-only action) or against another user's object (-> [[access-control]] / `hunt-idor`).

## When the value is rejected

A rejected tamper is not a closed door. Retry the same value in a representation the server parses but the validator missed: an alternate field the server also reads, parameter pollution (`price=10&price=0.01`), a nested wrapper (`{"item":{"price":0.01}}`), a type change (string vs number, array vs scalar), sign and precision tricks (`-0`, `1e-2`, trailing decimals), or re-sending a server-computed field an earlier step trusted. Reorder the steps so validation runs before the value is set.

## Chaining

Logic flaws compound. A price or quantity tamper that touches *another user's* cart is logic + IDOR (hand off to `hunt-idor`); a coupon or limit bypass that only works under concurrency is logic + race ([[race-conditions]]). Chain them for higher impact and say so in the title - "race-condition coupon re-redemption" reads bigger than "coupon bug".

## Confirmation gate

**NOT confirmation:** the app accepted an odd value; a `200` on a tampered request; the tampered field echoed back in the response; an order or total that merely *displays* wrong on your screen; a coupon that "applied" without the charge changing.

**IS confirmation:** the unintended end-state is realized and verified downstream - a negative or inflated balance that persists, a purchase completed at the free or discounted price (order confirmed, payment captured at the tampered amount), a workflow step skipped **and** its downstream effect confirmed (account provisioned, funds moved, access granted). For a race, the limit is actually exceeded (two redemptions both settled). Re-verify in a clean session, and confirm from the state only the successful abuse produces, not from the request the server merely accepted.

## Validation

- Proof = the economic/state effect demonstrated TWICE with a paired control: the
  attack order applies the discount/coupon/overflow AND a control order without the flaw
  behaves normally. One lucky order is an anecdote.
- Counterevidence: reconciliation/refund reversal may catch the effect later; note the
  window in the FIND's severity_change_conditions.

## False Positives

- Sandbox/test-mode amounts and sandboxes with fake gateways.
- Client-side-only 'reuse' the server already deduplicates.
- Race 'won' against a dev replica with different locking.
- Quantity/currency overflow the backend rounds or rejects at settlement.
- Feature-not-bug: bulk discount stacking that is the documented promotion.

## Cross-routing

- Load hunt-api when the abuse needs endpoint mechanics (verbs, mass assignment).
- Load hunt-injection when the root cause is a parser (unit mismatch, type juggling).
- Not this skill: plain cross-account object access (hunt-idor).

## Severity

Rated on realized impact per `hunt-core`.

| Outcome | Typical |
|---|---|
| Direct financial theft, auth bypass, unlimited privilege | critical |
| Discount / refund abuse, quota bypass with money impact | high |
| Limited abuse needing preconditions | medium |

## Distill

Confirmed and reusable (a generic logic-abuse pattern, no client specifics): `python3 scripts/wiki-stage.py --kind technique --slug <slug> --target-page techniques/web/business-logic.md`.

## Deadends

```
Append: - [ ] logic <feature> on <host> -- server recomputes price/total, enforces the state
              machine, ignores extra fields, idempotency keys present; race lost after bounded burst
```

Record what the server enforced, so the next pass does not retest a solid boundary.
