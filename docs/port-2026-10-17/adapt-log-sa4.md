# SA4 port adapt log - workflow + orchestrate slice (14 skills)

Date: 2026-10-17
Source: C:/Users/Lenovo/Documents/ObisidianVaults/HermesTORCH/skills
Dest:   C:/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills
Slice:  workflow/{bb-workflow, closeout/engagement-retro, closeout/evidence, closeout/learn,
        closeout/triage, ctf/ctf-box, ctf/ctf-category, nightmare, recon/ingest,
        recon/research-ingest} + orchestrate/{brain, engage, kali-seat, offensive}

Copy verification: diff -r --strip-trailing-cr source vs dest.
- 12 of 13 HermesTORCH-sourced skills: IDENTICAL, 0 missing files.
- workflow/bb-workflow: copy was TRUNCATED - dest was missing 14 lines (2 bullets:
  "SERIALIZE LANES ON SHARED STATEFUL RESOURCES" + "BIND LANE OUTPUT PATHS ABSOLUTELY").
  REPAIRED from source; post-repair content delta vs source is the intended adaptation only.
- workflow/closeout/learn: sourced from skills.bak-20261017 (not HermesTORCH, not diffed
  against it). VERIFIED intact: present, 310 lines, DEPRECATED banner + wiki stage/promote
  mechanics reference complete. Unchanged.

Adaptations applied (wsl claude cli seat):
1. CRLF -> LF on every CRLF file in the slice (14 files; repo .gitattributes eol=lf,
   same rule as SA1). engagement-retro + learn were already LF.
2. Seat-side VMshare paths: C:/Users/Lenovo/Desktop/VMshare -> /mnt/c/Users/Lenovo/Desktop/VMshare.
3. REPO anchor repointed to the wsl working tree: HermesTORCH -> ZTorch (/mnt/c form).
4. Hermes GUI-only mechanics (%LOCALAPPDATA%/hermes/config.yaml, ~/.hermes/skills profile,
   torch-skills DESKTOP junctions, Hermes memory/session_search tools) annotated as
   legacy-GUI-seat-only with the wsl claude cli equivalent; Kali VM aliases
   (kali-vm, vm-ssh.sh, tz@192.168.23.128) kept as-is everywhere.

Per-skill:

## workflow/bb-workflow
- bb-workflow/SKILL.md: ADAPTED
  - before: 14 bullets missing (truncated copy, dest ended after "...doesn't manage subagents itself.")
    after:  both bullets restored verbatim from HermesTORCH source (lines 149-162 there).
  - before: '# seat side (Windows) - engagement tree is DOUBLE-NESTED in VMshare:'
    after:  '# seat side (WSL via /mnt/c; ported 2026-10-17) - engagement tree is\n# DOUBLE-NESTED in VMshare:'
  - before: 'ENG_DIR=C:/Users/Lenovo/Desktop/VMshare/<eng>/<eng>'
    after:  'ENG_DIR=/mnt/c/Users/Lenovo/Desktop/VMshare/<eng>/<eng>'
  - before: '# VM side (same tree through the VMware share):'
    after:  '# Kali VM side (same tree through the VMware share):'
  - before/after endings: CRLF -> LF (whole file)
  - VM-side 'ENG_DIR=/mnt/VMshare/<eng>/<eng>' kept as-is.

## workflow/closeout/engagement-retro
- engagement-retro/SKILL.md: ADAPTED
  - before: '# seat side (Windows) - engagement tree is DOUBLE-NESTED in VMshare:'
    after:  '# seat side (WSL via /mnt/c; ported 2026-10-17) - engagement tree is\n# DOUBLE-NESTED in VMshare:'
  - before: 'ENG_DIR=C:/Users/Lenovo/Desktop/VMshare/<eng>/<eng>'
    after:  'ENG_DIR=/mnt/c/Users/Lenovo/Desktop/VMshare/<eng>/<eng>'
  - before: 'REPO=C:/Users/Lenovo/Documents/ObisidianVaults/HermesTORCH'
    after:  'REPO=/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch'
    (repo ledgers session/retro-log.md etc. must land in the wsl working tree; ZTorch/session/ exists)
  - before: '| Hermes `memory` tool (one declarative entry) |'
    after:  '| `memory` tool (Hermes GUI seat; wsl claude cli: project memory/CLAUDE.md) - one declarative entry |'
  - before: '| Hermes `session_search` |'
    after:  '| `session_search` (Hermes GUI seat; wsl claude cli: transcript/session recall) |'

## workflow/closeout/evidence
- evidence/SKILL.md: VERIFIED-UNCHANGED
  - Only hit is prose "VMshare mirror of the same engagement" (no Windows path) - non-breaking.
  - Endings CRLF -> LF only.

