import os
import importlib.util

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("fl", os.path.join(VAULT, "scripts", "find-lint.py"))
fl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fl)

_BODY = """---
title: t
severity: MEDIUM
status: {status}
affected: a
cvss: ""
---

## Description

{desc}

## Proof of Concept

```
curl http://{{target_ip}}/x
```

## Impact

Reads cross-user data.

## Remediation

Fix the authz check.
"""


def _write(tmp_path, status, extra=""):
    p = tmp_path / ("FIND-01-MEDIUM-x.md")
    p.write_text(_BODY.format(status=status, desc="desc " + extra + " padding to fifteen"))
    return str(p)


def test_confirmed_requires_capture_path(tmp_path):
    issues, _ = fl.lint_file(_write(tmp_path, "CONFIRMED"))
    assert any("capture path" in i for i in issues)


def test_confirmed_with_capture_path_passes_ladder_rule(tmp_path):
    issues, _ = fl.lint_file(_write(tmp_path, "CONFIRMED", extra="evidence: poc/03-ssrf-pair.png"))
    assert not any("capture path" in i for i in issues)


def test_research_alias_and_detected_do_not_require_capture(tmp_path):
    for st in ("RESEARCH", "DETECTED"):
        issues, _ = fl.lint_file(_write(tmp_path, st))
        assert not any("capture path" in i for i in issues)
