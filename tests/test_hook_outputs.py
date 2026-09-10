"""pass 12: hook OUTPUT-CONTRACT smoke test (the registration gap).

check-hooks.py verifies every hook is REGISTERED; nothing verified what a hook
PRINTS. Channel contracts differ by event (the .zcode/config.json mapping is
the source of truth):

- "strict" (PreToolUse/PostToolUse): stdout feeds the decision/context
  machinery. Legal: silence, or ONE JSON object carrying hookSpecificOutput.
  Anything else (a diagnostic line, a bare string, prose before/after the
  JSON) corrupts the stream for any JSON-parsing consumer.
- "context" (SessionStart/UserPromptSubmit/Stop): stdout IS the injection
  channel - plain prose is the point (live-observed: engagement-init's state
  block lands verbatim). We only flag the half-built dict: output that parses
  as a single JSON object yet lacks hookSpecificOutput (a JSON attempt gone
  wrong, never deliberate prose).

Payloads are deliberately minimal: this pins the OUTPUT SHAPE on the no-op
path; behavior is each hook's own test file's business.
"""
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOOKS = ROOT / "skills" / "hooks"

CASES = [
    # PreToolUse (strict)
    ("scope-guard.py", "strict",
     {"tool_name": "Bash", "tool_input": {"command": "ls"}}),
    ("drift-guard.py", "strict",
     {"tool_name": "Bash", "tool_input": {"command": "ls"}}),
    ("sleep-guard.py", "strict",
     {"tool_name": "Bash", "tool_input": {"command": "sleep 20"}}),
    ("zg-nudge.py", "strict",
     {"tool_name": "Bash", "tool_input": {"command": "grep -r x ."}}),
    ("tmux-nudge.py", "strict",
     {"tool_name": "Bash", "tool_input": {"command": "tmux ls"}}),
    ("burp-nudge.py", "strict",
     {"tool_name": "Bash", "tool_input": {"command": "curl -s x"}}),
    ("session-guard.py", "strict",
     {"tool_name": "Write", "tool_input": {"file_path": "/x.md", "content": "y"}}),
    ("big-read.py", "strict",
     {"tool_name": "Read", "tool_input": {"file_path": "/etc/hosts"}}),
    # PostToolUse (strict)
    ("recon-capture.py", "strict",
     {"tool_name": "Bash", "tool_input": {"command": "true"}, "tool_response": "ok"}),
    ("capture-poc.py", "strict",
     {"tool_name": "Bash", "tool_input": {"command": "true"}, "tool_response": "ok"}),
    ("tool-telemetry.py", "strict",
     {"tool_name": "Bash", "tool_input": {"command": "true"}, "tool_response": "ok"}),
    ("wiki-reindex.py", "strict",
     {"tool_name": "Write", "tool_input": {"file_path": "/tmp/x.md", "content": "x"}}),
    # context-channel hooks
    ("hunt-trigger.py", "context", {"prompt": "continue the engagement"}),
    ("close-out.py", "context", {"session_id": "t", "transcript_path": "/nonexistent.jsonl"}),
    ("engagement-init.py", "context", {"session_id": "t", "source": "startup"}),
]


def _run(script, payload, vault):
    env = dict(os.environ, ZTORCH_VAULT=str(vault),
               ENFORCE_OFF_MARKER=str(vault / ".no-enforce-off"))
    return subprocess.run([sys.executable, str(HOOKS / script)],
                          input=json.dumps(payload), capture_output=True,
                          text=True, timeout=60, env=env)


def test_every_hook_stdout_is_contract_shaped(tmp_path):
    vault = tmp_path / "vault"
    (vault / "targets").mkdir(parents=True)
    bad = []
    for script, channel, payload in CASES:
        r = _run(script, payload, vault)
        if r.returncode != 0:
            bad.append("%s: exit %d (%s)" % (script, r.returncode,
                                             r.stderr.strip()[:120]))
            continue
        out = r.stdout.strip()
        if not out:
            continue                          # silence is always contract-legal
        try:
            doc = json.loads(out)             # single JSON object?
            single = True
        except ValueError:
            single = False
        if channel == "strict":
            if not single:
                bad.append("%s: non-JSON stdout: %r" % (script, out[:80]))
            elif not isinstance(doc.get("hookSpecificOutput"), dict):
                bad.append("%s: JSON without hookSpecificOutput: %s"
                           % (script, sorted(doc)))
        else:
            if single and (not isinstance(doc, dict)
                           or not isinstance(doc.get("hookSpecificOutput"), dict)):
                bad.append("%s: half-built JSON (parses, no hookSpecificOutput) "
                           "- use plain prose or the full shape: %s"
                           % (script, out[:80]))
    assert not bad, "hook output-contract violations:\n  " + "\n  ".join(bad)
