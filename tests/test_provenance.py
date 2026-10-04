import importlib.util
import os
import sys

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(VAULT, "scripts"))  # offensive.py imports offensive_index
_spec = importlib.util.spec_from_file_location("off", os.path.join(VAULT, "scripts", "offensive.py"))
off = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(off)


def test_provenance_block_shape():
    b = off._provenance_block(merged=2)
    assert b.startswith("<!-- provenance")
    assert b.rstrip().endswith("-->")
    for tok in ("generator: offensive.py board", "needs-review: true",
                "assumptions: 2 hand-edited row(s) preserved verbatim"):
        assert tok in b
    assert "needs-review: false" in off._provenance_block(merged=0)


def test_provenance_replace_is_idempotent():
    text = off._provenance_block(merged=1) + "\n# Approach\n\nrows\n"
    once = off._apply_provenance(text, merged=3)
    assert once.count("<!-- provenance") == 1
    assert "merged=3" in once or "3 hand-edited" in once
