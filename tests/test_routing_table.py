"""Tests for the machine-readable routing table in scripts/routing.json.

The JSON is the contract `offensive.py index` parses: fingerprint -> {class,
skill, wiki, arsenal}. Key order in the object IS table order (first key per
class wins in _class_info), which json.load preserves. An empty `skill` value
is a legal G2-skipping state (vector-baseline rows with no doctrine match).
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROUTING_JSON = ROOT / "scripts" / "routing.json"
HUNT_DIR = ROOT / "skills" / "hunt"

REQUIRED_TOKENS = {
    "xss", "sqli", "ssrf", "idor", "rce", "jenkins", "wordpress", "tomcat",
    "gitlab", "spring", "jwt", "oauth", "s3", "kubernetes", "ldap", "smb",
}


def _rows():
    data = json.loads(ROUTING_JSON.read_text())
    return data["routing"]


def test_routing_json_loads():
    rows = _rows()
    assert rows, "routing table has no rows"
    hunt_dirs = {p.name for p in HUNT_DIR.iterdir() if p.is_dir() and p.name.startswith("hunt-")}
    for fp, row in rows.items():
        assert fp, "empty fingerprint key"
        assert set(row) == {"class", "skill", "wiki", "arsenal"}, \
            f"row {fp!r} must carry exactly class/skill/wiki/arsenal"
        skill = row["skill"]
        # empty skill is legal (G2-skipping baseline rows); non-empty must resolve
        if skill:
            assert skill in hunt_dirs, f"skill cell names no real skills/hunt dir: {skill!r}"
        assert row["class"], f"empty class for {fp!r}"
        assert row["wiki"], f"empty primary wiki for {fp!r}"
        assert row["arsenal"], f"empty arsenal slug for {fp!r}"

    missing = REQUIRED_TOKENS - set(rows)
    assert not missing, f"missing required fingerprint tokens: {missing}"
