#!/usr/bin/env python3
"""Advisory lint over every skills/**/SKILL.md. Prints issues, always exits 0.

Checks: frontmatter parses as YAML dict; name kebab-case <= 64 chars; description
<= 1024 chars with no bare angle brackets; frontmatter keys within the official six
plus this vault's own keys; balanced code fences; scripts/*.sh invoked with the
`bash scripts/...` spelling (exec bits unreliable on NTFS).
"""
import re
import sys
from pathlib import Path

OFFICIAL_KEYS = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}
# Census 2026-10-05 over all 57 skills/**/SKILL.md: disable-model-invocation (agents-md-improver),
# tools (agents-md-improver), type (wiki).
VAULT_KEYS = {"disable-model-invocation", "tools", "type"}
ALLOWED_KEYS = OFFICIAL_KEYS | VAULT_KEYS
NAME_RE = re.compile(r"^[a-z0-9-]{1,64}$")
FENCE_RE = re.compile(r"^\s*```", re.M)
SCRIPT_CALL_RE = re.compile(r"(?<!bash )(?<!`bash )scripts/[A-Za-z0-9_-]+\.sh")


def parse_frontmatter(text):
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end < 0:
        return None
    out = {}
    for line in text[4:end].splitlines():
        if ":" in line and not line.startswith((" ", "\t", "-")):
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip()
    return out


def lint_skill(path):
    issues = []
    text = path.read_text(encoding="utf-8-sig")  # utf-8-sig: strips a leading BOM, plain UTF-8 otherwise
    fm = parse_frontmatter(text)
    if fm is None:
        return ["%s: frontmatter missing or unparsable" % path]
    name = fm.get("name", "")
    if not NAME_RE.match(name):
        issues.append("%s: name not kebab-case <= 64: %r" % (path, name))
    desc = fm.get("description", "")
    if len(desc) > 1024:
        issues.append("%s: description over 1024 chars (%d)" % (path, len(desc)))
    if "<" in desc or ">" in desc:
        issues.append("%s: bare angle bracket in description" % path)
    for key in fm:
        if key not in ALLOWED_KEYS:
            issues.append("%s: unknown frontmatter key %r (add to VAULT_KEYS if intentional)"
                          % (path, key))
    if len(FENCE_RE.findall(text)) % 2:
        issues.append("%s: unbalanced code fences" % path)
    body = text.split("---", 2)[-1]
    for m in SCRIPT_CALL_RE.finditer(body):
        issues.append("%s: invoke as `bash %s` (exec bits unreliable on NTFS)"
                      % (path, m.group(0)))
    return issues


def lint_all(vault_root):
    root = Path(vault_root)
    issues = []
    for p in sorted(root.glob("skills/**/SKILL.md")):
        issues.extend(lint_skill(p))
    return issues


def main():
    root = Path(__file__).resolve().parents[1]
    issues = lint_all(root)
    for i in issues:
        print(i)
    print("skill-lint: %d issue(s) across skills/ (advisory)" % len(issues))
    return 0


if __name__ == "__main__":
    sys.exit(main())
