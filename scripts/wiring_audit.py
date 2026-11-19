#!/usr/bin/env python3
"""wiring_audit.py - every playbook class fingerprinted / told / trigger-routed,
or explicitly waived. Task 8 of the claude-red absorption pass.

Inputs (same files check-routing.py validates):
  scripts/playbook.json          classes + fingerprints
  scripts/tells.json             tell rows (class cell)
  skills/exploit/hunt/triggers.json   prompt-routing values
  skills/exploit/hunt/hunt-*/    the skill set

Coverage rules (per the task-8 brief):
  fingerprint: a class is covered when any fingerprint's `skills` list contains
               the class's skill, or the skill name appears in a fingerprint's
               tests text.
  tell:        any tells row whose `class` (canonicalized) equals the class name.
  trigger:     the class's skill appears as a value in any triggers section
               (so a prompt can route to it without model judgment).
"""
import json
import os
import sys

VAULT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

# tell rows use full words where playbook classes abbreviate; canonicalize
# (extend here, not ad-hoc in the matcher, when a new alias appears).
TELL_CLASS_ALIASES = {"deserialization": "deser", "file-upload": "upload"}


class WiringAudit:
    # Classes/skills that legitimately have no static wiring. One line each.
    WAIVED = frozenset({
        # wireless: physical-layer presence (radio, monitor mode); no banner or
        # source tell ever names it - routed by the surface/operator, not regex.
        "wireless",
        # postexp: post-foothold phase by definition; nothing to fingerprint
        # pre-compromise, routed by chains.json pivots and driver moves.
        "postexp",
        # social: targets humans (pretext/phishing); no technical surface to
        # fingerprint or tell on.
        "social",
        # hunt-core: shared methodology core, loaded via Skill(hunt-core) by
        # other hunt skills - never prompt-routed.
        "hunt-core",
        # hunt-ad-* sub-skills: dispatched by Skill(hunt-ad), not prompt-routed.
        "hunt-ad-acl", "hunt-ad-adcs", "hunt-ad-kerberos",
        # hunt-sqli-* / hunt-xss-* sub-variants: dispatched by their parent
        # hunt-sqli / hunt-xss skill mid-hunt, never prompt-routed.
        "hunt-sqli-boolean", "hunt-sqli-error", "hunt-sqli-oob",
        "hunt-sqli-time", "hunt-sqli-union",
        "hunt-xss-blind", "hunt-xss-clobber", "hunt-xss-csp", "hunt-xss-csti",
        "hunt-xss-dom", "hunt-xss-file", "hunt-xss-mxss",
        "hunt-xss-postmessage", "hunt-xss-reflected", "hunt-xss-stored",
    })

    @staticmethod
    def _canonical_tell_class(raw):
        c = (raw or "").strip().lower()
        return TELL_CLASS_ALIASES.get(c, c)

    def __init__(self, repo=VAULT):
        self.repo = repo
        self.playbook = self._load("scripts", "playbook.json")
        tells = self._load("scripts", "tells.json").get("tells", [])
        self.tell_classes = {
            self._canonical_tell_class(t.get("class"))
            for t in tells if isinstance(t, dict)}
        trig = self._load("skills", "exploit", "hunt", "triggers.json")
        self.trigger_targets = set()
        for section in ("triggers", "surface_triggers", "relational_triggers"):
            for val in trig.get(section, {}).values():
                targets = val if isinstance(val, list) else [val]
                self.trigger_targets.update(t for t in targets if isinstance(t, str))
        hunt_dir = os.path.join(repo, "skills", "exploit", "hunt")
        try:
            self.hunt_skills = {d for d in os.listdir(hunt_dir)
                                if d.startswith("hunt-")}
        except OSError:
            self.hunt_skills = set()

    def _load(self, *rel):
        try:
            with open(os.path.join(self.repo, *rel), encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            # fail CLOSED: an unreadable input must never audit to a
            # vacuous "0 unwaived gap(s)" rc 0.
            print("wiring_audit: cannot read %s: %s" % (os.path.join(*rel), e),
                  file=sys.stderr)
            raise SystemExit(2)

    # -- class -> skill -> wiring
    def _classes(self):
        return {c: r.get("skill") for c, r in
                (self.playbook.get("classes") or {}).items()
                if isinstance(r, dict)}

    def _fingerprint_skills(self):
        """Skills named by any fingerprint: via `skills` lists or tests text."""
        fps = self.playbook.get("fingerprints") or {}
        named = set()
        for fp in fps.values():
            if not isinstance(fp, dict):
                continue
            named.update(fp.get("skills") or [])
            blob = " ".join(fp.get("tests") or []).lower()
            named.update(s for s in self.hunt_skills if s.lower() in blob)
        return named

    def classes_without_fingerprint(self):
        named = self._fingerprint_skills()
        return {c for c, sk in self._classes().items() if sk not in named}

    def classes_without_tell(self):
        return {c for c in self._classes() if c not in self.tell_classes}

    def classes_without_trigger(self):
        return {c for c, sk in self._classes().items()
                if sk not in self.trigger_targets}

    def skills_without_trigger(self):
        return {s for s in self.hunt_skills if s not in self.trigger_targets}

    def failures(self):
        return {
            "fingerprint": self.classes_without_fingerprint(),
            "tell": self.classes_without_tell(),
            "trigger": self.classes_without_trigger(),
            "skill-trigger": self.skills_without_trigger(),
        }

    def unwaived(self):
        return {k: v - set(self.WAIVED) for k, v in self.failures().items()}

    def report(self):
        rows = ["| class | fingerprint | tell | trigger |",
                "|---|---|---|---|"]
        fps = self._fingerprint_skills()
        for c, sk in sorted(self._classes().items()):
            rows.append("| %s | %s | %s | %s |" % (
                c,
                "y" if sk in fps else ("waived" if c in self.WAIVED else "MISSING"),
                "y" if c in self.tell_classes else ("waived" if c in self.WAIVED else "MISSING"),
                "y" if sk in self.trigger_targets else "-"))
        return "\n".join(rows)


def _self_check():
    a = WiringAudit.__new__(WiringAudit)
    a.repo, a.playbook = "/nonexistent", {}
    a.tell_classes, a.trigger_targets, a.hunt_skills = set(), set(), set()
    assert a.classes_without_fingerprint() == set()
    assert a.classes_without_tell() == set()
    a.playbook = {"classes": {"xss": {"skill": "hunt-xss"}}}
    a.hunt_skills = {"hunt-xss"}
    assert a.classes_without_fingerprint() == {"xss"}
    a.playbook = {"classes": {"xss": {"skill": "hunt-xss"}},
                  "fingerprints": {"k": {"skills": ["hunt-xss"]}}}
    assert a.classes_without_fingerprint() == set()
    a.tell_classes = {WiringAudit._canonical_tell_class("deserialization")}
    a.playbook["classes"]["deser"] = {"skill": "hunt-deserialization"}
    a.hunt_skills.add("hunt-deserialization")
    assert a.classes_without_tell() == {"xss"}
    assert WiringAudit.WAIVED >= {"wireless", "postexp", "social"}
    print("self-check ok")


def main(argv):
    if "--self-check" in argv:
        _self_check()
        return 0
    audit = WiringAudit()
    if "--report" in argv:
        print(audit.report())
        print()
    bad = audit.unwaived()
    for kind, missing in bad.items():
        if missing:
            print("no %s wiring: %s" % (kind, ", ".join(sorted(missing))))
    print("wiring_audit: %d unwaived gap(s)" % sum(len(v) for v in bad.values()))
    return 1 if any(bad.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
