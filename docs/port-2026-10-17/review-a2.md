# Review A2 - dependency-existence audit (81 SKILL.md + 44 checklist.md)

Summary:
- 46 findings: 36 BROKEN, 8 INTENTIONAL, 2 UNCLEAR.
- Biggest risk: 20 skills still carry the donor-seat transport (`cd .../HermesTORCH`), so every hunt lane in those classes executes the FROZEN donor repo's `scripts/vm-ssh.sh` instead of the active ZTorch repo.
- Second cluster: donor-only helper scripts the port did not carry (ponytail-debt.py, obsidian-lint.py, phases.json, vm-bridge.sh, scope-sync.sh, interceptor-automation.sh, interceptor-cdp.sh, jsluice-patterns.json) plus the deleted vendored `caido-mode` dir (seed confirmed).
- Wiki corpus is healthy: 245 unique wikilinks resolve except one (`evidence-capture`); every `--target-page` distill path exists except `techniques/network/vpn-appliances.md`; all `Skill(<name>)` cross-refs resolve to a `skills/**/<name>/SKILL.md` dir.
- Seed checks: `skills/surface/caido/SKILL.md` caido-mode refs BROKEN-fix-elsewhere as predicted; `docs/skill-map.md` line 70 helper `scripts/caido.sh` EXISTS (not broken) but the same line's "caido-mode SDK CLI vendored" claim is stale.

All 125 files were read end-to-end; grep was used only to locate and line-number refs. No fixes applied.