## workflow/closeout/learn
- learn/SKILL.md: VERIFIED-INTACT (skills.bak-20261017 provenance; not diffed vs HermesTORCH
  per directive). 310 lines, deprecated-on-Hermes banner + stage/promote mechanics whole.
  Its Hermes memory/session_search mentions are descriptive of WHY deprecated - left as-is.
  Already LF; zero changes.

## workflow/closeout/triage
- triage/SKILL.md: VERIFIED-UNCHANGED
  - Only hit: prose citation "HermesTORCH docs/hackbot-port.md 2.1" (no full Windows path,
    not operational) - left as-is.
  - Endings CRLF -> LF only.

## workflow/ctf/ctf-box
- ctf-box/SKILL.md: VERIFIED-UNCHANGED
  - Grep hit "recalling an exploit from memory:" was a MEMORY:-pattern false positive (LLM
    recall, not a memory tool ref). Endings CRLF -> LF only.

## workflow/ctf/ctf-category
- ctf-category/SKILL.md: VERIFIED-UNCHANGED (0 grep hits). Endings CRLF -> LF only.

## workflow/nightmare
- nightmare/SKILL.md: VERIFIED-UNCHANGED (0 grep hits). Endings CRLF -> LF only.

## workflow/recon/ingest
- ingest/SKILL.md: VERIFIED-UNCHANGED (0 grep hits). Endings CRLF -> LF only.

## workflow/recon/research-ingest
- research-ingest/SKILL.md: VERIFIED-UNCHANGED (0 grep hits). Endings CRLF -> LF only.

## orchestrate/brain
- brain/SKILL.md: VERIFIED-UNCHANGED (0 grep hits; "Agent tool aliases" tier-routing table is
  already generic). Endings CRLF -> LF only.

## orchestrate/engage
- engage/SKILL.md: VERIFIED-UNCHANGED (0 grep hits). Endings CRLF -> LF only.

## orchestrate/kali-seat
- kali-seat/SKILL.md: ADAPTED
  - Added port note under "## Seat map (this machine)": ACTIVE seat = wsl claude cli on
    /mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch; "Hermes seat" rows = legacy
    reference; Windows paths -> /mnt/c equivalents; Kali VM aliases unchanged.
  - Vault-paths table:
    before: '| Windows | `C:\Users\Lenovo\Documents\ObisidianVaults\HermesTORCH` | PRIMARY workspace ... |'
    after:  '| Windows (Hermes GUI, legacy) | same path | legacy desktop-app seat tree - reference only (pre-2026-10-17 primary) |'
    before: '| WSL | `/mnt/c/Users/Lenovo/Documents/ObisidianVaults/HermesTORCH` | native script runs in WSL ... |'
    after:  '| WSL (ACTIVE seat) | `/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch` | PRIMARY workspace - wsl claude cli repo (hunt skills + wiki + scripts); native script runs in WSL (vm-ssh.sh transport) |'
    before: '| Donor | `C:\Users\Lenovo\Documents\ObisidianVaults\ZTorch\ZTorch` | FROZEN upstream/history reference only - owns git-ignored targets/ client data; never edited |'
    after:  '| Donor | `/mnt/c/Users/Lenovo/Documents/ObisidianVaults/HermesTORCH` | FROZEN upstream/history reference only - legacy skills source; never edited |'
  - before: 'registered in `%LOCALAPPDATA%/hermes/config.yaml`): out-of-scope ...'
    after:  'registered in `%LOCALAPPDATA%/hermes/config.yaml` (legacy Hermes GUI seat; under the wsl claude cli seat hooks register in the repo/claude settings and this file does not exist)): out-of-scope ...'
  - Endings CRLF -> LF only.

## orchestrate/offensive
- offensive/SKILL.md: ADAPTED
  - G2 condition 3 (DESKTOP junction) annotated:
    before: '...junctions every `skills/*/*/SKILL.md` directory).'
    after:  '...junctions every `skills/*/*/SKILL.md` directory). Legacy Hermes GUI seat only - under the wsl claude cli seat, skills load straight from the repo ring, no junction exists or is needed; G2 condition 3 is N/A there and telemetry gate stays advisory.'
- offensive/scripts/junction-sweep.ps1: VERIFIED-UNCHANGED (content). Windows-seat-only
  tooling (NTFS junctions + $repo HermesTORCH path); converting to /mnt/c would break it on
  the seat where it actually runs. SKILL.md note above marks it GUI-seat-only.
- offensive/templates/lane-agent-context.md: VERIFIED-UNCHANGED (<REPO>/<ENG_DIR_SEAT> are
  fill-at-dispatch placeholders). Endings CRLF -> LF only.

offensive.py check: ZTorch/scripts/offensive.py contains NO Windows paths, no ENG_DIR
literal, no %LOCALAPPDATA% (verified by grep) - nothing to adapt there.

Totals: 14 skills in slice -> 4 adapted (bb-workflow, engagement-retro, kali-seat, offensive),
10 verified unchanged/intact, 0 missing files. 1 truncation repaired (bb-workflow).
