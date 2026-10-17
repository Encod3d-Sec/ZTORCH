# A3 review - routing and registry integrity (port 2026-10-17, commit 7ffe4c9)

Summary:
- 13 findings: 10 BROKEN, 2 INTENTIONAL, 1 UNCLEAR.
- The triggers/routing/playbook/chains registries themselves are fully intact: every routed skill name resolves to a real skills dir, zero name collisions, check-routing.py exits 0.
- Biggest risk: the skills tree was mirrored wholesale but six donor scripts it invokes were not ported, leaving three ported skills (interceptor, obsidian-lint, ponytail-debt) inoperable and lint-wiki.py hard-failing on this seat.
- Second risk: apply-wiring.py write_triggers provably deletes the relational_triggers tier from triggers.json on its next trigger apply (simulated; keys in vs keys out captured below).

Loader located: skills/hooks/hunt-trigger.py (registered in .zcode/config.json via ZCODE_PROJECT_DIR) loads `../exploit/hunt/triggers.json` relative to its own realpath, i.e. skills/exploit/hunt/triggers.json - resolves on the new tree. All 26 hunt-* targets, plus ctf-category, research-ingest, research, nday, disclosure, offensive, ingest, redteamlead, metasploit, fuzz, js-discover, js-parser, interceptor, graphify, hunt-core resolve to skills/**/<name>/SKILL.md dirs and are present in the session skill registry. routing.json: 116 rows, 26 distinct skills, every row resolves and every referenced hunt skill carries a `## Wiki` section (validated programmatically via offensive_index._lint_hunt_methods). Name collisions: none (uniq -d over all SKILL.md dir basenames is empty).

| File | Line | Class | Evidence | Proposed fix |
|---|---|---|---|---|
| scripts/apply-wiring.py | 52 | BROKEN | `def write_triggers(d):` emits only `_comment`, `triggers`, `_surface_comment`, `surface_triggers`; grep `relational` over the file = 0 hits. Simulated on a temp copy: keys in `['relational_triggers', 'surface_triggers', 'triggers']` -> keys out `['_comment', '_surface_comment', 'surface_triggers', 'triggers']`, relational survived: False. hunt-trigger.py:187 (`data.get("relational_triggers", {})`) and tests/test_relational_nudge.py depend on the tier; one future `trigger` action silently kills graphify relational routing. | Round-trip `relational_triggers` in write_triggers the same way as the other two blocks. |
| skills/surface/interceptor/SKILL.md | 78 | BROKEN | `ONE COMMAND: ` + `bash scripts/interceptor-automation.sh` (line 79 continues with the up/down/status/context verb list and `(repo scripts/)`) - scripts/interceptor-automation.sh does not exist here; donor scripts/ has it. The skill's whole bring-up path dead-ends. | Port interceptor-automation.sh from the donor scripts/. |
| skills/surface/interceptor/SKILL.md | 195 | BROKEN | `INTERCEPTOR_PAGE=<id> bash scripts/interceptor-cdp.sh eval '<js>'` - interceptor-cdp.sh absent; also invoked at lines 224, 226-229, 249, 269, 276. The DEV-TOOLS CONTEXT LAW section is entirely inoperable. | Port interceptor-cdp.sh from the donor scripts/. |
| skills/surface/interceptor/SKILL.md | 168 | BROKEN | `export the full diff to ` + `setup/interceptor/local-patches.patch` `in the main repo` - setup/interceptor/ does not exist in this repo; donor has it including local-patches.patch. The skill's disaster-recovery contract dangles. | Copy donor setup/interceptor/ (at minimum local-patches.patch). |
| skills/orchestrate/kali-seat/SKILL.md | 130 | BROKEN | `drive the VM directly with ` + `scripts/vm-bridge.sh '<cmd>'` `(same base64 law)` - vm-bridge.sh absent (also refs at lines 122 and 125). Documented fallback when win-vm.sh is unusable; following it on this seat fails. | Port vm-bridge.sh from donor, or re-point lines 122/125/130 at win-vm.sh. |
| skills/orchestrate/kali-seat/SKILL.md | 162 | BROKEN | `bash scripts/scope-sync.sh` `(or the documented vm-ssh + sudo -S route when direct root ssh` - scope-sync.sh absent; donor scripts/ has it. Primary scope-sync route on the skill's checklist is a dead command. | Port scope-sync.sh from donor. |
| skills/platform/obsidian-lint/SKILL.md | 28 | BROKEN | `python3 scripts/obsidian-lint.py targets/<eng>` - obsidian-lint.py absent; the command is also the skill's description (line 3). The entire skill is inoperable. | Port scripts/obsidian-lint.py from donor. |
| skills/platform/ponytail-debt/SKILL.md | 19 | BROKEN | `python3 scripts/ponytail-debt.py` - absent (also line 27 `--stamp` form; skills/platform/ponytail/SKILL.md lines 55 and 68 route `/ponytail-debt` to the same missing script). The slash skill and the ponytail marker ledger are dead. | Port scripts/ponytail-debt.py from donor. |
| skills/surface/js-parser/SKILL.md | 219 | BROKEN | `cp scripts/jsluice-patterns.json /mnt/c/Users/Lenovo/Desktop/VMshare/<eng>/<eng>/js/jsluice-patterns.json` - the repo-side source file is absent (K12 contract, lines 217-224). skills/exploit/hunt/hunt-api/SKILL.md:185 also cites it (`like jsluice-patterns.json`). The cp fails before any VM-side run. | Port scripts/jsluice-patterns.json from donor. |
| skills/orchestrate/offensive/SKILL.md | 35 | BROKEN | `phase` `(predefined phase chain + current phase, from scripts/phases.json - advisory)` - phases.json absent AND this seat's scripts/offensive.py has no phase subcommand (4 prose-only `phase` hits; donor offensive.py has 27 and the files differ). The SKILL documents a driver subcommand that errors here. | Either port the donor driver's phase feature + phases.json, or drop the `phase` clause from the aux list. |
| (aggregated) skills/**/SKILL.md skill-lint residuals | - | INTENTIONAL | skill-lint.py exit 0 by design; 45 advisory lines. The `bare angle bracket in description` on skills/workflow/bb-workflow/SKILL.md is the `->` arrow inside the description string, not a markup token; the `invoke as bash scripts/X` lines where X exists (capture.sh, win-vm.sh, vm-ssh.sh, browser.sh, caido.sh, ...) are style nudges from an advisory linter. | Keep; no action. |
| skills/surface/interceptor/SKILL.md | 43 | INTENTIONAL | Donor tool-tree absolute paths (`/mnt/c/Users/Lenovo/AppData/Local/hermes/tools/interceptor/...`, `.bun/bin/bun.exe`, Edge-on-seat, HKCU NativeMessagingHosts) - the tool dir EXISTS on this host, so the CLI invocations resolve; the skill is donor-seat flavored but not wrong here. | Keep. |
| scripts/check-routing.py | 209 | UNCLEAR | Trigger regex-compile loop iterates `for section in ("triggers", "surface_triggers"):` only - `relational_triggers` keys are never re.compile-checked (lint-wiki.check_triggers resolves their skill targets but compiles nothing). All three current relational regexes do compile and hunt-trigger.py:56 fails open per-key, so nothing is broken today; the drift check just has a blind spot for the tier it does not know to guard. | Extend the section tuple with `relational_triggers`. Escalate: trivial, but it touches the shared linter other slices also reviewed. |

