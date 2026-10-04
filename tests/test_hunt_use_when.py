import glob
import os
import re

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_every_hunt_description_ends_with_use_when():
    skills = sorted(glob.glob(os.path.join(VAULT, "skills", "hunt", "hunt-*", "SKILL.md")))
    assert len(skills) == 27
    for p in skills:
        text = open(p, encoding="utf-8").read()
        m = re.search(r"^description:\s*(.+)$", text, re.M)
        assert m, p
        assert m.group(1).rstrip().endswith("."), p
        tail = m.group(1).lower()
        assert tail.rfind("use when") > len(tail) * 0.5, (p, m.group(1)[-80:])


CORE = os.path.join(VAULT, "skills", "hunt", "hunt-core", "SKILL.md")


def test_hunt_core_carries_rules_ladder_violations():
    t = open(CORE, encoding="utf-8").read()
    for tok in ("wiki-first", "OOB gate", "verification before status change",
                "gave-up-by-repetition", "hallucination", "omission",
                "SOCKS5", "ladder:", "Recommended next"):
        assert tok in t, tok


def test_ladder_order():
    t = open(CORE, encoding="utf-8").read()
    seq = ["change UA", "reader proxy", "page cache", "archive", "alt engine", "SOCKS5"]
    pos = [t.index(s) for s in seq]
    assert pos == sorted(pos)
