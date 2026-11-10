---
title: trusted-types-bypass
---

# trusted-types-bypass

Staged content promotes here.

## Trusted Types bypass classes (2025-2026 state)

`require-trusted-types-for 'script'` forces DOM sinks to take a TrustedHTML/TrustedScript object instead of a string. Three recurring bypass families:

1. Permissive default policy: pages install `window.trustedTypes.createPolicy('default', ...)` for compatibility; when `createHTML` identity-passes attacker strings, every string sink is re-enabled. Probe: read `trustedTypes.defaultPolicy` and its `createHTML` behaviour in console.
2. Sanitizer disagreement (mXSS): app code sanitizes input before `createHTML`, but the sanitizer allowlist and the DOM parser disagree about the result. DOMPurify before 3.2.4 (CVE-2025-26791, template-literal regex mishandling) executed THROUGH Trusted-Types-compliant code because the policy accepted the sanitized-but-remutated markup. Treat "TT enabled" as no protection while any sanitizer sits inside the policy path.
3. DOM-clobbering gadgets producing typed objects: attacker-controlled id/name attributes redirect `getElementById`-style lookups to attacker nodes; gadget code that calls `createHTML`/`createScript` on node-derived values launders attacker HTML through the sanctioned API.

Also probe: `createScriptURL` policies that block `javascript:` but allow `data:` or relative URLs, and engines where `'unsafe-eval'` still bypasses the types check for eval-family sinks.

### Sources
- https://tyrusrc.github.io/learnfromscratch/learn/topics/web/trusted-types-bypass/
- https://nvd.nist.gov/vuln/detail/CVE-2025-26791

<!-- promoted-slug: trusted-types-bypass-classes -->
