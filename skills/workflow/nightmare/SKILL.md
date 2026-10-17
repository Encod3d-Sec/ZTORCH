---
name: nightmare
description: Recompiled Windows LPE arsenal (Nightmare_Eclipse PoCs, Defender verdicts recorded) for CTF/lab privesc. Use when a standard-user Windows foothold needs a kernel/LPE shortcut on a CTF box.
metadata:
  hermes:
    tags: [lpe, windows, poc-picker]
    related_skills: [ctf-box, hunt-windows]
---

# Nightmare Arsenal (Windows LPE, CTF)

Reworked (hash-changed, cross-compiled) Windows LPE PoCs from Nightmare_Eclipse
(git.churchofmalware.org; upstream clones read-only at `raw/git/`). Binaries +
verdicts live in the PRIVATE repo `github.com/Encod3d-Sec/Nightmare`; build
recipes in its BUILD.md. Authorized CTF/lab targets ONLY.

**Hub:** [[privesc-exploit-arsenal]] (Windows table, nightmare row) ? routed from Skill(hunt-windows).

## Wiki

Hub: [[exploit-dev-moc]] - Primary page: [[windows-privesc]]
**REFS:** [[windows-privesc]]

## Gate

- Confirm target authorization (scope.md for engagements; CTF box rules otherwise).
- These are LOCAL privilege escalations: you need an interactive session of a
  standard user. Admin one-shots (wmiexec/schtasks) can test Defender verdicts
  but CANNOT validate the LPE itself. RDP 3389 or console access required.

## Triage: pick the PoC by target build

| PoC | Bug | Fire when | Caution |
|---|---|---|---|
| mini-plasma | CVE-2020-17103 cldflt placeholder hydration race | Any build per author; TURNKEY SYSTEM shell | Race: variable, record run counts. Needs .NET 4.8 + the 2 loose DLLs pushed together |
| red-sun | Defender cloud-tag rewrite-to-origin overwrite | Defender + cloud protection ON; overwrites System32\TieringEngineService.exe | Turnkey but disruptive (kills/replace a Defender-managed binary) |
| green-plasma | ctfmon BaseNamedObjects session-cache section | Win11/2022/2026 (author unsure re Win10) | Creates privileged section only; chain to SYSTEM is Phase 2 dev work |
| legacy-hive | User Profile Service arbitrary hive load | All builds supported at Jul 2026 patches | Needs creds of a 2nd standard user + a 3rd (admin) username |
| blue-hammer | Defender RPC MpUpdateEngineSignature path abuse | Defender-managed hosts | Author admits bugs; verify-first, treat as reference build |

Pick ONE, highest-fits-first: mini-plasma > red-sun > legacy-hive > green-plasma > blue-hammer.

## Workflow

1. **Pull the arsenal** (Kali): clone `git@github.com:Encod3d-Sec/Nightmare.git`
   into the engagement working dir. Read the PoC's VERDICT.md: verdicts are
   PER-BUILD, a different target build means the binary is unproven, not bad.
2. **Record the build**: `cmd /c ver` + DisplayVersion (repo tools/nm.sh build).
3. **Defender status**: tools/nm.sh mpstatus. If cloud protection is OFF,
   red-sun is out.
4. **Throwaway standard user** (admin): tools/nm.sh user HOST ADMIN PASS nmtest <pass>.
5. **Push** binaries via tools/nm.sh push (lands C:\ProgramData).
6. **Run in the nmtest interactive session** (RDP in as nmtest via xfreerdp if
   3389 open). One named tmux window per action.
7. **Verdicts x2**: 0 min and +10 min (tools/nm.sh threats) - cloud verdicts
   flip late. Full protocol: repo tools/TEST-PROTOCOL.md.
8. **Record**: write VERDICT.md per the template, commit + push to the private
   repo. Binaries land in the repo WITH their verdicts; an untested build
   ships as verdict PENDING, never silently.

## Failure handling

- PoC runs, no SYSTEM: race PoC -> retry up to 3, count runs, then move on
  (stop condition). Stripped PoC (green-plasma/legacy-hive) -> expected, they
  are Phase 2; fall back to the standard winpeas misconfig sweep
  (Skill(hunt-windows)).
- Defender flags it: note the threat name in VERDICT.md. Do NOT iterate
  obfuscation on the target; rebuild variants are Phase 2 work in the repo.

## Boundaries

- NEVER run against out-of-scope or production hosts. PreToolUse scope guard applies.
- Repo is PRIVATE by design; never push it public, never embed binaries in the wiki.
- Wiki keeps technique notes only (no binaries); client specifics stay under targets/<eng>/.

## False Positives

- PoC runs clean but the box kernel is outside the PoC's tested range
  (verdict PROBABLY-NOT, not a failed run - record the kernel delta).
- PoC "succeeds" in a container sharing the host kernel (kernel patch
  level is the HOST's - verify against the target's own uname).
- Compile succeeds, exploit hangs on patchguard/EDR - that is a
  BLOCKED verdict with the observed tell, never a silent drop.