| File | Line | Class | Evidence | Proposed fix |
|---|---|---|---|---|
| skills/surface/caido/SKILL.md | 17 | BROKEN | `1. **caido-mode CLI** (primary API surface): vendored at `skills/surface/caido/caido-mode/`` - dir absent from skills/surface/caido/ (only SKILL.md there); also referenced at line 90 | Restore the vendored caido-mode dir (separate restore task, as seeded) |
| skills/surface/caido/SKILL.md | 49 | BROKEN | `cd skills/surface/caido/caido-mode && npm install     # node_modules is gitignored; node 22 works` | Same restore as above; line is dead until the dir lands |
| skills/surface/caido/SKILL.md | 129 | BROKEN | `Run from `skills/surface/caido/caido-mode/`; `npx tsx caido-client.ts <cmd>` below.` | Same restore as above |
| docs/skill-map.md | 70 | BROKEN | `caido/` (headless Caido driver; caido-mode SDK CLI vendored + helper `scripts/caido.sh`)` - helper `scripts/caido.sh` EXISTS (seed resolves), but "vendored" is false today | After the caido-mode restore this line is true again; until then drop or annotate "vendored" |
| skills/platform/ponytail/SKILL.md | 55 | BROKEN | `python3 scripts/ponytail-debt.py` lists every marker` - no such file in scripts/ | Port `scripts/ponytail-debt.py` from the donor vault or point at the installed plugin's sweep |
| skills/platform/ponytail-debt/SKILL.md | 19 | BROKEN | `python3 scripts/ponytail-debt.py` (also line 27 with `--stamp`) - script absent from scripts/ | Same port as above |
| skills/platform/obsidian-lint/SKILL.md | 3 | BROKEN | description: `...run scripts/obsidian-lint.py to catch mangled text...` (also line 28: `python3 scripts/obsidian-lint.py targets/<eng>`) - no such file in scripts/ | Port `scripts/obsidian-lint.py` from the donor vault |
| skills/orchestrate/offensive/SKILL.md | 35 | BROKEN | `phase` (predefined phase chain + current phase, from scripts/phases.json - advisory)` - scripts/phases.json absent | Port phases.json or correct the line to wherever the chain now lives |
| skills/orchestrate/kali-seat/SKILL.md | 122 | BROKEN | `the way `scripts/vm-ssh.sh` and `scripts/vm-bridge.sh` do` - scripts/vm-bridge.sh absent (also lines 125 and 130) | Port vm-bridge.sh or rewrite the three refs to the surviving bridge (`scripts/win-vm.sh`) |
| skills/orchestrate/kali-seat/SKILL.md | 130 | BROKEN | `drive the VM directly with `scripts/vm-bridge.sh '<cmd>'` (same base64 law).` | Same as above |
| skills/orchestrate/kali-seat/SKILL.md | 162 | BROKEN | `push `bash scripts/scope-sync.sh` (or the documented vm-ssh + sudo -S route...)` - scripts/scope-sync.sh absent | Port scope-sync.sh or point the line at `scripts/burp/burp-scope-sync.py`'s sibling if one exists donor-side |
| skills/surface/interceptor/SKILL.md | 78 | BROKEN | `ONE COMMAND: `bash scripts/interceptor-automation.sh up|down|status|context` (repo scripts/)` (also line 222) - script absent from scripts/ | Port interceptor-automation.sh from the donor repo scripts/ |
| skills/surface/interceptor/SKILL.md | 195 | BROKEN | `INTERCEPTOR_PAGE=<id> bash scripts/interceptor-cdp.sh eval '<js>'` (also lines 224, 226, 229, 249, 276) - script absent from scripts/ | Port interceptor-cdp.sh from the donor repo scripts/ |
| skills/surface/interceptor/SKILL.md | 157 | BROKEN | `(deferred - see design-scope-shim.md OPEN QUESTIONS Q1)` - no design-scope-shim.md anywhere in the repo | Port docs/design-scope-shim.md or drop the citation |
| skills/surface/js-parser/SKILL.md | 217 | BROKEN | `the patterns file is the K12 contract - repo scripts/jsluice-patterns.json is canonical` (also line 219 `cp scripts/jsluice-patterns.json ...`) - file absent from scripts/ | Port scripts/jsluice-patterns.json from the donor repo (secrets pass A0 depends on it) |
| skills/surface/browser/screenshot/SKILL.md | 22 | BROKEN | `Hub: [[moc]] - Primary page: [[evidence-capture]]` (also line 24 `**REFS:** [[evidence-capture]]`) - no wiki page named evidence-capture exists anywhere under wiki/ | Restore/rename the donor wiki page (wiki graph + hunt-core tier-1 lookup read this block) |
| skills/exploit/hunt/hunt-vpn/SKILL.md | 208 | BROKEN | `--target-page techniques/network/vpn-appliances.md` (also line 247) - wiki/techniques/network/vpn-appliances.md absent (network/ has 17 pages, none by that name) | Scaffold wiki/techniques/network/vpn-appliances.md or repoint to an existing network page |
| skills/exploit/exec/metasploit/SKILL.md | 43 | BROKEN | `wsl.exe -d kali-linux -u root bash -c "cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults/HermesTORCH && bash scripts/vm-ssh.sh '<command>'"` - drives the frozen donor repo, not the active ZTorch repo (60+ sibling skills use the ZTorch path) | Replace `HermesTORCH` with `ZTorch/ZTorch` in the cd path |
| skills/exploit/hunt/hunt-pwn/SKILL.md | 37 | BROKEN | same donor cd line as metasploit:43 (block header also still says `# seat side (Windows)`) | Replace `HermesTORCH` with `ZTorch/ZTorch` |
| skills/exploit/hunt/hunt-rce/SKILL.md | 61 | BROKEN | same donor cd line | Replace `HermesTORCH` with `ZTorch/ZTorch` |
| skills/exploit/hunt/hunt-secrets/SKILL.md | 59 | BROKEN | same donor cd line | Replace `HermesTORCH` with `ZTorch/ZTorch` |
| skills/exploit/hunt/hunt-smuggling/SKILL.md | 60 | BROKEN | same donor cd line | Replace `HermesTORCH` with `ZTorch/ZTorch` |
| skills/exploit/hunt/hunt-sqli/SKILL.md | 55 | BROKEN | same donor cd line | Replace `HermesTORCH` with `ZTorch/ZTorch` |
| skills/exploit/hunt/hunt-sqli-boolean/SKILL.md | 47 | BROKEN | same donor cd line | Replace `HermesTORCH` with `ZTorch/ZTorch` |
| skills/exploit/hunt/hunt-sqli-error/SKILL.md | 47 | BROKEN | same donor cd line | Replace `HermesTORCH` with `ZTorch/ZTorch` |
| skills/exploit/hunt/hunt-sqli-oob/SKILL.md | 50 | BROKEN | same donor cd line | Replace `HermesTORCH` with `ZTorch/ZTorch` |
| skills/exploit/hunt/hunt-sqli-time/SKILL.md | 46 | BROKEN | same donor cd line | Replace `HermesTORCH` with `ZTorch/ZTorch` |
| skills/exploit/hunt/hunt-sqli-union/SKILL.md | 45 | BROKEN | same donor cd line | Replace `HermesTORCH` with `ZTorch/ZTorch` |
| skills/exploit/hunt/hunt-ssrf/SKILL.md | 57 | BROKEN | same donor cd line | Replace `HermesTORCH` with `ZTorch/ZTorch` |
| skills/exploit/hunt/hunt-upload/SKILL.md | 57 | BROKEN | same donor cd line | Replace `HermesTORCH` with `ZTorch/ZTorch` |
| skills/exploit/hunt/hunt-vpn/SKILL.md | 46 | BROKEN | same donor cd line | Replace `HermesTORCH` with `ZTorch/ZTorch` |
| skills/exploit/hunt/hunt-windows/SKILL.md | 43 | BROKEN | `root bash -c "cd /mnt/c/.../HermesTORCH && bash scripts/vm-ssh.sh` - abbreviated donor spelling, same defect | Replace with the full ZTorch path (match the sibling skills' exact line) |
| skills/exploit/hunt/hunt-xss/SKILL.md | 58 | BROKEN | same donor cd line | Replace `HermesTORCH` with `ZTorch/ZTorch` |
| skills/exploit/hunt/hunt-xss-blind/SKILL.md | 46 | BROKEN | same donor cd line | Replace `HermesTORCH` with `ZTorch/ZTorch` |
| skills/exploit/hunt/hunt-xss-dom/SKILL.md | 47 | BROKEN | same donor cd line | Replace `HermesTORCH` with `ZTorch/ZTorch` |
| skills/exploit/hunt/hunt-xss-reflected/SKILL.md | 47 | BROKEN | same donor cd line | Replace `HermesTORCH` with `ZTorch/ZTorch` |
| skills/exploit/hunt/hunt-xss-stored/SKILL.md | 49 | BROKEN | same donor cd line | Replace `HermesTORCH` with `ZTorch/ZTorch` |
| skills/orchestrate/offensive/SKILL.md | 175 | INTENTIONAL | `%LOCALAPPDATA%/hermes/torch-skills/<name>` desktop-junction G2 condition - explicitly annotated: `Legacy Hermes GUI seat only - under the wsl claude cli seat, skills load straight from the repo ring, no junction exists or is needed` | Keep |
| skills/orchestrate/kali-seat/SKILL.md | 37 | INTENTIONAL | `C:\Users\Lenovo\Documents\ObisidianVaults\HermesTORCH` - seat-map row labelled `legacy desktop-app seat tree - reference only` | Keep |
| skills/orchestrate/kali-seat/SKILL.md | 179 | INTENTIONAL | `hermes/agent-hooks/torch-hook-adapter.py`, registered in `%LOCALAPPDATA%/hermes/config.yaml` (legacy Hermes GUI seat; under the wsl claude cli seat hooks register in the repo/claude settings and this file does not exist)` - self-annotated legacy | Keep |
| skills/workflow/closeout/triage/SKILL.md | 163 | INTENTIONAL | `Independent-industry corroboration (Armada talk, HermesTORCH docs/hackbot-port.md 2.1):` - provenance citation naming the donor doc; not an invoked dependency | Keep (optionally note the doc lives in the donor vault) |
| skills/exploit/hunt/ (template) | n/a | INTENTIONAL | `ENG_DIR=/mnt/c/Users/Lenovo/Desktop/VMshare/<eng>/<eng>` + `/mnt/VMshare/<eng>/<eng>` double-nested engagement tree - VM-side mirror path, present in every hunt skill's Paths block | Keep (VM-side external by design) |
| skills/exploit/hunt/ (template) | n/a | INTENTIONAL | `/opt/scope-shim/bin/{curl,httpx}` - VM-side scope-shim absolute paths in every hunt Transport block | Keep (VM-side external) |
| skills/surface/interceptor/SKILL.md | 43 | INTENTIONAL | `/mnt/c/Users/Lenovo/AppData/Local/hermes/tools/interceptor/daemon/interceptor-daemon.exe` + `/mnt/c/Users/Lenovo/.bun/bin/bun.exe` (also lines 161, 186-194; js-discover 250) - Windows-hosted tool tree the skill documents as external (`Windows-hosted exe: call via /mnt/c spelling from the WSL seat`) | Keep (INTENTIONAL-external) |
| skills/workflow/ctf/ctf-box/SKILL.md | 35 | INTENTIONAL | `check `/opt/arsenal` first for pspy/linpeas/shot/capture` + `/root/vm.sh` throughout - VM/WSL-side tooling homes | Keep (VM-side external) |
| skills/platform/ponytail/SKILL.md | 4 | UNCLEAR | `(scripts/, skills/, hermes/, setup/)` - hermes/ dir does not exist in this repo (donor framework dir); ponytail-review lines 15/20 `git diff -- scripts/ skills/ hermes/ setup/` likewise. Harmless (diff still runs, empty pathspec) but a donor leftover | Drop the `hermes/` token from both scope lists, or restore the dir if a Torchv2 hermes/ tree is planned |
| skills/surface/interceptor/SKILL.md | 168 | UNCLEAR | `export the full diff to `setup/interceptor/local-patches.patch` in the main repo` - on-demand export target, currently absent; if the donor tool tree holds local patches, the recovery copy was not ported | Verify donor setup/interceptor/local-patches.patch and copy it during the interceptor restore |

Verification notes (checked, clean):
- All `Skill(<name>)` references across the 125 files resolve to an existing `skills/**/<name>/SKILL.md` directory (the only regex hits that did not were literal placeholders `Skill(...)` / `Skill(x)` in prose).
- 243 of 245 unique `[[wikilink]]` targets resolve by path or unique basename; the two non-page strings ([[target]] in graphify's syntax docs, [[page]]/[[wikilink]] placeholders in learn) are prose examples, plus the missing `[[evidence-capture]]` row above.
- Every `--target-page` distill argument resolves under wiki/ except `techniques/network/vpn-appliances.md` (row above).
- Seed `scripts/caido.sh` EXISTS; `scripts/caido-battery.sh`, `scripts/burp/` (idor-sweep.py, burp-hunt.sh, burp-transport.sh, burp-scope-sync.py, burp-mcp-cli.py, burp-approve.sh), `scripts/wordlists/harness-paths.txt`, `setup/burp/`, `setup/templates/_eval.md`, `docs/superpowers/harness-retro.md`, `raw/manifest.md`, `skills/exploit/hunt/triggers.json`, and all 7 hunt `references/*.md` files exist.
- checklists: every checklist.md copy-target and header matches its SKILL.md contract; hunt-core intentionally ships no checklist (stated in-file).
