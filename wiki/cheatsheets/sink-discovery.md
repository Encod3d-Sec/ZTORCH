---
title: "Sink Discovery"
type: cheatsheet
tags: [sinks, cheatsheet, web, owasp, xss, sqli, ssrf, rce, deserialization]
sources: []
date_created: 2026-11-09
date_updated: 2026-11-09
---

# Sink Discovery

Sink IDENTIFIERS per OWASP class: what the sink looks like in source
(post-foothold grep) and in traffic (black-box tell), 2025-2026 additions
flagged. This is the discovery layer; escalation detail lives in the matching
technique page. Companion regex battery: `scripts/tells.json`.

Discipline: greps LOCATE, reading CONFIRMS. After any grep hit, read the
enclosing function end-to-end before declaring a sink; a called-with-constant
match is not a sink.

## XSS DOM sinks

```
innerHTML  outerHTML  insertAdjacentHTML  document.write()  document.writeln()
jQuery: $(x).html()  .append()  .prepend()  .after()  .before()  .replaceWith()
eval()  new Function()  setTimeout("str")  setInterval("str")
location  location.href  location.assign()  location.replace()  open()
setAttribute("href"|"src"|"action"|"formaction"|"data"|"xlink:href", x)
srcdoc (iframe)  postMessage listener -> any sink above
```

Grep:
```
(innerHTML|outerHTML|insertAdjacentHTML)\s*\(?\s*=
document\.(write|writeln)\s*\(
\$\([^)]*\)\.(html|append|prepend|after|before|replaceWith)\s*\(
setTimeout\(\s*['"]  setInterval\(\s*['"]
setAttribute\(\s*['"](href|src|action|formaction)
addEventListener\(\s*['"]message['"]
```

Traffic tells: reflected marker landing in an HTML attr/tag context; JSON
consumed by client-side templating; hash/query params surviving into DOM
updates (test `#<img src onerror>` in the fragment); postMessage with no
origin check.

NEW 2025-2026: mXSS round-trip oracle (DOMPurify CVE-2025-15599 3.1.3-3.2.6,
CVE-2026-0540 2.5.3-2.5.8) - the sanitizer VERSION in a response header or
bundle is itself a sink-finder; DOM clobbering gadgets (sinks dereferencing
clobberable `window.x.y` chains); LLM/chat UIs rendering markdown server-side
= fresh stored-XSS class. Detail: [[xss]].

## SQLi: ORM escape hatches

Frameworks parameterize by default; the bugs live in the raw-query hatches:
```
Django:      Model.objects.extra(where=[..], select=..)  .raw(..)
SQLAlchemy:  text() with %s/concat  session.execute(f"..{x}..")
Laravel:     whereRaw  orderByRaw  selectRaw  havingRaw  DB::raw
Rails:       where("name = '#{x}'")  order(params[:sort])
GORM:        db.Where("name = " + x)  db.Raw(fmt.Sprintf(..))
Prisma:      $queryRawUnsafe  $executeRawUnsafe
MyBatis:     ${param} (string subst) vs #{} (safe bind); order-by in ${}
Sequelize:   sequelize.query(..)  where: sequelize.literal(x)
WordPress:   WP_Query array building (CVE-2022-21661 shape persists)
```

Grep:
```
\$\{                       # MyBatis mapper XML - flag every one
(whereRaw|orderByRaw|selectRaw|havingRaw|DB::raw)\s*\(
\.extra\(.*where
queryRawUnsafe|executeRawUnsafe
text\(\s*['"][^'"]*\+
\.Where\(\s*['"][^'"]*['"]\s*\+      # GORM/C# concat
order\s*\(.*params                   # Rails/Hibernate order-by from params
```

