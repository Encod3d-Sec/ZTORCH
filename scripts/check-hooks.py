#!/usr/bin/env python3
"""Canonical expected vault-hook set + drift detector (hooks AND skills).

Single source of truth for which vault hooks SHOULD be registered in this
machine's ~/.claude/settings.json. settings.json is machine-local and does not
sync across devices, so a hook can silently go unregistered on one machine
(hooks fail open + silent, so the omission is invisible). This module lets the
SessionStart hook surface that drift as one advisory line.

When you add a new vault hook to setup/install-hooks.sh, also add it to
EXPECTED_HOOKS below so the drift check stays accurate on every device.

missing_hooks() returns the expected hooks that are absent from settings.json,
including hooks registered only under the WRONG event (a hook on the wrong
event never fires where the framework expects it, so it fails like a missing
one, named as "base (expected X, registered under Y)"). It fails open: an
unreadable or missing settings.json returns [] (we cannot assert drift without
the file).

unregistered_scripts() WARNs on skills/hooks scripts registered under NO event
in the committed .zcode/config.json, and pycache_audit() WARNs on (and deletes)
orphaned __pycache__ bytecode whose source .py is gone. Both are advisory: they
never flip the exit code.

missing_skills() does the parallel check for skills: setup/install-skills.sh
symlinks every SKILL.md-bearing dir under skills/ into ~/.claude/skills so the
Skill tool + /skills picker can load it. That dest is also machine-local and the
installer is only re-run by hand, so a newly added vault skill can sit
unregistered (Skill(<name>) -> "Unknown skill") while triggers.json still routes
to it. No EXPECTED list to maintain: the SKILL.md walk IS the source of truth,
identical to the installer's `find skills -name SKILL.md`.
"""
import json
import os
import sys

# (event, script_basename) pairs the per-device installer registers.
# Match this to setup/install-hooks.sh.
EXPECTED_HOOKS = [
    ("SessionStart", "session-start.sh"),
    ("SessionStart", "engagement-init.py"),
    ("UserPromptSubmit", "hunt-trigger.py"),
    ("PostToolUse", "recon-capture.py"),
    ("PostToolUse", "tool-telemetry.py"),
    ("PostToolUse", "capture-poc.py"),
    ("PostToolUse", "wiki-reindex.py"),
    ("PreToolUse", "scope-guard.py"),
    ("PreToolUse", "lane-guard.py"),
    ("PreToolUse", "sleep-guard.py"),
    ("PreToolUse", "session-guard.py"),
    ("PreToolUse", "write-guard.py"),
    ("PreToolUse", "drift-guard.py"),
    ("PreToolUse", "eng-ckpt.py"),
    ("PreToolUse", "zg-nudge.py"),
    ("PreToolUse", "tmux-nudge.py"),
    ("PreToolUse", "burp-nudge.py"),
    ("PreToolUse", "big-read.py"),
    ("PreCompact", "pre-compact.sh"),
    ("Stop", "close-out.py"),
    ("Stop", "cost-snap.py"),
]


def default_settings_path():
    return os.path.expanduser("~/.claude/settings.json")


def _event_commands(settings):
    """Yield (event, command) for every registered hook command. Handles both
    registration shapes: ~/.claude/settings.json (hooks -> event -> groups)
    and the committed .zcode/config.json (hooks -> {"events": {event -> groups}}).
    """
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        return
    events = hooks.get("events")
    if not isinstance(events, dict):
        events = hooks  # settings.json shape: hooks maps event -> groups
    for event, groups in events.items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            for hk in group.get("hooks", []):
                if isinstance(hk, dict):
                    cmd = hk.get("command", "")
                    if isinstance(cmd, str):
                        yield event, cmd


def _registered_commands(settings):
    """Yield every hook command string across all events in settings."""
    for _event, cmd in _event_commands(settings):
        yield cmd


