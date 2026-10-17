# SA3 slice port log - 2026-10-17

Source: C:/Users/Lenovo/Documents/ObisidianVaults/HermesTORCH/skills
Dest: C:/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills
Method: `diff -r --strip-trailing-cr` per skill dir (copy integrity), then grep for
Hermes-GUI-specific mechanics (%LOCALAPPDATA%, AppData/hermes, torch-skills, hermes
CLI, 'Hermes Agent'/'Hermes desktop', MEDID, MEMORY:, VMshare Windows spellings,
browser_exec/browser_vault), then targeted adaptations only.

## Copy integrity (12/12 dirs, 0 missing files)

- verified-unchanged (copy whole, no adaptation needed): surface/browser/chrome-devtools-browser, surface/browser/screenshot, surface/burp/hunt-burp, surface/burp/screenshot-burp, surface/caido, surface/fuzz, surface/vector-workflow, report/disclosure, report/walkthrough
- adapted (copy whole + fixes below): surface/interceptor, surface/js-discover, surface/js-parser

## Line endings

- 13 files across the slice arrived CRLF from the HermesTORCH source; converted all to LF per brief ("keep LF"). Post-conversion `diff -r --strip-trailing-cr` still IDENTICAL for the 9 unchanged skills; remaining diffs are only the intentional adaptations below.

## Adaptations (file | before | after)

- skills/surface/interceptor/SKILL.md (wake-law daemon path; $LOCALAPPDATA unset in wsl bash):
  `INTERCEPTOR_SPIN_WATCHDOG=off "$LOCALAPPDATA/hermes/tools/interceptor/daemon/interceptor-daemon.exe" --standalone`
  -> `INTERCEPTOR_SPIN_WATCHDOG=off /mnt/c/Users/Lenovo/AppData/Local/hermes/tools/interceptor/daemon/interceptor-daemon.exe --standalone`
- skills/surface/interceptor/SKILL.md (wsl cannot resolve bare `powershell`):
  `(powershell Start-Process '<url>')` -> `(powershell.exe Start-Process '<url>')`
- skills/surface/interceptor/SKILL.md (install-state path, seat is now WSL):
  `repo cloned to \`C:/Users/Lenovo/AppData/Local/hermes/tools/interceptor\`` -> `repo cloned to \`/mnt/c/Users/Lenovo/AppData/Local/hermes/tools/interceptor\``
- skills/surface/interceptor/SKILL.md (CLI block: cmd `set`/`%CLI%`/C:/ paths break in wsl bash -> POSIX var + /mnt/c spelling; Windows exes via interop):
  `set CLI=C:/Users/Lenovo/AppData/Local/hermes/tools/interceptor/dist/interceptor` -> `CLI=/mnt/c/Users/Lenovo/AppData/Local/hermes/tools/interceptor/dist/interceptor`
  `export INTERCEPTOR_CONTEXT=$(cat "$LOCALAPPDATA/hermes/tools/interceptor/edge-context.txt")` -> `export INTERCEPTOR_CONTEXT=$(cat /mnt/c/Users/Lenovo/AppData/Local/hermes/tools/interceptor/edge-context.txt)`
  7x `C:/Users/Lenovo/.bun/bin/bun.exe %CLI% <verb>` -> `/mnt/c/Users/Lenovo/.bun/bin/bun.exe "$CLI" <verb>` (status, window new, open, net log, links, act, eval)
- skills/surface/js-discover/SKILL.md (seat-side ENG_DIR; seat is now WSL):
  `# seat side (Windows)` -> `# seat side (WSL)`; `ENG_DIR=C:/Users/Lenovo/Desktop/VMshare/<eng>/<eng>` -> `ENG_DIR=/mnt/c/Users/Lenovo/Desktop/VMshare/<eng>/<eng>`
- skills/surface/js-discover/SKILL.md (prose seat path):
  `the seat sees the same bytes at C:/Users/Lenovo/Desktop/VMshare/<eng>/<eng>` -> `... at /mnt/c/Users/Lenovo/Desktop/VMshare/<eng>/<eng>`
