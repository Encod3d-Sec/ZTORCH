"""Claim-side gate: success-verb sentences in PoC/Impact must cite a fresh capture path."""
import os
import importlib.util
import textwrap

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("fl", os.path.join(VAULT, "scripts", "find-lint.py"))
find_lint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(find_lint)


def _card(tmp_path, poc, impact):
    p = tmp_path / "FIND-01-HIGH-claim.md"
    p.write_text(textwrap.dedent(
        "---\n"
        "status: CONFIRMED\n"
        "severity: high\n"
        "counterevidence: none found\n"
        "confidence: high\n"
        "severity_change_conditions: n/a\n"
        "---\n"
        "\n"
        "# FIND-01 claim\n"
        "\n"
        "## Description\n"
        "Endpoint lacks auth.\n"
        "\n"
        "## Proof of Concept\n"
        + poc + "\n"
        "## Impact\n"
        + impact + "\n"
        "## Remediation\n"
        "Add auth.\n"
    ), encoding="utf-8")
    return p


def _issues(card):
    issues, _warnings = find_lint.lint_file(card)
    return issues


def test_claim_without_path_fails(tmp_path):
    card = _card(tmp_path, "I dumped the user table.\n", "Attacker bypassed auth.\n")
    issues = _issues(card)
    assert any("claim without fresh capture" in i for i in issues)


def test_claim_with_existing_path_passes(tmp_path):
    cap = tmp_path / "poc" / "01-dump.txt"
    cap.parent.mkdir()
    cap.write_text("raw", encoding="utf-8")
    card = _card(
        tmp_path,
        "I dumped the user table, capture at poc/01-dump.txt.\n",
        "Auth bypassed per poc/01-dump.txt.\n",
    )
    issues = _issues(card)
    assert not any("claim without fresh capture" in i for i in issues)


def test_claim_with_missing_path_fails(tmp_path):
    card = _card(
        tmp_path,
        "I dumped the user table, capture at poc/99-gone.txt.\n",
        "Data exfiltrated.\n",
    )
    issues = _issues(card)
    assert any("claim without fresh capture" in i for i in issues)


def test_hedged_future_tense_not_flagged(tmp_path):
    card = _card(tmp_path, "An attacker could dump the user table.\n", "Impact if abused.\n")
    issues = _issues(card)
    assert not any("claim without fresh capture" in i for i in issues)


def test_fenced_commands_not_flagged(tmp_path):
    card = _card(tmp_path, "```\ncurl -s http://x/api | jq .\n```\nDone.\n", "Read access.\n")
    issues = _issues(card)
    assert not any("claim without fresh capture" in i for i in issues)
