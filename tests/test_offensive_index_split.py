"""Wave 5: the vault-markdown index compiler (CACHE_NAME, parse_routing_table,
parse_tool_index, parse_hunt_method, build_index, load_index, index_stale, plus the
_read/_die/_section helpers those need) moves from offensive.py into its own
offensive_index.py module, re-exported from offensive.py so every existing caller
(offensive.py's own cmd_index/cmd_board/cmd_next/cmd_foothold/cmd_done, and the test
suite's offensive.<name> call sites) keeps working unchanged."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import offensive  # noqa: E402
import offensive_index  # noqa: E402

VAULT = ROOT / "tests" / "fixtures" / "offensive"


def test_offensive_index_module_has_the_symbols():
    for name in ("CACHE_NAME", "build_index", "load_index", "index_stale",
                 "parse_routing_table", "parse_tool_index", "parse_hunt_method",
                 "_read", "_die", "_section"):
        assert hasattr(offensive_index, name), f"offensive_index missing {name}"


def test_offensive_reexports_are_the_same_objects():
    """Re-export, not a copy -- offensive.X must be identically offensive_index.X."""
    for name in ("CACHE_NAME", "build_index", "load_index", "index_stale",
                 "parse_routing_table", "parse_tool_index", "parse_hunt_method",
                 "_read", "_die", "_section"):
        assert getattr(offensive, name) is getattr(offensive_index, name), (
            f"offensive.{name} is not the same object as offensive_index.{name}")


def test_parse_routing_table_still_works_through_offensive():
    """A real behavior check, not just an identity check: the re-exported function still runs."""
    rt = offensive.parse_routing_table(VAULT)
    assert rt["ssrf"]["skill"] == "hunt-ssrf"


def test_build_index_still_works_through_offensive(tmp_path):
    idx = offensive.build_index(tmp_path, VAULT)
    assert set(idx["routing"]) == {"ssrf", "idor", "sqli", "login-form"}
    assert (tmp_path / offensive.CACHE_NAME).exists()
