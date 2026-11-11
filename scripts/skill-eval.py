#!/usr/bin/env python3
"""skill-eval.py - eval harness for the hunt-skill layer (static, no targets).

Three eval families:

  ROUTING  scenario prompt -> the LIVE hunt-trigger.py matcher (imported, not
           copied) -> assert the expected skill lands in the expected tier.
           A FAIL here means the auto-trigger layer is wrong, not this script.
  WIRING   pointer-graph integrity for every skill shipping a
           references/bypass-arsenal.md: SKILL.md pointer present, arsenal is
           ASCII, checklist carries a NEW-20xx/arsenal marker, every
           [[payload-page]] link resolves to a wiki page. This is the
           regression net for the arsenal wiring pattern (proposal: prompts
           are reviewed artifacts).
  RECALL   key-technique anchors per arsenal/checklist (any-of alternatives):
           an edit that deletes the load-bearing technique fails loudly.

Run: python3 scripts/skill-eval.py   (exit 1 on any FAIL; battery wrapper
tests/test_skill_evals.py). Lab-functional evals deliberately excluded
(operator decision 2026-11-09).
"""
import glob
import importlib.util
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
HUNT = os.path.join(ROOT, "skills", "exploit", "hunt")


def _load_hook():
    path = os.path.join(ROOT, "skills", "hooks", "hunt-trigger.py")
    spec = importlib.util.spec_from_file_location("hunt_trigger", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


HT = _load_hook()
TRIG = json.load(open(os.path.join(HUNT, "triggers.json"), encoding="utf-8"))


def route(prompt):
    """Replicate hunt-trigger.py main() tiering minus telemetry/meta hooks."""
    scan = HT._strip_code(prompt)
    hard, down = HT._match_gated(TRIG.get("triggers", {}), scan)
    soft = HT._match(TRIG.get("surface_triggers", {}), scan) + down
    seen, s = set(hard), []
    for x in soft:
        if x not in seen:
            seen.add(x)
            s.append(x)
    return hard, s


ROUTING = [
    # (name, prompt, {"hard": [must be hard], "soft": [must be hard-or-soft],
    #                  "no_hard": [must not be hard], "hard_empty": bool})
    ("ssrf-importer", "Test the profile-picture importer for SSRF before moving on.",
     {"hard": ["hunt-ssrf"]}),
    ("idor-invoices", "Hunt for IDOR on the invoice endpoints.",
     {"hard": ["hunt-idor"]}),
    ("smuggle-cdn", "Probe the CDN edge for request smuggling.",
     {"hard": ["hunt-smuggling"]}),
    ("cache-deception", "Assess the CDN for cache deception on the account page.",
     {"hard": ["hunt-cache"]}),
    ("cors-api", "Test for CORS misconfiguration on the API.",
     {"hard": ["hunt-auth"]}),
    ("mcp-poison", "Test the MCP server integration for tool poisoning.",
     {"hard": ["hunt-mcp"]}),
    ("graphql-hard", "Test the GraphQL endpoint for injection issues.",
     {"hard": ["hunt-injection"]}),
    ("adcs-esc", "Test ESC15 against the AD CS enrollment endpoint.",
     {"hard": ["hunt-ad"]}),
    ("secrets-js", "Hunt for hardcoded secrets in the JS bundle.",
     {"hard": ["hunt-secrets"]}),
    ("xss-report-quiet", "Write up the found XSS for the client report.",
     {"no_hard": ["hunt-xss"]}),
    ("login-form-soft", "The portal has a login form and a forgot password page.",
     {"soft": ["hunt-auth"]}),
    ("framework-quiet", "Update the AGENTS.md section about output rules.",
     {"hard_empty": True}),
]

# (label, path relative to vault, [alternatives]) - pass if ANY alternative present
RECALL = [
    ("federation sig2n", "skills/exploit/hunt/hunt-federation/references/bypass-arsenal.md", ["sig2n"]),
    ("federation DCR", "skills/exploit/hunt/hunt-federation/references/bypass-arsenal.md", ["dynamic client registration", "DCR"]),
    ("auth easy-auth", "skills/exploit/hunt/hunt-auth/references/bypass-arsenal.md", ["Easy Auth", ".auth/me"]),
    ("api get-copy-put", "skills/exploit/hunt/hunt-api/references/bypass-arsenal.md", ["GET-copy", "copy-PUT", "GET copy", "copy PUT"]),
    ("idor value-ladder", "skills/exploit/hunt/hunt-idor/references/bypass-arsenal.md", ["value ladder", "value-ladder", "ladder"]),
    ("injection two-stage", "skills/exploit/hunt/hunt-injection/references/bypass-arsenal.md", ["StyleSmuggler", "two-stage"]),
    ("injection federation-entities", "skills/exploit/hunt/hunt-injection/references/bypass-arsenal.md", ["_entities", "APQ"]),
    ("upload cspt", "skills/exploit/hunt/hunt-upload/references/bypass-arsenal.md", ["CSPT", "Content-Type"]),
    ("cache delimiters", "skills/exploit/hunt/hunt-cache/references/bypass-arsenal.md", ["delimiter", "CF-Cache-Status"]),
    ("smuggling continuation", "skills/exploit/hunt/hunt-smuggling/references/bypass-arsenal.md", ["CONTINUATION", "H2.CL"]),
    ("cicd tag-rewrite", "skills/exploit/hunt/hunt-cicd/references/bypass-arsenal.md", ["CVE-2025-30066", "pull_request_target"]),
    ("mcp rug-pull", "skills/exploit/hunt/hunt-mcp/references/bypass-arsenal.md", ["rug pull", "cross-server"]),
    ("llm 2026-top10", "skills/exploit/hunt/hunt-llm/references/bypass-arsenal.md", ["LLM08", "crescendo"]),
    ("vpn kev-wave", "skills/exploit/hunt/hunt-vpn/checklist.md", ["CVE-2026-19868"]),
    ("cloud ipv6-metadata", "skills/exploit/hunt/hunt-cloud/checklist.md", ["fd00:ec2"]),
    ("m365 illegal-mail", "skills/exploit/hunt/hunt-m365/checklist.md", ["Illegal Mail"]),
    ("adcs esc15", "skills/exploit/hunt/hunt-ad-adcs/references/bypass-arsenal.md", ["ESC15", "schema"]),
    ("xss mxss", "skills/exploit/hunt/hunt-xss/references/bypass-arsenal.md", ["mxss", "re-serialization"]),
    ("xss csp-chain", "skills/exploit/hunt/hunt-xss/references/bypass-arsenal.md", ["dangling markup", "strict-dynamic"]),
    ("sqli order-by", "skills/exploit/hunt/hunt-sqli/references/bypass-arsenal.md", ["CASE WHEN", "ORDER BY"]),
    ("sqli second-order", "skills/exploit/hunt/hunt-sqli/references/bypass-arsenal.md", ["second-order", "second order"]),
    ("bizlogic race", "skills/exploit/hunt/hunt-bizlogic/references/bypass-arsenal.md", ["single-packet", "TOCTOU", "idempotency"]),
    ("secrets ladder", "skills/exploit/hunt/hunt-secrets/references/bypass-arsenal.md", ["GetCallerIdentity", "metadata-scope"]),
    ("ad cisa-17", "skills/exploit/hunt/hunt-ad/references/bypass-arsenal.md", ["CVE-2025-29810", "CISA 17"]),
    ("ad-acl shadow-admin", "skills/exploit/hunt/hunt-ad-acl/references/bypass-arsenal.md", ["shadow admin", "ESC4"]),
    ("kerberos golden-cert", "skills/exploit/hunt/hunt-ad-kerberos/references/bypass-arsenal.md", ["PKINIT", "golden CERT"]),
    ("pwn glibc-heap", "skills/exploit/hunt/hunt-pwn/references/bypass-arsenal.md", ["safe-linking", "tcache"]),
    ("windows patch-wave", "skills/exploit/hunt/hunt-windows/references/bypass-arsenal.md", ["CVE-2026-50345", "CVE-2025-64669"]),
    ("macos tcc", "skills/exploit/hunt/hunt-macos/references/bypass-arsenal.md", ["TCC", "CVE-2026-28912"]),
    ("ics read-first", "skills/exploit/hunt/hunt-ics/references/bypass-arsenal.md", ["fc 43", "unit-ID"]),
    ("crypto authlib", "wiki/payloads/crypto.md", ["CVE-2026-27962", "fail-open"]),
    ("webauthn passkey-idor", "wiki/payloads/webauthn-passkey.md", ["CVE-2025-71400", "credential-ID"]),
    ("cicd ghostaction", "wiki/payloads/cicd.md", ["GhostAction", "pull_request_target"]),
    ("ldap filter-template", "wiki/payloads/ldap.md", ["CVE-2026-90979", "4515"]),
]


def eval_routing():
    out = []
    for name, prompt, exp in ROUTING:
        hard, soft = route(prompt)
        ok, why = True, []
        for s in exp.get("hard", []):
            if s not in hard:
                ok = False
                why.append("expected %s in hard; hard=%s soft=%s" % (s, hard, soft))
        for s in exp.get("soft", []):
            if s not in hard and s not in soft:
                ok = False
                why.append("expected %s in soft; hard=%s soft=%s" % (s, hard, soft))
        for s in exp.get("no_hard", []):
            if s in hard:
                ok = False
                why.append("%s fired hard unexpectedly; hard=%s" % (s, hard))
        if exp.get("hard_empty") and hard:
            ok = False
            why.append("expected no hard fires; hard=%s" % hard)
        out.append((ok, "routing:" + name, "; ".join(why)))
    return out


def _wiki_exists(link):
    return (bool(glob.glob(os.path.join(ROOT, "wiki", "*", link + ".md")))
            or bool(glob.glob(os.path.join(ROOT, "wiki", "*", "*", link + ".md"))))


def eval_wiring():
    out = []
    for d in sorted(os.listdir(HUNT)):
        a = os.path.join(HUNT, d, "references", "bypass-arsenal.md")
        if not os.path.isfile(a):
            continue
        body = open(a, encoding="utf-8", errors="replace").read()
        skill_md = os.path.join(HUNT, d, "SKILL.md")
        s = open(skill_md, encoding="utf-8", errors="replace").read() if os.path.isfile(skill_md) else ""
        out.append(("references/bypass-arsenal.md" in s,
                    "wiring:%s:pointer" % d, "SKILL.md lacks the arsenal pointer"))
        out.append((all(b < 128 for b in open(a, "rb").read()),
                    "wiring:%s:ascii" % d, "non-ASCII bytes in arsenal"))
        chk = os.path.join(HUNT, d, "checklist.md")
        c = open(chk, encoding="utf-8", errors="replace").read() if os.path.isfile(chk) else ""
        out.append((bool(re.search(r"NEW 20(?:2[4-9]|[3-9]\d)|bypass-arsenal", c)),
                    "wiring:%s:checklist-marker" % d,
                    "checklist lacks a NEW-20xx / bypass-arsenal marker"))
        for link in re.findall(r"\[\[([a-z0-9-]+)\]\]", body):
            out.append((_wiki_exists(link),
                        "wiring:%s:link:%s" % (d, link),
                        "arsenal links [[%s]] but no wiki/*/%s.md exists" % (link, link)))
    return out


def eval_recall():
    out = []
    for label, rel, alts in RECALL:
        p = os.path.join(ROOT, rel)
        body = open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""
        low = body.lower()
        out.append((any(a.lower() in low for a in alts),
                    "recall:" + label,
                    "none of %s found in %s" % (alts, rel)))
    return out


def main():
    results = eval_routing() + eval_wiring() + eval_recall()
    fails = 0
    for ok, name, why in results:
        if not ok:
            fails += 1
            print("[FAIL] %s - %s" % (name, why))
        elif "-v" in sys.argv:
            print("[PASS] %s" % name)
    print("skill-eval: %d passed, %d failed" % (len(results) - fails, fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
