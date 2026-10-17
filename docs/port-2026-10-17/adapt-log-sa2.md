# Port adaptation log — SA2 slice (exploit/hunt + exploit/exec)

Date: 2026-10-17. Source: HermesTORCH/skills -> Dest: ZTorch/ZTorch/skills (wsl claude cli target).
Adaptation rule: seat-side `C:/Users/Lenovo/Desktop/VMshare` -> `/mnt/c/Users/Lenovo/Desktop/VMshare`. VM spelling `/mnt/VMshare` and kali-vm aliases kept as-is. Target-side `C:\` paths in hunt-windows (victim privesc cmds) untouched. LF endings preserved throughout (verified: 0 CRLF files).

| Skill | Copy | Adapted files | Change (before -> after) |
|---|---|---|---|
| hunt/hunt-pwn | clean | SKILL.md, checklist.md | `ENG_DIR=C:/Users/Lenovo/Desktop/VMshare/<eng>/<eng>` -> `ENG_DIR=/mnt/c/Users/Lenovo/Desktop/VMshare/<eng>/<eng>` (x2 files, 4 lines) |
| hunt/hunt-rce | clean | SKILL.md, checklist.md | same ENG_DIR conversion (3 lines SKILL.md incl. prose "the C:/... spelling" -> "the /mnt/c/... spelling", 1 line checklist) |
| hunt/hunt-secrets | clean | SKILL.md, checklist.md | same ENG_DIR conversion (3+1 lines) |
| hunt/hunt-smuggling | clean | SKILL.md, checklist.md | same ENG_DIR conversion (3+1 lines) |
| hunt/hunt-sqli | clean | SKILL.md, checklist.md | same ENG_DIR conversion (3+1 lines) |
| hunt/hunt-sqli-boolean | clean | SKILL.md | `ENG_DIR=C:/Users/...` -> `ENG_DIR=/mnt/c/Users/...` (1 line) |
| hunt/hunt-sqli-error | clean | SKILL.md | same (1 line) |
| hunt/hunt-sqli-oob | clean | SKILL.md | same (1 line) |
| hunt/hunt-sqli-time | clean | SKILL.md | same (1 line) |
| hunt/hunt-sqli-union | clean | SKILL.md | same (1 line) |
| hunt/hunt-ssrf | clean | SKILL.md, checklist.md | same ENG_DIR conversion (3+1 lines) |
| hunt/hunt-upload | STALE-RESYNCED | SKILL.md, checklist.md | ENG_DIR conversion (3+1 lines); PLUS dest SKILL.md was missing 22-line "Cloud/object-storage uploads (S3 presigned URLs)" section present in updated source — resynced from source (with path conversion applied), section verified present (X-Amz-Signature grep hit), only intended path diffs remain |
| hunt/hunt-vpn | clean | SKILL.md, checklist.md | same ENG_DIR conversion (3+1 lines) |
| hunt/hunt-windows | clean | SKILL.md, checklist.md | seat ENG_DIR conversion (2+1 lines); victim-side `C:\Windows\Tasks` / accesschk `C:\` commands intentionally NOT changed |
| hunt/hunt-xss | clean | SKILL.md, checklist.md | same ENG_DIR conversion (3+1 lines) |
| hunt/hunt-xss-blind | clean | SKILL.md, checklist.md | same ENG_DIR conversion (2+1 lines) |
| hunt/hunt-xss-dom | clean | SKILL.md | same (1 line) |
| hunt/hunt-xss-reflected | clean | SKILL.md | same (1 line) |
| hunt/hunt-xss-stored | clean | SKILL.md | same (1 line) |
| exec/delegate | clean | (none) | verified-unchanged: no Windows/Hermes-GUI mechanics found |
| exec/metasploit | clean | SKILL.md | `ENG_DIR=C:/Users/...` -> `ENG_DIR=/mnt/c/Users/...` (1 line) |
| exec/redteamlead | clean | (none) | verified-unchanged: no Windows/Hermes-GUI mechanics found |

Sweep findings across all 22 dirs: zero hits for %LOCALAPPDATA%, AppData/hermes, torch-skills junctions, `hermes vault`/hermes-agent CLI, "Hermes Agent"/"Hermes desktop", MEDID, MEMORY: tool refs. Only the seat-side VMshare path pattern required adaptation (39 lines converted across 31 files).

Totals: 22 dirs verified (diff -r --strip-trailing-cr vs source), 20 dirs adapted (31 files, 39 line conversions), 2 dirs verified-unchanged (delegate, redteamlead), 0 files missing. 1 stale-copy incident (hunt-upload/SKILL.md) resolved by resync.
