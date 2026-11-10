---
title: f5-asm-cookie-probing
---

# f5-asm-cookie-probing

Staged content promotes here.

## F5 BIG-IP ASM TS cookie probing (policy fingerprinting without a scanner)

`TS<hash>=<value>` cookies are set by ASM on first blocked or learned request and validated on the way back; they carry enforcement state, not session state.

Use:
1. Version class: pre-11.4 deployments sign with MD5 (name `TS` + MD5-derived suffix); 11.4+ use a per-deployment random security key with a configurable algorithm (K6850). An MD5-era value surviving on a modern build is itself a legacy cookie-security misconfig note.
2. Policy-strictness oracle: replay the SAME suspicious request three ways: TS cookie intact, TS stripped, TS value truncated or garbled. Differences in status / block page / violation support-id reveal whether ASM trusts the client-held cookie and how the policy scores the request when its state is lost.
3. Parameter-discovery side channel: ASM block pages enumerate the violated parameter or URL class; each violation type maps to learned policy, so block pages let you enumerate enforced parameters and signatures without brute force.
4. Fresh-state re-evaluation: a stripped TS plus a fresh session pushes ASM into transparent re-evaluation of the request, the classic reset before testing a WAF-evasive payload variant.

Cookie tampering protection (K57420543) closes the tamper leg when enabled; without it, value edits are not detected. ASM enforcement is officially bypassable with a support bypass mechanism (K22021244 class): any exposed bypass/i-rule path reopens the lane entirely.

### Sources
- https://my.f5.com/manage/s/article/K6850
- https://my.f5.com/manage/s/article/K57420543
- https://my.f5.com/manage/s/article/K22021244
- https://f5-agility-labs-waf.readthedocs.io/en/latest/class4/module6/lab1/lab1.html

<!-- promoted-slug: f5-asm-ts-cookie-probing -->