Traffic tells: any param landing in ORDER BY / sort / filter / column-NAME
position (cannot be parameterized, the #1 blind spot); JSON `{"filter":..}
{"sort":..}` bodies; GraphQL variables into where clauses; headers
(X-Forwarded-For, UA) into logging tables = second-order candidates.

NEW 2025-2026: LangGraph checkpointer chain (CVE-2025-67644 ->
CVE-2026-28277) - agent persistence layers are SQL sinks; unauth
token-lookup SQLi shape (FortiWeb CVE-2025-25257). Escalation:
[[sql-injection]] + `skills/exploit/hunt/hunt-sqli/references/waf-bypass.md`.

## Command injection / RCE sinks

```
system() exec() popen() shell_exec() passthru() backticks  proc_open()
os.system os.popen subprocess.*(shell=True)  eval exec compile
Runtime.getRuntime().exec  ProcessBuilder
child_process.exec/execSync  spawn(str,{shell:true})
open("|cmd") (Ruby)  IO.popen  %x{}
```

Grep:
```
(system|exec|popen|shell_exec|passthru|proc_open)\s*\(
os\.(system|popen)\s*\(   subprocess\.\w+\([^)]*shell\s*=\s*True
Runtime\.getRuntime\(\)\.exec|ProcessBuilder
child_process\.(exec|execSync)|spawn\([^)]*shell
```

Traffic tells: filename/upload-field/import-URL params; PDF generators;
image processors (ImageMagick policy escapes); archive extraction (zip-slip,
tar compress-program class); webhook fetchers. NEW: CI/CD pipeline config
(`.github/workflows` `${{ }}` injection), MCP tool args executed as shell.

## SSRF URL-fetcher sinks

```
requests.get(url) urllib.request urlopen  http.Get (Go)
curl_exec()  file_get_contents()  fetch()  axios.get
new URL(url) + open() redirect chains  HttpURLConnection
```

Grep:
```
(requests|urllib\.request|urlopen|http\.Get|curl_exec|file_get_contents)\s*\(\s*[^'"]*?(url|host|target|domain|endpoint|callback|webhook|redirect|next|src|img)
open\s*\(\s*(req|params|request)\.
fetch\s*\(\s*(params|query|body)\.
```

Traffic tells: URL params named url/target/host/domain/callback/webhook/
feed/proxy/next/dest/return_to, `img?u=`; PDF-from-URL, import-from-URL,
avatar-from-URL, webhook validators, S3-presign flows. NEW (PATT 2026):
blind-SSRF chain discipline (interactsh canary -> gopher/dict/file scheme
exploitation when the fetcher is curl/libcurl -> cloud metadata). Tools:
SSRFmap, Gopherus, See-SURF, SSRF-Sheriff, r3dir.

## Deserialization magic bytes

Fastest traffic tell: base64 prefix of a serialized blob in any
param/cookie:
```
.NET ViewState   FF 01        -> /w
BinaryFormatter  ..FF FF FF   -> AAEAAAD
Java serialized  AC ED        -> rO0
PHP serialized   4F 3A        -> Tz:  (O:, a:, s:, i:, b: prefixes)
Python pickle    80 04 95     -> gASV
Ruby Marshal     04 08        -> BAgK
```

Grep:
```
BinaryFormatter|ObjectStateFormatter|ViewState
ObjectInputStream|readObject\(\)|XMLDecoder
unserialize\s*\(   maybe_unserialize
pickle\.loads|yaml\.load\((?![^)]*Loader)   Marshal\.load
O:\d+:"
```

Traffic tells: long base64 blobs in cookies/hidden fields; session data
that round-trips; remember-me tokens; cache values (memcached/redis get ->
unserialize). NEW: language-native gadget escalation (ysoserial, phpggc,
universal-Ruby); PyYAML full-load class still live.

## File upload / inclusion sinks

```
move_uploaded_file  $_FILES  File.SaveAs  Files.transferTo
include require include_once require_once  virtual()
readfile  send_file  res.sendFile
```

Grep:
```
move_uploaded_file|transferTo|File\.SaveAs
(include|require)(_once)?\s*\(?\s*\$
(readfile|send_file|res\.sendFile|FileUtils\.readFileToString)\s*\(\s*(req|params|request)
(\.\./|\.\.\\\\){2,}          # traversal strings in traffic
```

Traffic tells: upload accepting double extension / trailing-dot names;
content-type vs magic-byte mismatch accepted; upload later served from same
origin (stored-XSS/RCE check); download params `?file=` `?path=` `?page=`
`?template=` (LFI/RFI + log-poison class). NEW: client-side processing
pipelines (sharp/ImageMagick) parser differentials; zip-slip sinks.

## SSTI sinks

```
Jinja2: render_template_string  Template(x)
Twig    Freemarker  Velocity (Java)  Mako (Python)  ERB (Ruby)
```

Grep:
```
render_template_string\s*\(|Template\(\s*(req|params|f?['"][^'"]*)
(Mako|ERB)\.new|Velocity\.evaluate|Configuration\.setTemplate
```

Traffic tell: `{{7*7}}` / `${7*7}` / `<%= 7*7 %>` reflected as `49`; error
pages naming the engine; email-merge/personalization previews (classic
blind SSTI sink).

## NoSQL / GraphQL passthrough

The param IS the query object:
```
$where  $ne  $nin  $regex  $gt  $expr  $func
db.collection.find({ user: req.body.user })
Model.find(req.query) / Model.find(req.body)
```

Grep:
```
find\s*\(\s*(req\.(query|body)|params|body)\s*[\),]
\$where|(\$ne|\$regex|\$expr)\s*:
aggregate\s*\(\s*(req|params|body)
```

GraphQL: resolvers passing `args` straight into find/where;
introspection gating as the only control; batch queries hiding brute force;
field suggestions as an oracle (CVE-2025-22151 Strawberry class). 2025
SensePost oracles + aggregation-pipeline injection: [[sql-injection]] NoSQL
section.

## Prototype pollution / mass assignment

Sinks: recursive merge of user JSON (legacy `lodash.merge`, deepmerge,
`Object.assign` on nested paths), `__proto__` keys; server side
`model.create(req.body)` without an allowlist.
```
merge|deepMerge|extend\s*\(.*req\.(body|query)
__proto__|constructor\s*\[|prototype\]
\.create\s*\(\s*req\.body|update\s*\(\s*[^)]*req\.body
```

Traffic tell: accepted JSON keys spawning new object fields (`"isAdmin":
true` in a profile update); gadgets: `__proto__.status` into Koa/Express
internals, polluted `child_process` options.

## LLM-stack sinks (NEW 2025-2026 class)

Agent/chat plumbing where user text crosses a trust boundary:
- system-prompt concatenation with user input
- tool-call args built from model output (shell/exec sink re-run)
- RAG content rendered into prompts AND into chat UI (stored XSS via
  markdown render)
- agent memory/checkpointer backends = SQLi sinks (LangGraph
  CVE-2025-67644)
- MCP server tools that exec, read files, or fetch URLs with model-chosen
  args (SSRF/RCE/LFI re-run); plugin manifests fetched from user URLs

```
system_prompt\s*\+|systemPrompt.*concat
(messages|prompt)\s*\+\s*(req|user|input)
execute_tool|tool_call.*exec|subprocess
```

Tell: a URL/file/command referenced in natural language later appearing in
a fetch/exec trace.

## How to use this

1. Post-foothold source review: run the greps per class, then READ each
   hit's enclosing function end-to-end.
2. Black-box: match traffic tells first (magic bytes, base64 prefixes,
   `{{7*7}}`, URL-named params) - they shortlist the class before any
   source exists.
3. Escalation lives in the technique pages ([[xss]], [[sql-injection]],
   [[ssrf]], [[os-command-injection]], [[insecure-deserialization]] and the hunt skills'
   `references/` arsenals) - this page only FINDS the sink.
