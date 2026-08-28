"""ZCode hook stdout contract: strict hook JSON or nothing.

ZCode parses hook stdout against the HookJSONOutput schema; plain-text output
fails validation and is discarded (recoverable error, context never injected).
emit() buffers the hook's advisory messages and flush() prints them as one
event-typed hookSpecificOutput payload -- the shape the runtime accepts for
SessionStart / UserPromptSubmit / Stop context injection.
"""
import json

_BUF = []


def emit(msg):
    """Buffer one advisory message (replaces a bare print)."""
    if msg:
        _BUF.append(msg)


def flush(event_name):
    """Print buffered messages as valid hook JSON; an empty buffer prints nothing."""
    if not _BUF:
        return
    payload = {"hookSpecificOutput": {"hookEventName": event_name,
                                      "additionalContext": "\n\n".join(_BUF)}}
    print(json.dumps(payload))
    del _BUF[:]