def missing_hooks(settings_path=None):
    """Return expected hooks absent from settings.json: fully missing, or
    registered only under the WRONG event. Wrong-event entries are named as
    "base (expected X, registered under Y)" so the fix is actionable. Match is
    by the script basename appearing anywhere in a registered hook command
    string (commands use ~/.claude/vault-hooks/<name> or `python3 ... <name>`).
    Fails open: unreadable/missing settings -> [].
    """
    if settings_path is None:
        settings_path = default_settings_path()
    try:
        with open(settings_path, encoding="utf-8") as f:
            settings = json.load(f)
    except Exception:
        return []  # fail open: cannot assert drift without the file

    found_events = {}  # expected basename -> set of events it is registered under
    for event, cmd in _event_commands(settings):
        for _expected, basename in EXPECTED_HOOKS:
            if basename in cmd:
                found_events.setdefault(basename, set()).add(event)

    problems = []
    for event, basename in EXPECTED_HOOKS:
        found = found_events.get(basename)
        if not found:
            problems.append(basename)
        elif event not in found:
            problems.append("%s (expected %s, registered under %s)"
                            % (basename, event, ", ".join(sorted(found))))
    return problems


def vault_root():
    """Repo root: scripts/check-hooks.py -> its grandparent dir."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def stale_hooks(settings_path=None, hooks_root=None):
    """Return registered vault-hook scripts that no longer exist in skills/hooks.

    The mirror image of missing_hooks(). settings.json is machine-local and the
    installer only ADDS, so a hook DELETED upstream stays registered on every
    already-provisioned device, pointing at a file the next `git pull` removed.
    That is not silent: the hook cannot start, so a PostToolUse entry errors on
    every matching tool call (and a PreToolUse one exits 2, which BLOCKS
    Bash/Write/Edit). Detect by name, not by an EXPECTED list, so a removal
    needs no bookkeeping. Fails open: unreadable settings/hooks dir -> [].
    """
    if settings_path is None:
        settings_path = default_settings_path()
    if hooks_root is None:
        hooks_root = os.path.join(vault_root(), "skills", "hooks")
    try:
        with open(settings_path, encoding="utf-8") as f:
            settings = json.load(f)
        present = set(os.listdir(hooks_root))
    except Exception:
        return []  # fail open: cannot assert drift without both sides

    stale = []
    for cmd in _registered_commands(settings):
        for token in cmd.split():
            name = token.rsplit("/", 1)[-1]
            if "vault-hooks/" in token and name not in present:
                stale.append(name)
    return sorted(set(stale))


def default_skills_dest():
    return os.path.expanduser("~/.claude/skills")


def _vault_skill_names(skills_root):
    """Basenames of every dir under skills_root holding a SKILL.md.

    Mirrors setup/install-skills.sh's `find skills -name SKILL.md` -> the exact
    set that installer symlinks into ~/.claude/skills. os.walk over a missing
    tree yields nothing, so an absent skills/ naturally returns [] (fail open).
    """
    names = set()
    try:
        for dirpath, _dirs, files in os.walk(skills_root):
            if "SKILL.md" in files:
                names.add(os.path.basename(dirpath))
    except Exception:
        return set()
    return names


def missing_skills(skills_root=None, dest=None):
    """Return vault skill names not symlinked into ~/.claude/skills.

    A vault skill is unregistered when the installer has not been re-run since
    it was added: triggers.json routes to it but Skill(<name>) fails. We flag by
    presence-of-name only (os.path.lexists, so a broken symlink still counts as
    'present' - that is a different drift). Fails open: an unreadable skills/
    tree returns [] (cannot assert drift without the source).
    """
    if skills_root is None:
        skills_root = os.path.join(vault_root(), "skills")
    if dest is None:
        dest = default_skills_dest()
    names = _vault_skill_names(skills_root)
    missing = [n for n in names if not os.path.lexists(os.path.join(dest, n))]
    return sorted(missing)


# engagement-init.py self-registers the "engagement-init" telemetry tag
# (_telemetry.hook), so that name is never unregistered drift.
SELF_REGISTERED_TAG = "engagement-init"


def unregistered_scripts(hooks_root=None, config_path=None):
    """Return skills/hooks/*.py|*.sh files registered under NO event in the
    committed .zcode/config.json. WARN-class, not FAIL: an unregistered script
    may be an intentional library, so callers must not flip their exit code on
    it. `_`-prefixed names are shared libraries (imported, never registered);
    engagement-init's self-registered tag is excluded by stem. Fails open:
    unreadable config or hooks dir -> [].
    """
    if hooks_root is None:
        hooks_root = os.path.join(vault_root(), "skills", "hooks")
    if config_path is None:
        config_path = os.path.join(vault_root(), ".zcode", "config.json")
    try:
        with open(config_path, encoding="utf-8") as f:
            settings = json.load(f)
        names = os.listdir(hooks_root)
    except Exception:
        return []  # fail open: cannot assert drift without both sides

    registered = set()
    for _event, cmd in _event_commands(settings):
        for token in cmd.split():
            name = token.rsplit("/", 1)[-1].rstrip('"')
            if name.endswith((".py", ".sh")):
                registered.add(name)

    out = []
    for name in sorted(names):
        if not name.endswith((".py", ".sh")) or name.startswith("_"):
            continue
        if name in registered or os.path.splitext(name)[0] == SELF_REGISTERED_TAG:
            continue
        out.append(name)
    return out


def pycache_audit(roots=None):
    """Delete and return orphaned .pyc files under skills/hooks/ and scripts/:
    bytecode whose source .py no longer sits next to its __pycache__ dir
    (Python's own source-resolution rule for cached bytecode). Stale bytecode
    for deleted sources is safe to drop; the dirs themselves and any .pyc
    whose source still lives are never touched. WARN-class: advisory only.
    """
    if roots is None:
        roots = [os.path.join(vault_root(), "skills", "hooks"),
                 os.path.join(vault_root(), "scripts")]
    deleted = []
    for root in roots:
        for dirpath, _dirs, files in os.walk(root):
            if os.path.basename(dirpath) != "__pycache__":
                continue
            src_dir = os.path.dirname(dirpath)
            for f in files:
                if not f.endswith(".pyc"):
                    continue
                stem = f[:-4].split(".cpython-")[0]
                if not stem or os.path.exists(os.path.join(src_dir, stem + ".py")):
                    continue
                path = os.path.join(dirpath, f)
                try:
                    os.remove(path)
                    deleted.append(path)
                except OSError:
                    pass
    return deleted


def main():
    rc = 0
    miss_h = missing_hooks()
    if miss_h:
        print("Missing or mis-registered vault hooks: " + ", ".join(miss_h))
        print("Run: bash setup/install-hooks.sh")
        rc = 1
    else:
        print("all %d vault hooks registered" % len(EXPECTED_HOOKS))
    stale_h = stale_hooks()
    if stale_h:
        print("Stale vault hooks (script deleted upstream, still registered): "
              + ", ".join(stale_h))
        print("Run: bash setup/install-hooks.sh")
        rc = 1
    miss_s = missing_skills()
    if miss_s:
        print("Unregistered vault skills: " + ", ".join(miss_s))
        print("Run: bash setup/install-skills.sh")
        rc = 1
    else:
        print("all vault skills registered")
    # advisory drift classes below: WARN only, never flip the exit code
    unreg = unregistered_scripts()
    if unreg:
        print("WARN unregistered scripts in skills/hooks/ (intentional library, or "
              "missing .zcode/config.json registration): " + ", ".join(unreg))
    orphans = pycache_audit()
    if orphans:
        print("WARN deleted %d orphaned .pyc (source .py gone): %s"
              % (len(orphans), ", ".join(os.path.basename(p) for p in orphans)))
    print("skill-lint (advisory, never a gate):")
    try:
        # skill-lint.py has a hyphen in its filename, so a plain import can't reach it.
        import importlib.util
        _spec = importlib.util.spec_from_file_location(
            "skill_lint", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "skill-lint.py"))
        skill_lint = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(skill_lint)
        issues = skill_lint.lint_all(vault_root())
        for i in issues[:20]:
            print("  " + i)
        print("  %d issue(s) total" % len(issues) if issues else "  clean")
    except Exception as e:
        print("  skipped: %s" % e)
    return rc


if __name__ == "__main__":
    sys.exit(main())