## Mandated runs (raw output, vault root)

### python3 scripts/check-routing.py

```
check-routing: 0 violation(s)
EXIT=0
```

### python3 scripts/skill-lint.py (EXIT=0, advisory by design)

```
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/exploit/hunt/hunt-auth/SKILL.md: invoke as `bash scripts/capture.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/exploit/hunt/hunt-core/SKILL.md: invoke as `bash scripts/check-leaks.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/exploit/hunt/hunt-rce/SKILL.md: invoke as `bash scripts/stager.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/orchestrate/kali-seat/SKILL.md: invoke as `bash scripts/win-vm.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/orchestrate/kali-seat/SKILL.md: invoke as `bash scripts/vm-ssh.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/orchestrate/kali-seat/SKILL.md: invoke as `bash scripts/win-rsh.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/orchestrate/kali-seat/SKILL.md: invoke as `bash scripts/win-rsh.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/orchestrate/kali-seat/SKILL.md: invoke as `bash scripts/vm-ssh.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/orchestrate/kali-seat/SKILL.md: invoke as `bash scripts/vm-bridge.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/orchestrate/kali-seat/SKILL.md: invoke as `bash scripts/win-vm.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/orchestrate/kali-seat/SKILL.md: invoke as `bash scripts/vm-bridge.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/orchestrate/kali-seat/SKILL.md: invoke as `bash scripts/vm-bridge.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/orchestrate/kali-seat/SKILL.md: invoke as `bash scripts/vm-ssh.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/platform/wiki/SKILL.md: invoke as `bash scripts/check-leaks.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/surface/browser/chrome-devtools-browser/SKILL.md: invoke as `bash scripts/browser.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/surface/browser/chrome-devtools-browser/SKILL.md: invoke as `bash scripts/browser.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/surface/browser/chrome-devtools-browser/SKILL.md: invoke as `bash scripts/browser.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/surface/browser/screenshot/SKILL.md: invoke as `bash scripts/capture.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/surface/browser/screenshot/SKILL.md: invoke as `bash scripts/capture.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/surface/browser/screenshot/SKILL.md: invoke as `bash scripts/capture.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/surface/browser/screenshot/SKILL.md: invoke as `bash scripts/capture.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/surface/browser/screenshot/SKILL.md: invoke as `bash scripts/capture.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/surface/browser/screenshot/SKILL.md: invoke as `bash scripts/capture.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/surface/burp/hunt-burp/SKILL.md: invoke as `bash scripts/capture.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/surface/burp/screenshot-burp/SKILL.md: invoke as `bash scripts/capture.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/surface/burp/screenshot-burp/SKILL.md: invoke as `bash scripts/capture.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/surface/burp/screenshot-burp/SKILL.md: invoke as `bash scripts/capture.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/surface/caido/SKILL.md: invoke as `bash scripts/caido.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/surface/caido/SKILL.md: invoke as `bash scripts/browser.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/surface/caido/SKILL.md: invoke as `bash scripts/caido.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/surface/caido/SKILL.md: invoke as `bash scripts/caido.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/surface/interceptor/SKILL.md: invoke as `bash scripts/browser.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/surface/interceptor/SKILL.md: invoke as `bash scripts/interceptor-automation.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/surface/interceptor/SKILL.md: invoke as `bash scripts/interceptor-cdp.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/workflow/bb-workflow/SKILL.md: bare angle bracket in description
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/workflow/closeout/learn/SKILL.md: invoke as `bash scripts/check-leaks.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/workflow/ctf/ctf-box/SKILL.md: invoke as `bash scripts/vm-scan.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/workflow/ctf/ctf-box/SKILL.md: invoke as `bash scripts/capture.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/workflow/ctf/ctf-box/SKILL.md: invoke as `bash scripts/capture.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/workflow/ctf/ctf-box/SKILL.md: invoke as `bash scripts/recon-web.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/workflow/ctf/ctf-box/SKILL.md: invoke as `bash scripts/vm-rsh.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/workflow/ctf/ctf-box/SKILL.md: invoke as `bash scripts/capture.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/workflow/ctf/ctf-box/SKILL.md: invoke as `bash scripts/autocard.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/workflow/ctf/ctf-box/SKILL.md: invoke as `bash scripts/capture.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/workflow/ctf/ctf-box/SKILL.md: invoke as `bash scripts/wl-add.sh` (exec bits unreliable on NTFS)
skill-lint: 45 issue(s) across skills/ (advisory)
```

## Supporting evidence (extra runs)

### python3 scripts/lint-wiki.py -v (exit 1; dead-script-ref section is the registry-relevant part)

```
=== wiki lint ===
broken wikilinks : 0 distinct missing target(s)
dead script refs : 7
    scripts/scope-sync.sh  <- skills/orchestrate/kali-seat/SKILL.md
    scripts/vm-bridge.sh  <- skills/orchestrate/kali-seat/SKILL.md
    scripts/obsidian-lint.py  <- skills/platform/obsidian-lint/SKILL.md
    scripts/ponytail-debt.py  <- skills/platform/ponytail/SKILL.md
    scripts/ponytail-debt.py  <- skills/platform/ponytail-debt/SKILL.md
    scripts/interceptor-automation.sh  <- skills/surface/interceptor/SKILL.md
    scripts/interceptor-cdp.sh  <- skills/surface/interceptor/SKILL.md
