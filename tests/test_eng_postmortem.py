"""eng-postmortem.py: offline replay of a finished engagement's log.md (synthetic
fixture; lane shapes reuse lane_validate's regex). Durations are the @HH:MM open cell
to the NEXT timestamped line (approximate, same-day wrap), failure classes come from
`-> NOT VERIFIED` reasons, tool counts from the log grammar tokens."""
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("eng_postmortem", ROOT / "scripts" / "eng-postmortem.py")
em = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(em)

LOG = """# engagement log (synthetic)

- lane web (10.0.0.5) in flight @10:00: SUCCESS = `nmap -p-` done | tmux win 1 | capture poc/web | handle ag-1 -> VERIFIED: poc/web/nmap.txt
- lane sqli (10.0.0.5) in flight @11:00: SUCCESS = `uid=33` | tmux win 2 | capture poc/sqli | handle ag-2 -> NOT VERIFIED: uid=33 absent from capture poc/sqli
- lane ssh (10.0.0.6) in flight @12:00: SUCCESS = `id=0` | tmux win 3 | capture poc/ssh | handle ag-3
tool nmap ok
tool nmap fail
tool gobuster blocked
2026-10-12 12:40 | lane | dispatch | ok | lane ssh re-served
- lane broken in flight doing recon stuff
"""


def _stats():
    return em.parse(LOG)


def test_lane_census_and_verdicts():
    lanes = {l["name"]: l for l in _stats()["lanes"]}
    assert set(lanes) == {"web", "sqli", "ssh"}
    assert lanes["web"]["verified"] and not lanes["web"]["not_verified"]
    assert lanes["sqli"]["not_verified"]
    assert not lanes["ssh"]["closed"]                     # handle-only tail: still open


def test_durations_from_open_cell_to_next_anchor():
    lanes = {l["name"]: l for l in _stats()["lanes"]}
    assert lanes["web"]["dur"] == 60                      # @10:00 -> next anchor @11:00
    assert lanes["sqli"]["dur"] == 60                     # @11:00 -> next anchor @12:00
    assert lanes["ssh"]["dur"] is None                    # never closed


def test_midnight_wrap_is_same_day_heuristic():
    text = ("- lane late (10.0.0.9) in flight @23:50: SUCCESS = `x` | tmux win 4 | capture poc/late | handle ag-9 -> VERIFIED: x\n"
            "2026-10-13 00:10 | cleanup | close | ok | day wrapped\n")
    assert em.parse(text)["lanes"][0]["dur"] == 20


def test_failure_classes_from_not_verified_reasons():
    st = _stats()
    assert st["lanes"][1]["reason"].startswith("uid=33 absent")
    out = em.render(st)
    assert "absent-from-capture" in out and "NOT VERIFIED" in out


def test_tool_and_audit_grammar_counts():
    st = _stats()
    assert st["tools"] == {"ok": 1, "fail": 1, "blocked": 1}
    assert st["tool_fails"] == {"nmap": 1, "gobuster": 1}
    assert st["audit_cats"].get("lane") == 1


def test_envelope_missing_counts():
    st = _stats()
    assert len(st["envelope_missing"]) == 1
    assert "line 10" in st["envelope_missing"][0]         # `- lane broken ...` has no envelope
    assert "envelope problems: 1" in em.render(st)


def test_main_over_eng_dir(tmp_path, capsys):
    (tmp_path / "log.md").write_text(LOG, encoding="utf-8")
    assert em.main(["--eng", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "~60min" in out and "never closed" in out and "nmap=1" in out


def test_main_missing_log_fails_soft(capsys):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        assert em.main(["--eng", d]) == 0
    assert "no log" in capsys.readouterr().out
