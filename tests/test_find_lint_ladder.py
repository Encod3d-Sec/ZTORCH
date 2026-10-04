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


_LADDER_COMMENT = ("   # ladder: DETECTED (tool hit, unverified) -> CONFIRMED "
                   "(PoC validated + poc/ capture) -> EXPLOITED (used in the chain); "
                   "RESEARCH = alias of DETECTED")


def test_template_ladder_comment_does_not_satisfy_capture_gate(tmp_path):
    # scaffolded from the new template: status line carries the full trailing ladder
    # comment (verbatim from setup/templates/_find.md), body has no poc/ ref anywhere
    p = tmp_path / "FIND-02-MEDIUM-x.md"
    p.write_text(_BODY.format(status="CONFIRMED" + _LADDER_COMMENT,
                              desc="desc padding to fifteen"))
    issues, _ = fl.lint_file(str(p))
    assert any("capture path" in i for i in issues)


_PLACE_POC = """---
title: t
severity: MEDIUM
status: CONFIRMED
affected: a
cvss: ""
---

## Description

desc padding to fifteen chars.

## Proof of Concept

```
<# step 1 ...>
```

## Impact

Reads cross-user data.

## Remediation

Fix the authz check.
"""


def _write_raw(tmp_path, body, name="FIND-03-MEDIUM-x.md"):
    p = tmp_path / name
    p.write_text(body)
    return str(p)


def test_confirmed_absent_capture_file(tmp_path):
    body = _PLACE_POC.replace("<# step 1 ...>", "curl -s http://10.0.0.5/x")
    body = body.replace("desc padding", "desc evidence: poc/99-absent.png padding")
    issues, _ = fl.lint_file(_write_raw(tmp_path, body))
    assert any(i.startswith("STILL VERIFYING - missing:") and "absent" in i for i in issues)


def test_confirmed_placeholder_poc(tmp_path):
    issues, _ = fl.lint_file(_write_raw(tmp_path, _PLACE_POC))
    assert any(i.startswith("STILL VERIFYING - missing:") and "placeholder" in i
               for i in issues)


def test_confirmed_real_poc_passes(tmp_path):
    body = _PLACE_POC.replace("<# step 1 ...>", "curl -s http://10.0.0.5/x")
    body = body.replace("desc padding", "desc evidence: poc/03-ok.png padding")
    (tmp_path / "poc").mkdir()
    (tmp_path / "poc" / "03-ok.png").write_bytes(b"x")
    issues, _ = fl.lint_file(_write_raw(tmp_path, body))
    assert not any("STILL VERIFYING" in i for i in issues)


def test_false_positive_needs_reason_prefix(tmp_path):
    body = _PLACE_POC.replace("status: CONFIRMED", "status: FALSE_POSITIVE")
    issues, _ = fl.lint_file(_write_raw(tmp_path, body))
    assert any("FP:" in i for i in issues)


def test_false_positive_with_prefix_skips_evidence(tmp_path):
    body = _PLACE_POC.replace("status: CONFIRMED", "status: FALSE_POSITIVE")
    # fill the template placeholder: section_nonempty treats a bare <...> PoC as empty
    body = body.replace("<# step 1 ...>", "curl -s http://10.0.0.5/x")
    body = body.replace("desc padding", "FP: intended behavior, confirmed with admin")
    issues, _ = fl.lint_file(_write_raw(tmp_path, body))
    assert not issues


def test_ignored_with_prefix_skips_evidence(tmp_path):
    body = _PLACE_POC.replace("status: CONFIRMED", "status: IGNORED")
    body = body.replace("<# step 1 ...>", "curl -s http://10.0.0.5/x")
    body = body.replace("desc padding", "IGNORED: out of program scope per rules page")
    issues, _ = fl.lint_file(_write_raw(tmp_path, body))
    assert not issues
