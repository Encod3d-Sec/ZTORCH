#!/usr/bin/env python3
"""PreToolUse(Write|Edit) hook: refuse-by-ask text writes onto BINARY files.

Hermes port (docs/port-specs/proposals-aux-eval-guards.md #1, curated): the target
file EXISTS and starts with a known binary magic (PNG/JPEG/GIF/PDF/ZIP/ELF/SQLite/
Java .class) -> permissionDecision "ask" with the reason. A text Write/Edit into a
binary (poc images, loot dbs, capture archives) silently destroys the file: the tool
succeeds, the bytes are gone. Ask, not deny: the operator may genuinely intend a
byte-level patch.

Skipped half, NOTED per the port contract: refusing a whole-file REPLACE of content
the session never Read (hermes _stale_overwrite_blocker) needs read-baseline state
tracked across a PostToolUse(Read) recorder; there is no cheap stateless check, so
that half is out of scope here.

Fail open: any error -> allow silently. skills/hooks/.enforce-off downgrades the ask
to an advisory context line.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# (magic prefix, human name). ZIP covers .docx/.xlsx/.jar; cafebabe is Java .class.
BINARY_MAGICS = (
    (b"\x89PNG\r\n\x1a\n", "PNG image"),
    (b"\xff\xd8\xff", "JPEG image"),
    (b"GIF87a", "GIF image"),
    (b"GIF89a", "GIF image"),
    (b"%PDF-", "PDF document"),
    (b"PK\x03\x04", "ZIP archive (or docx/xlsx/jar)"),
    (b"PK\x05\x06", "ZIP archive (empty)"),
    (b"\x7fELF", "ELF binary"),
    (b"SQLite format 3\x00", "SQLite database"),
    (b"\xca\xfe\xba\xbe", "Java class (or Mach-O fat binary)"),
)


def _enforce_off():
    marker = os.environ.get("ENFORCE_OFF_MARKER") or os.path.join(HERE, ".enforce-off")
    return os.path.exists(marker)


def _binary_kind(path):
    """Magic-prefix name for an existing file, or None (missing/unreadable/empty/text)."""
    try:
        if not os.path.isfile(path):
            return None
        with open(path, "rb") as fh:
            head = fh.read(16)
    except OSError:
        return None
    if not head:
        return None
    for magic, name in BINARY_MAGICS:
        if head.startswith(magic):
            return name
    return None


def main():
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return

    fp = ((data.get("tool_input") or {}).get("file_path") or "")
    if not fp:
        return
    kind = _binary_kind(fp)
    if not kind:
        return

    if _enforce_off():
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": (
                "write-guard (advisory; enforcement OFF via .enforce-off): %s looks "
                "like a %s; a text Write/Edit would destroy it. Confirm you mean it."
                % (fp, kind)),
        }}))
        return

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": (
            "BINARY TARGET: %s is a %s; a text Write/Edit writes UTF-8 over the "
            "bytes and silently destroys the file. Confirm to overwrite, or target "
            "a text export beside it instead." % (fp, kind)),
    }}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
