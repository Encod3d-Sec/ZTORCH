#!/usr/bin/env python3
"""check-routing.py - exit 1 if the routing data files drift. One line per violation.

Consumers fail OPEN and per-entry (a bad regex silently drops one fingerprint /
trigger / tell row forever - next_move.py, hunt-trigger.py, tells.py all `continue`
on re.error). This check makes that drift loud at edit time instead.

Validated:
  playbook.json    regexes, skills, refs, prio/approach/tools enums
  chains.json      edge keys + to_class in the class vocab, scalar-or-null skill,
                   cost/gate enums, gain/likelihood/to_phase types
  tells.json       re-or-fname present + compiles, scalar + resolving skill
  triggers.json    keys compile (values: skill resolution lives in lint-wiki)
  coverage-classes valid str -> [str] map

playbook refs/skills and triggers values reuse lint-wiki.check_playbook /
check_triggers so the two linters can never disagree.
"""
import ast
import difflib
import importlib.util
import json
import os
import re
import sys

VAULT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, VAULT)
sys.path.insert(0, os.path.join(VAULT, "skills", "hooks"))
sys.path.insert(0, os.path.join(VAULT, "scripts"))   # `import offensive` below: this file's own dir

# lint-wiki.py has a hyphen in its name; import by path (test_zcode_config_hooks
# precedent for importing hyphenated scripts).
_spec = importlib.util.spec_from_file_location(
    "lint_wiki", os.path.join(VAULT, "scripts", "lint-wiki.py"))
lint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lint)

# ponytail: _class_vocab() is the canonical vocab but importing it pulls the
# engagement hook modules; ast-extract the static CLASS_ALIASES literal instead,
# plus coverage-classes values - swap to `import _engagement; _engagement_classes.
# _class_vocab()` if CLASS_ALIASES ever stops being a plain literal.
def class_vocab():
    src = open(os.path.join(VAULT, "skills", "hooks", "_engagement_classes.py"),
               encoding="utf-8").read()
    m = re.search(r"CLASS_ALIASES\s*=\s*(\{.*?\n\})", src, re.S)
    if not m:
        return set()
    aliases = ast.literal_eval(m.group(1))
    vocab = set(aliases.keys())
    try:
        cc = json.load(open(os.path.join(VAULT, "scripts", "coverage-classes.json"),
                            encoding="utf-8"))
        for v in cc.values():
            if isinstance(v, list):
                vocab.update(c.lower() for c in v)
    except Exception:
        pass
    return {c.lower() for c in vocab}


def _tool_slugs_fn():
    return {f[:-3] for f in os.listdir(os.path.join(VAULT, "wiki", "tools"))
            if f.endswith(".md")}
_tool_slugs = _tool_slugs_fn()


def _skill_names():
    """All skill dir names at any depth (for did-you-mean suggestions)."""
    out = set()
    for root, _, dirs in os.walk(os.path.join(VAULT, "skills")):
        out.update(dirs)
    return out


def _didyoumean(name, names):
    m = difflib.get_close_matches(name, names, n=1)
    return "; did you mean '%s'?" % m[0] if m else ""


