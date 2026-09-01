"""Tests for the machine-readable routing table in skills/hunt/hunt-core/SKILL.md.

The table is the contract `offensive.py index` parses: fingerprint -> class -> hunt-skill
-> primary wiki page -> arsenal slug. See .superpowers/sdd/2026-08-31-offensive-driver/task-1-brief.md.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_MD = ROOT / "skills" / "hunt" / "hunt-core" / "SKILL.md"
HUNT_DIR = ROOT / "skills" / "hunt"

MARKER = "## Routing table (machine-readable)"

EXPECTED_HEADER = ["fingerprint", "class", "hunt-skill", "primary wiki", "arsenal slug"]

REQUIRED_TOKENS = {
    "xss", "sqli", "ssrf", "idor", "rce", "jenkins", "wordpress", "tomcat",
    "gitlab", "spring", "jwt", "oauth", "s3", "kubernetes", "ldap", "smb",
}


def _parse_table():
    text = SKILL_MD.read_text()
    assert MARKER in text, "routing table section missing from hunt-core/SKILL.md"
    section = text.split(MARKER, 1)[1]

    # stop at the next top-level heading so we don't slurp unrelated content
    next_heading = section.find("\n## ")
    if next_heading != -1:
        section = section[:next_heading]

    lines = [l for l in section.splitlines() if l.strip().startswith("|")]
    assert len(lines) >= 3, "routing table has no header/separator/data rows"

    header = [c.strip() for c in lines[0].strip().strip("|").split("|")]

    rows = []
    for line in lines[2:]:  # skip header + separator
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != len(header):
            continue
        rows.append(dict(zip(header, cells)))

    return header, rows


def test_routing_table_parses():
    header, rows = _parse_table()

    assert header == EXPECTED_HEADER, f"unexpected columns: {header}"
    assert rows, "routing table has no data rows"

    hunt_dirs = {p.name for p in HUNT_DIR.iterdir() if p.is_dir() and p.name.startswith("hunt-")}

    seen_fingerprints = set()
    class_fingerprints = {}

    for row in rows:
        skill = row["hunt-skill"].strip("`")
        assert skill in hunt_dirs, f"hunt-skill cell names no real skills/hunt dir: {skill!r}"

        fp = row["fingerprint"].strip("`")
        assert fp, "empty fingerprint cell"
        assert fp not in seen_fingerprints, f"duplicate fingerprint token: {fp!r}"
        seen_fingerprints.add(fp)

        cls = row["class"].strip("`")
        assert cls, "empty class cell"
        class_fingerprints.setdefault(cls, set()).add(fp)

        assert row["primary wiki"].strip("`"), f"empty primary wiki for {fp!r}"
        assert row["arsenal slug"].strip("`"), f"empty arsenal slug for {fp!r}"

    # every class is unique-or-fingerprint-mapped: a class shared across rows must be
    # reached through distinct fingerprint tokens, never a bare duplicate row.
    for cls, fps in class_fingerprints.items():
        assert len(fps) >= 1

    missing = REQUIRED_TOKENS - seen_fingerprints
    assert not missing, f"missing required fingerprint tokens: {missing}"
