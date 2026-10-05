import importlib.util
import os

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("nm", os.path.join(VAULT, "scripts", "next_move.py"))
nm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nm)


def test_verb_render():
    line = nm.format_chain_move("web01", "ssrf", "rce",
                                {"move": "pivot to metadata", "verb": "enables"},
                                "", "")
    assert "[enables]" in line and "ssrf->rce" in line


def test_no_verb_renders_as_before():
    line = nm.format_chain_move("web01", "ssrf", "rce", {"move": "pivot"}, "", "")
    assert "[" not in line.split(" - ")[0].replace("web01", "")


def test_chains_json_verbs_in_enum():
    import json
    d = json.load(open(os.path.join(VAULT, "scripts", "chains.json"), encoding="utf-8"))
    enum = {"discovered_on", "enables", "exploits", "depends_on", "links_vuln"}
    for edge in d.get("edges", {}).values():
        for cand in edge.get("then", []):
            if "verb" in cand:
                assert cand["verb"] in enum
