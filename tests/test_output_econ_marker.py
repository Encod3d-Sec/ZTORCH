"""Non-prose elision marker (port-specs P3, hermes compression_marker port).
The stub's omission marker carries embedded omitted/total counts (a copied marker is
visibly stale) and never a bare '...' ellipsis a model could imitate as prose."""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
                                "scripts"))
import output_econ as oe


def test_stub_marker_carries_counts_and_no_ellipsis():
    data = b"".join(b"line %d %s\n" % (i, b"y" * 40) for i in range(2000))  # >> THRESH
    stub = oe.econ(data, "nmap -p- t", "/ingest/nmap-1.txt")
    m = re.search(rb"\[ZT-ELIDE:(\d+)/(\d+)", stub)
    assert m, "no [ZT-ELIDE:omitted/total marker in stub"
    omitted, total = int(m.group(1)), int(m.group(2))
    assert total == len(data)            # total count embedded and exact
    assert 0 < omitted < total           # omitted count embedded and sane
    assert b"..." not in stub            # no bare ellipsis string to imitate
