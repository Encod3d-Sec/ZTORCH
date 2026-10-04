import importlib.util
import os

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("st", os.path.join(VAULT, "scripts", "status.py"))
st = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(st)


def _find(eng, name, sev, status):
    body = "---\ntitle: t\nseverity: %s\nstatus: %s\naffected: a\n---\n# t\n" % (sev, status)
    (eng / "Vulns" / "web01").mkdir(parents=True, exist_ok=True)
    (eng / "Vulns" / "web01" / name).write_text(body, encoding="utf-8")


def test_risk_math_and_bands(tmp_path):
    eng = tmp_path / "eng"
    eng.mkdir()
    _find(eng, "FIND-01-CRITICAL-a.md", "CRITICAL", "CONFIRMED")
    _find(eng, "FIND-02-HIGH-b.md", "HIGH", "DETECTED")
    _find(eng, "FIND-03-MEDIUM-c.md", "MEDIUM", "RESEARCH")
    _find(eng, "FIND-04-LOW-d.md", "LOW", "EXPLOITED")
    _find(eng, "FIND-05-CRITICAL-e.md", "CRITICAL", "FALSE_POSITIVE")
    line = st.risk_line(str(eng))
    # crit*10 + high*5 + med*2 + low*0.5 = 10+5+2+0.5 = 17.5 -> MEDIUM band (<=30)
    assert line.startswith("risk: MEDIUM (score 17.5, open: 1c/1h/1m/1l)")
    assert "fix-rate: 25% (1/4)" in line       # exploited 1 of 4 actionable


def test_risk_line_absent_without_findings(tmp_path):
    eng = tmp_path / "eng"
    eng.mkdir()
    assert st.risk_line(str(eng)) is None


def test_activity_line_excludes_blocked_from_rate(tmp_path):
    eng = tmp_path / "eng"
    eng.mkdir()
    import json
    ev = [{"kind": "tool", "tool": "Bash"}] * 7 + \
         [{"kind": "hook", "hook": "drift-guard", "action": "deny"}] * 3
    with open(eng / ".events.jsonl", "w", encoding="utf-8") as fh:
        for e in ev:
            fh.write(json.dumps(e) + "\n")
    line = st.activity_line(str(eng))
    # rate over executed only: 7 executed of 7+3 total -> 70.0%
    assert line == "calls 7 blocked 3 rate 70.0% cleanup-pending 0"
