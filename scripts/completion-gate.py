#!/usr/bin/env python3
"""completion-gate.py - per-run checklist ledger + artifact verification.

The Armada hackbot talk (docs/hackbot-port.md, mined 2026-10-11) measured the
harness's single biggest win: markdown checklists as completion ledgers plus a
review pass that verifies every declared output artifact exists and is
non-zero bytes took collection accuracy from ~0.4% to near-full. The failure
it fixes: a lane reports success, the run "completes", and 13 of 22 output
dirs turn out empty. Self-reports are not completion; artifacts are.

House style: a lens, not a gate. Exit 0 always; the verdict lines go into the
engagement log and the brain decides.

Usage:
  python3 scripts/completion-gate.py init <dir> --title "<run name>" [--steps steps.txt]
      Writes <dir>/run-ledger.md. Steps come from --steps (one per line) or a
      6-step generic lane skeleton. A step line may declare its artifact
      inline: `- probe httpx sweep @ out/httpx.txt`.

  python3 scripts/completion-gate.py check <dir-or-ledger.md> [--capture <dir>]
      Verdicts per checklist box: OK, UNCHECKED (box not ticked), MISSING
      (declared artifact path does not exist), EMPTY (artifact is 0 bytes).
      --capture additionally flags an empty or absent lane capture dir.
      On any failure, prints the GENERIC NUDGE to re-dispatch the lane with
      (verbatim, per the talk: generic beats specific because you do not know
      where it failed).

Steps file format: one step per line, `#` comments ignored. Inline artifact
after ` @ ` (a path containing `/` or a dot-suffixed name).
"""
import argparse
import os
import sys

LEDGER = "run-ledger.md"

GENERIC_SKELETON = [
    "read engagement state + scope before first action",
    "execute the lane's specified window/commands in full",
    "write raw outputs to the capture dir before any post-processing",
    "record the SUCCESS observable verbatim in the envelope",
    "REVERT any target state the run changed",
    "confirm every declared artifact is non-zero and in the capture dir",
]

NUDGE = (
    "GENERIC NUDGE (re-dispatch verbatim): your work was just reviewed and "
    "either a step of the checklist was missed or an artifact of sufficient "
    "proof was not generated. Read run-ledger.md and the output for each step, "
    "find what you missed, and complete it. Do not re-run steps that already "
    "have their artifact; do not report a verdict without the raw observable."
)


def _artifact_of(step_text):
    """Extract the inline artifact path from a step line, or None.

    The path is the single token after ' @ ' (no spaces). Resolved relative to
    the ledger's directory by the caller.
    """
    if " @ " not in step_text:
        return None
    tail = step_text.rsplit(" @ ", 1)[1].strip()
    art = tail.split()[0] if tail.split() else ""
    # path-ish: contains a separator or a dot-suffix; rejects bare words like "done"
    if art and ("/" in art or "\\" in art or ("." in art and not art.endswith("."))):
        return art
    return None


def _resolve(art, ledger_dir):
    """Artifact paths in the ledger are relative to the LEDGER's directory."""
    if os.path.isabs(art):
        return art
    return os.path.join(ledger_dir, art)


def cmd_init(args):
    os.makedirs(args.dir, exist_ok=True)
    path = os.path.join(args.dir, LEDGER)
    if os.path.exists(path):
        sys.stderr.write("completion-gate: %s already exists, leaving it alone\n" % path)
        return
    steps = []
    if args.steps:
        with open(args.steps, encoding="utf-8") as fh:
            steps = [l.strip() for l in fh
                     if l.strip() and not l.strip().startswith("#")]
    if not steps:
        steps = list(GENERIC_SKELETON)
    lines = [
        "# Run ledger - %s" % args.title,
        "",
        "Every box ticked and every artifact non-zero, or the run is not done.",
        "Checked by: `python3 scripts/completion-gate.py check %s`" % args.dir,
        "",
    ]
    for s in steps:
        lines.append("- [ ] %s" % s)
    lines.append("")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print("wrote %s (%d steps)" % (path, len(steps)))


def cmd_check(args):
    target = args.target
    if os.path.isdir(target):
        target = os.path.join(target, LEDGER)
    if not os.path.isfile(target):
        print("VERDICT: NO LEDGER (%s not found) - run was never given a checklist" % target)
        print(NUDGE)
        return
    unchecked, missing, empty, stale, ok = [], [], [], [], 0
    ledger_mtime = os.path.getmtime(target)
    with open(target, encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\n").rstrip("\r")
            if not line.startswith("- ["):
                continue
            text = line[3:].lstrip(" ]").lstrip()
            done = line.startswith("- [x]") or line.startswith("- [X]")
            art = _artifact_of(text)
            if not done:
                unchecked.append(text)
                continue
            if art:
                art_path = _resolve(art, os.path.dirname(os.path.abspath(target)))
                if not os.path.exists(art_path):
                    missing.append(art)
                elif os.path.getsize(art_path) == 0:
                    empty.append(art)
                elif os.path.getmtime(art_path) < ledger_mtime - 2:
                    # artifact older than the ledger's last edit = residue from a
                    # PREVIOUS run; ticking the box does not make it fresh evidence
                    stale.append(art)
                else:
                    ok += 1
            else:
                ok += 1
    capture_note = ""
    if args.capture:
        if not os.path.isdir(args.capture):
            capture_note = "CAPTURE MISSING (%s)" % args.capture
        elif not any(os.scandir(args.capture)):
            capture_note = "CAPTURE EMPTY (%s)" % args.capture
        else:
            capture_note = "capture OK"
    if not unchecked and not missing and not empty and not stale and not capture_note.startswith("CAPTURE"):
        print("VERDICT: COMPLETE (%d steps verified%s)" % (ok, ", " + capture_note if capture_note else ""))
        return
    print("VERDICT: INCOMPLETE run-ledger=%s" % os.path.abspath(target))
    for t in unchecked:
        print("  UNCHECKED: %s" % t)
    for a in missing:
        print("  MISSING (declared, absent): %s" % a)
    for a in empty:
        print("  EMPTY (0 bytes): %s" % a)
    for a in stale:
        print("  STALE (artifact predates the ledger edit - previous run's residue): %s" % a)
    if capture_note.startswith("CAPTURE"):
        print("  %s" % capture_note)
    print("  verified: %d" % ok)
    print(NUDGE)


def main():
    ap = argparse.ArgumentParser(description="run checklist ledger + artifact gate (lens, exit 0)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_init = sub.add_parser("init", help="write a run-ledger.md checklist")
    p_init.add_argument("dir")
    p_init.add_argument("--title", default="lane run")
    p_init.add_argument("--steps", help="steps file, one per line, optional inline artifact after ' @ '")
    p_init.set_defaults(func=cmd_init)
    p_chk = sub.add_parser("check", help="verify a ledger (dir or file)")
    p_chk.add_argument("target", help="engagement/lane dir or run-ledger.md path")
    p_chk.add_argument("--capture", help="lane capture dir to also flag if empty/absent")
    p_chk.set_defaults(func=cmd_check)
    args = ap.parse_args()
    args.func(args)
    sys.exit(0)  # lens, not gate


if __name__ == "__main__":
    main()