- skills/surface/js-discover/SKILL.md (vm-ssh wrapper pointed at the old HermesTORCH repo):
  `cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults/HermesTORCH && bash scripts/vm-ssh.sh '<command>'` -> `cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch && bash scripts/vm-ssh.sh '<command>'`
- skills/surface/js-discover/SKILL.md (seat-side verify command, wsl spelling):
  `C:/Users/Lenovo/.bun/bin/bun.exe C:/Users/Lenovo/AppData/Local/hermes/tools/interceptor/dist/interceptor status` -> `/mnt/c/Users/Lenovo/.bun/bin/bun.exe /mnt/c/Users/Lenovo/AppData/Local/hermes/tools/interceptor/dist/interceptor status` (note added: Windows-hosted exe via /mnt/c from WSL seat)
- skills/surface/js-discover/SKILL.md (corpus evidence path):
  `C:/Users/Lenovo/Desktop/VMshare/<eng>/<eng>/js/<domain>/raw/interceptor/` -> `/mnt/c/Users/Lenovo/Desktop/VMshare/<eng>/<eng>/js/<domain>/raw/interceptor/`
- skills/surface/js-discover/checklist.md (bare bun.exe unresolvable in wsl):
  `` daemon answers `bun.exe .../dist/interceptor status` `` -> `` daemon answers `/mnt/c/Users/Lenovo/.bun/bin/bun.exe .../dist/interceptor status` ``
- skills/surface/js-discover/checklist.md (stop-condition referenced the old HermesTORCH skill dirs):
  `Nothing written into the skill dirs (C:/Users/Lenovo/Documents/ObisidianVaults/HermesTORCH/skills/surface/js-{discover,parser}/)` -> `... (/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/surface/js-{discover,parser}/)`
- skills/surface/js-parser/SKILL.md (seat-side ENG_DIR):
  `# seat side (Windows)` -> `# seat side (WSL)`; `ENG_DIR=C:/Users/Lenovo/Desktop/VMshare/<eng>/<eng>` -> `ENG_DIR=/mnt/c/Users/Lenovo/Desktop/VMshare/<eng>/<eng>`
- skills/surface/js-parser/SKILL.md (prose seat path):
  `reads the same bytes at C:/Users/Lenovo/Desktop/VMshare/<eng>/<eng>` -> `... at /mnt/c/Users/Lenovo/Desktop/VMshare/<eng>/<eng>`
- skills/surface/js-parser/SKILL.md (patterns-file copy target):
  `cp scripts/jsluice-patterns.json C:/Users/Lenovo/Desktop/VMshare/<eng>/<eng>/js/jsluice-patterns.json` -> `... /mnt/c/Users/Lenovo/Desktop/VMshare/<eng>/<eng>/js/jsluice-patterns.json`

## Reviewed, intentionally NOT changed

- js-discover SKILL.md L243 build-location note + L247 chrome://extensions "Load unpacked" path stay C:/ spelling: those run in Windows-hosted Chrome/tooling, not the WSL seat.
- interceptor SKILL.md L246 "netwatch outfile: full Windows path (C:/...) - bun.exe drops POSIX paths": still correct for the Windows-hosted bun.exe.
- Kali VM references kept as-is: kali-linux distro, vm-ssh.sh transport, user tz, /home/tz/go/bin, VM-side /mnt/VMshare spellings, /mnt/VMshare double-nested layout.
- caido SKILL.md `wsl.exe ... bash -c` gotcha: still valid from a WSL seat (interop).
- No browser_exec/browser_vault/MEDID/MEMORY:/Hermes Agent/Hermes desktop/torch-skills/hermes-CLI references found anywhere in the 12 dirs; nothing to note as N/A beyond the LOCALAPPDATA hermes tool paths converted above.
- walkthrough SKILL.md `powershell` hit is a markdown code-fence language tag, not a command - left alone.

## Counts

- verified (copy confirmed whole): 12
- adapted (files changed): 3 skills / 4 files (interceptor SKILL.md, js-discover SKILL.md, js-discover checklist.md, js-parser SKILL.md); +13 files CRLF->LF
- missing files: 0
