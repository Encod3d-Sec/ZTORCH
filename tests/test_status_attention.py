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


def _oob(eng, token, status):
    row = "| %s | sink | ssrf | 10:00 | %s | src |\n" % (token, status)
    p = eng / "oob.md"
    t = p.read_text(encoding="utf-8") if p.exists() else (
        "# OOB\n\n| token | sink | class | planted | status | source |\n"
        "|---|---|---|---|---|---|\n")
    p.write_text(t + row, encoding="utf-8")


def test_attention_rows_and_priorities(tmp_path):
    eng = tmp_path / "eng"
    eng.mkdir()
    (eng / "log.md").write_text("", encoding="utf-8")
    _oob(eng, "tok1", "waiting")
    _oob(eng, "tok2", "HIT")
    _find(eng, "FIND-06-CRITICAL-f.md", "CRITICAL", "CONFIRMED")
    (eng / "changelog.md").write_text(
        "| # | time | host | type | location | content | rollback | verified |\n"
        "|---|---|---|---|---|---|---|---|\n"
        "| 1 | 10:00 | h | config | /x | c | `r` |  |\n", encoding="utf-8")
    rows = st.attention_rows(str(eng))
    keys = [k for k, _, _, _ in rows]
    assert "oob:1" in keys and "cleanup:1" in keys and "crit:1" in keys
    pri = {k: p for k, p, _, _ in rows}
    assert pri["oob:1"] == "p0" and pri["cleanup:1"] == "p0" and pri["crit:1"] == "p0"
    act = {k: a for k, _, a, _ in rows}
    assert act["oob:1"].startswith("ACTION REQUIRED")


def test_dismissal_fingerprint_equality_and_rearm(tmp_path):
    eng = tmp_path / "eng"
    eng.mkdir()
    (eng / "log.md").write_text("", encoding="utf-8")
    _oob(eng, "tok1", "waiting")
    _find(eng, "FIND-07-CRITICAL-g.md", "CRITICAL", "CONFIRMED")
    # crit is dismissable; oob is not -> fingerprint over dismissable keys only
    st.attention_store(str(eng), ["crit:1"])
    assert st.attention_suppressed(str(eng), ["crit:1"]) is True
    assert st.attention_suppressed(str(eng), ["crit:2"]) is False   # new count re-arms
    st.attention_reset(str(eng))
    assert st.attention_suppressed(str(eng), ["crit:1"]) is False


def test_actionable_never_dismissed(tmp_path):
    eng = tmp_path / "eng"
    eng.mkdir()
    (eng / "log.md").write_text("", encoding="utf-8")
    _oob(eng, "tok1", "waiting")
    st.attention_store(str(eng), ["oob:1"])
    rows = st.attention_rows(str(eng))
    assert any(k == "oob:1" for k, _, _, _ in rows)   # still rendered
