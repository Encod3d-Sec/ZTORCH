#!/usr/bin/env python3
"""SessionStart hook: auto-register vault skills + inject the session hot cache.

Python-only on purpose: ZCode hook commands run through whatever shell the seat
has (cmd/Git Bash on Windows), so this hook must not depend on bash. The
install-skills subprocess is best-effort (fails open when bash is absent);
everything else is pure python.

ZCode parses hook stdout as strict hook JSON, so the hot cache is emitted as
SessionStart additionalContext via _emit (plain text would be discarded).
Fail open: any error -> empty output, exit 0.
"""
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _emit  # noqa: E402

VAULT = os.path.dirname(os.path.dirname(HERE))


def _rotate_hot(hot_path, archive_path, keep=3):
    """Enforce hot.md's own 'Keep ~3 newest entries' header: archive older entries to
    hot-archive.md VERBATIM (nothing is deleted). Ranked by the YYYY-MM-DD in each '## '
    heading; undated headings are always kept (nothing to rank them by). No-op -- no
    writes at all -- while the file is within budget, so sessions that add nothing
    touch nothing."""
    try:
        with open(hot_path, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines(keepends=True)
    except OSError:
        return
    head, entries, cur = [], [], None
    for ln in lines:
        if ln.startswith("## "):
            if cur:
                entries.append(cur)
            cur = [ln]
        elif cur is not None:
            cur.append(ln)
        else:
            head.append(ln)
    if cur:
        entries.append(cur)
    dated = []
    for i, e in enumerate(entries):
        m = re.match(r"## (\d{4}-\d{2}-\d{2})", e[0])
        dated.append((m.group(1) if m else None, i, e))
    keep_idx = {i for d, i, _e in dated if d is None}
    ranked = sorted((x for x in dated if x[0]), key=lambda x: x[0], reverse=True)
    keep_idx |= {i for _d, i, _e in ranked[:keep]}
    drop = [e for d, i, e in dated if i not in keep_idx]
    if not drop:
        return
    try:
        with open(archive_path, "a", encoding="utf-8") as f:
            f.write("\n<!-- archived from hot.md %s (hot.md keeps ~%d newest entries) -->\n"
                    % (time.strftime("%Y-%m-%d"), keep))
            for e in drop:
                f.write("".join(e).rstrip("\n") + "\n")
        with open(hot_path, "w", encoding="utf-8") as f:
            f.write("".join(head)
                    + "".join("".join(e).rstrip("\n") + "\n\n"
                              for d, i, e in dated if i in keep_idx))
    except OSError:
        return


def main():
    # Auto-register vault skills so a freshly-authored skill is invocable without a
    # manual setup/install-skills.sh run. Idempotent; best-effort (bash may be
    # absent on some seats); the harness rescans on session start.
    try:
        subprocess.run(
            ["bash", os.path.join(VAULT, "setup", "install-skills.sh")],
            cwd=VAULT, timeout=90,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL)
    except Exception:
        pass

    # Enforce the hot.md entry budget BEFORE injecting, so the session sees the trimmed
    # cache (and the file can never regrow to an unbounded per-turn context cost).
    try:
        _rotate_hot(os.path.join(VAULT, "session", "hot.md"),
                    os.path.join(VAULT, "session", "hot-archive.md"))
    except Exception:
        pass

    # Inject the session hot cache into context.
    try:
        hot = os.path.join(VAULT, "session", "hot.md")
        if os.path.isfile(hot):
            with open(hot, encoding="utf-8", errors="replace") as f:
                txt = f.read().strip()
            if txt:
                _emit.emit(txt)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    try:
        _emit.flush("SessionStart")
    except Exception:
        pass
    sys.exit(0)