playbook integrity: 0 issue(s)
triggers integrity: 0 issue(s)
frontmatter      : 0 hard issue(s); 4 page(s) missing a date (soft)
    no date: wiki/cheatsheets/macos-enumeration.md
    no date: wiki/cheatsheets/macos-loot-locations.md
    no date: wiki/payloads/macos-app-injection.md
    no date: wiki/tools/caido.md
index.md         : current
leanest areas    : blockchain (238L), forensics (591L), macos (982L)
em-dash (soft)   : 13 page(s), 35 prose occurrence(s) - vault rule says avoid (comma/semicolon/rewrite)
FAIL: 7 hard problem(s)
```

(Wiki-content lines above belong to the wiki slice; carried here only because the dead-script-ref block is the hard-fail evidence for the missing-port rows.)

### apply-wiring.py write_triggers simulation (temp copy, repo untouched)

```
keys in : ['relational_triggers', 'surface_triggers', 'triggers']
keys out: ['_comment', '_surface_comment', 'surface_triggers', 'triggers']
relational_triggers survived: False
```

### routing.json programmatic validation (offensive_index linters, read-only)

```
routing rows: 116
hunt-method lint: OK (all skills resolve, all have ## Wiki)
distinct skills: hunt-ad, hunt-api, hunt-auth, hunt-bizlogic, hunt-cache, hunt-cicd, hunt-cloud, hunt-deserialization, hunt-federation, hunt-ics, hunt-idor, hunt-injection, hunt-llm, hunt-m365, hunt-macos, hunt-mcp, hunt-pwn, hunt-rce, hunt-secrets, hunt-smuggling, hunt-sqli, hunt-ssrf, hunt-upload, hunt-vpn, hunt-windows, hunt-xss
```

### Name-collision check

```
find skills -name SKILL.md | dirname-basenames | sort | uniq -d
(empty output = no collisions)
```

### Provenance notes (donor diff, read-only)

- skills/exploit/hunt/triggers.json is byte-identical to the donor copy (diff empty); scripts/apply-wiring.py is also identical - the write_triggers relational drop is inherited, not introduced, but is live on this seat.
- Donor scripts/ has 9 entries this repo lacks: attic/, interceptor-automation.sh, interceptor-cdp.sh, jsluice-patterns.json, obsidian-lint.py, phases.json, ponytail-debt.py, scope-sync.sh, vm-bridge.sh. Six of the seven ported-reference ones (all but jsluice-patterns.json, which is .json and so invisible to the SCRIPTREF_RE gate) are exactly what lint-wiki dead-ref FAILs on.
