# SA5 slice port adapt log (2026-10-17) - source HermesTORCH/skills -> ZTorch/ZTorch/skills, target wsl claude cli

- platform/agents-md-improver: VERIFIED unchanged (diff -r --strip-trailing-cr clean; no Windows-isms)
- platform/caveman: VERIFIED unchanged (diff clean; no Windows-isms)
- platform/graphify: VERIFIED unchanged (diff clean; no Windows-isms)
- platform/obsidian-lint: VERIFIED unchanged (diff clean; VMshare mention in description only, no path)
- platform/ponytail: VERIFIED unchanged (diff clean; `hermes/` in diff-path lists is a no-op git path, not a break)
- platform/ponytail-debt: VERIFIED unchanged (diff clean; no Windows-isms)
- platform/ponytail-review: VERIFIED unchanged (diff clean; `hermes/` in diff-path lists is a no-op git path, not a break)
- platform/wiki: ADAPTED - SKILL.md L28 `export QMD_VAULT="C:/Users/Lenovo/Documents/ObisidianVaults/HermesTORCH"` -> `"/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch"`; L31 `~/.bun/bin/qmd.exe` -> `~/.bun/bin/qmd`, `~/...bun/bin/bun.exe add -g @tobilu/qmd` -> `~/.bun/bin/bun add -g @tobilu/qmd` (WSL bun, no .exe). Incident narrative kept verbatim.
- research/nday: ADAPTED - SKILL.md L29 seat-side `PROJ=C:/Users/Lenovo/Documents/ObisidianVaults/HermesTORCH/raw/research/<project>` -> `/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/raw/research/<project>` (+ comment "(Windows)" -> "(WSL)"); L32 VM-side same HermesTORCH->ZTorch/ZTorch; L43 transport `cd .../HermesTORCH && bash scripts/vm-ssh.sh` -> `cd .../ZTorch/ZTorch && bash scripts/vm-ssh.sh` (kali-linux transport kept as-is); checklist.md L15 seat spelling `C:/.../raw/research/<project>` -> `/mnt/c/.../raw/research/<project>`
- research/research: VERIFIED unchanged (diff clean; wsl kali-linux clone transport already cross-platform)
- research/searchsploit: ADAPTED - SKILL.md L38 `ENG_DIR=C:/Users/Lenovo/Desktop/VMshare/<eng>/<eng>` -> `ENG_DIR=/mnt/c/Users/Lenovo/Desktop/VMshare/<eng>/<eng>` (+ comment "(seat side, Windows" -> "(seat side, WSL"); L41 research-mode PROJ HermesTORCH -> /mnt/c/.../ZTorch/ZTorch/raw/research/<project>; L55 transport `cd .../HermesTORCH && bash scripts/vm-ssh.sh` -> `cd .../ZTorch/ZTorch && bash scripts/vm-ssh.sh`; VM-side /mnt/VMshare kept as-is (kali VM share mount)
- research/wiki-arsenal: VERIFIED unchanged (diff clean; no Windows-isms)
- research/wiki-recon: VERIFIED unchanged (diff clean; no Windows-isms)
- skills/hooks/ (dir extra): VERIFIED whole (diff -r --strip-trailing-cr clean, 23 scripts + __pycache__); grep found no %LOCALAPPDATA%/AppData/hermes/junction/hermes-CLI deps; hooks are claude-cli-wired (.zcode/config.json + ~/.claude/vault-hooks symlink) so none are Hermes-runtime-only -> no inert-hook removals; added hooks/README-ported-2026-10-17.md one-line note (tool-telemetry.py skill_view branch is Hermes-seat normalization, inert/fail-open under claude cli)
- skills-setup.md (extra): VERIFIED exists at skills/skills-setup.md (11312 bytes; per instructions no diff - sourced from old ZTorch skills.bak-20261017)
- Line endings: all edits kept LF (file(1): ASCII text, no CRLF); no style/content rewrites beyond path mechanics