def violations(repo=VAULT):
    bad = []
    skills = _skill_names()

    # -- playbook: reuse lint-wiki's checks verbatim, add the enum delta
    bad += lint.check_playbook(lint.existing_basenames(), repo)
    bad += lint.check_triggers(repo)
    try:
        fps = json.load(open(os.path.join(repo, "scripts", "playbook.json"),
                             encoding="utf-8"))["fingerprints"]
    except Exception as e:
        bad.append(("scripts/playbook.json", "unreadable: %s" % e))
        fps = {}
    for key, fp in fps.items():
        if not isinstance(fp, dict):
            bad.append(("playbook [%s]" % key, "value is not an object"))
            continue
        if fp.get("prio") not in (1, 2, 3):
            bad.append(("playbook [%s]" % key,
                        "prio %r not in {1,2,3}" % fp.get("prio")))
        for a in fp.get("approach", []):
            if a not in ("ctf", "bugbounty", "pentest"):
                bad.append(("playbook [%s]" % key, "unknown approach %r" % a))
        tools = fp.get("tools", [])
        if not isinstance(tools, list) or any(not isinstance(t, str) for t in tools):
            bad.append(("playbook [%s]" % key, "tools must be a list of strings"))
        for t in (tools if isinstance(tools, list) else []):
            if t not in _tool_slugs:
                bad.append(("playbook [%s]" % key,
                            "tool slug %r has no wiki/tools/ page (G8 serves a "
                            "generic '%s <target>' line and nothing catches it)" % (t, t)))

    # reverse direction (pass 13): CLASS_TOOL values must also resolve. A dangle
    # here is silent at runtime (the fallback invocation prints, no warning) and
    # every bb engagement emits the mcp/llm rows.
    try:
        import offensive
        for cls, slug in offensive.CLASS_TOOL.items():
            if slug not in _tool_slugs:
                bad.append(("offensive.py CLASS_TOOL",
                            "%s -> %r has no wiki/tools/ page" % (cls, slug)))
    except Exception as e:
        bad.append(("offensive.py", "CLASS_TOOL import failed: %s" % e))

    # -- chains: the whole file is unvalidated today
    vocab = class_vocab()
    try:
        edges = json.load(open(os.path.join(repo, "scripts", "chains.json"),
                               encoding="utf-8"))["edges"]
    except Exception as e:
        bad.append(("scripts/chains.json", "unreadable: %s" % e))
        edges = {}
    for key, edge in edges.items():
        if key.lower() not in vocab:
            bad.append(("chains [%s]" % key, "edge key not in class vocab"))
        if not isinstance(edge.get("then"), list):
            bad.append(("chains [%s]" % key, "then[] missing or not a list"))
            continue
        for i, step in enumerate(edge["then"]):
            loc = "chains [%s] then[%d]" % (key, i)
            if not isinstance(step, dict):
                bad.append((loc, "not an object"))
                continue
            tc = step.get("to_class")
            if tc and tc.lower() not in vocab:
                bad.append((loc, "to_class %r not in class vocab" % tc))
            sk = step.get("skill")
            if sk is not None and not isinstance(sk, str):
                bad.append((loc, "skill must be a SCALAR string or null (next_move "
                                 "splices it into one Skill() line)"))
            elif isinstance(sk, str) and sk and not lint._skill_exists(repo, sk):
                bad.append((loc, "unknown skill %s%s" % (sk, _didyoumean(sk, skills))))
            if step.get("cost") not in (None, "cheap", "medium", "expensive"):
                bad.append((loc, "cost %r not cheap|medium|expensive" % step.get("cost")))
            if step.get("gate") not in (None, "oob"):
                bad.append((loc, "gate %r not None|'oob'" % step.get("gate")))
            if not isinstance(step.get("gain"), int):
                bad.append((loc, "gain must be an int"))
            if not isinstance(step.get("likelihood"), (int, float)):
                bad.append((loc, "likelihood must be numeric"))

    # -- tells: re-or-fname + compiles (tells.py compiles with NO flags), skill resolves
    try:
        tells = json.load(open(os.path.join(repo, "scripts", "tells.json"),
                               encoding="utf-8"))["tells"]
    except Exception as e:
        bad.append(("scripts/tells.json", "unreadable: %s" % e))
        tells = []
    for i, t in enumerate(tells):
        if not isinstance(t, dict):
            continue
        loc = "tells[%d]" % i
        has_re, has_fn = "re" in t, "fname" in t
        if has_re == has_fn:            # both or neither
            bad.append((loc, "exactly one of re|fname required"))
        if has_re:
            try:
                re.compile(t["re"])
            except re.error as e:
                bad.append((loc, "bad regex: %s" % e))
        elif has_fn and not isinstance(t["fname"], str):
            bad.append((loc, "fname must be a string"))
        sk = t.get("skill")
        if sk is not None and not isinstance(sk, str):
            bad.append((loc, "skill must be scalar"))
        elif isinstance(sk, str) and sk and not lint._skill_exists(repo, sk):
            bad.append((loc, "unknown skill %s%s" % (sk, _didyoumean(sk, skills))))
        if not (t.get("class") or "").strip():
            bad.append((loc, "missing class cell"))

    # -- coverage-classes: valid str -> [str] map with known type keys
    try:
        cc = json.load(open(os.path.join(repo, "scripts", "coverage-classes.json"),
                            encoding="utf-8"))
        for k, v in cc.items():
            if k.startswith("_"):
                continue
            if k not in ("pentest", "bugbounty", "ctf"):
                bad.append(("coverage-classes [%s]" % k, "unknown engagement type"))
            if not isinstance(v, list) or any(not isinstance(c, str) for c in v):
                bad.append(("coverage-classes [%s]" % k, "value must be a list of strings"))
    except Exception as e:
        bad.append(("scripts/coverage-classes.json", "unreadable: %s" % e))

    # -- triggers: keys compile (hunt-trigger.py matches with re.I)
    try:
        trig = json.load(open(os.path.join(repo, "skills", "exploit", "hunt", "triggers.json"),
                              encoding="utf-8"))
        for section in ("triggers", "surface_triggers"):
            for key in trig.get(section, {}):
                try:
                    re.compile(key, re.I)
                except re.error as e:
                    bad.append(("%s [%s]" % (section, key), "bad regex: %s" % e))
    except Exception as e:
        bad.append(("skills/exploit/hunt/triggers.json", "unreadable: %s" % e))

    return bad


def main():
    bad = violations()
    for loc, msg in bad:
        print("%s: %s" % (loc, msg))
    print("check-routing: %d violation(s)" % len(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
