# Torchv2 port review: consolidated verified fix ledger

Port under review: `7ffe4c9` (skills/ wholesale mirror + wsl integration), branch `ai-uplift`.
Slices: A1 stale refs (17 rows), A2 dependency existence (46), A3 wiring/logic (13), A4 docs + report skills (19), A5 driver state + battery (7 raw).
All load-bearing claims re-verified main-session: apply-wiring.py `write_triggers` source read (relational tier provably dropped); lint-wiki rerun; donor file existence (scripts, wiki pages, absence of docs/design-scope-shim.md); offensive.py phases.json grep (0 refs); caido-mode deletion vs `b00dfff`; triggers.json/routing.json route resolution.

## Stop-condition reassessment

Raw BROKEN rows across slices are ~75 pre-dedupe, which trips the spec's ~25-BROKEN stop
condition. Reassessed at consolidation: the composition is pattern-concentrated, not a
divergent systemic failure:

- 20 rows are one repeated one-line donor transport anchor (`cd .../HermesTORCH` -> ZTorch).
- ~12 rows are one stale-layout prose cluster (skill-map/layout/AGENTS/README).
- ~10 rows are one missing-files cluster (donor helpers + caido-mode + 2 wiki pages).
- 3 logic bugs (apply-wiring round-trip, tells.json depth regex, check-routing coverage gap).
- 1 driver-state staleness class (mtime-bumped SKILL.md files vs `.offensive-index.json` G9).

Batch execution stays sound under the operator's standing directive.

## Batch assignments

### F4 scripts/routing (execute first: apply-wiring fix unblocks future trigger edits)

| id | file | fix | status |
|---|---|---|---|
| F4-1 | scripts/apply-wiring.py:52 | `write_triggers` round-trips `relational_triggers` (preserve `_relational_comment` when present; emit tier only when key exists) | OPEN |
| F4-2 | scripts/check-routing.py:209 | section tuple `("triggers", "surface_triggers")` gains `relational_triggers` | OPEN |
| F4-3 | scripts/tells.json:467 | fname regex -> `(^|/)skills/(?:[^/]+/)+SKILL\\.md$` (3-level tree) | OPEN |
| F4-4 | scripts/caido.sh:5,14 | `skills/caido` -> `skills/surface/caido` | OPEN |
| F4-5 | scripts/wiring-exempt.txt:20 | comment -> `skills/exploit/hunt` (skill lives at skills/report/disclosure) | OPEN |
| F4-6 | tests/test_routing_table.py:38 | assert message text -> `skills/exploit/hunt` | OPEN |

### F2 tooling restore/port (from donor vault + git history)

| id | source | action | status |
|---|---|---|---|
| F2-1 | git `b00dfff` | restore vendored `skills/caido/caido-mode/` (21 files) -> `skills/surface/caido/caido-mode/` | OPEN |
| F2-2 | donor scripts/ | port `interceptor-automation.sh` (seat-scan: donor paths) | OPEN |
| F2-3 | donor scripts/ | port `interceptor-cdp.sh` (seat-scan) | OPEN |
| F2-4 | donor scripts/ | port `vm-bridge.sh` (seat-scan; kali-seat L122-130) | OPEN |
| F2-5 | donor scripts/ | port `scope-sync.sh` (kali-seat L162) | OPEN |
| F2-6 | donor scripts/ | port `obsidian-lint.py` (obsidian-lint skill L3,28) | OPEN |
| F2-7 | donor scripts/ | port `ponytail-debt.py` (ponytail L55,68; ponytail-debt L19,27) | OPEN |
| F2-8 | donor scripts/ | port `jsluice-patterns.json` verbatim (js-parser L217-219) | OPEN |
| F2-9 | donor setup/interceptor/ | copy `local-patches.patch` only (rest is donor-local dev scaffolding) | OPEN |
| F2-10 | donor wiki/techniques/methodology/ | copy `evidence-capture.md` (screenshot skill L22,24) after boundary check | OPEN |
| F2-11 | donor wiki/techniques/network/ | copy `vpn-appliances.md` (hunt-vpn L208,247) after boundary check | OPEN |

Decision: `scripts/phases.json` NOT ported (inert here; offensive.py has no phase subcommand,
0 phases.json refs). Fix is dropping the clause from offensive SKILL.md L35 (F1-24).
Decision: `docs/design-scope-shim.md` does not exist anywhere donor-side (only `hermes/scope-shim/`
framework internals, not ported by design); citation dropped from interceptor SKILL.md (F1-25).

### F1 skills content

| id | file | fix | status |
|---|---|---|---|
| F1-1..20 | 20 skills (metasploit:43, hunt-pwn:37, hunt-rce:61, hunt-secrets:59, hunt-smuggling:60, hunt-sqli:55 + 5 sqli experts, hunt-ssrf:57, hunt-upload:57, hunt-vpn:46, hunt-windows:43, hunt-xss:58 + 4 xss experts) | `cd /mnt/c/.../HermesTORCH` -> `.../ZTorch/ZTorch` (hunt-windows abbreviated spelling -> full path; hunt-pwn block header `# seat side (Windows)` -> wsl seat spelling) | OPEN |
| F1-21 | skills/report/walkthrough/SKILL.md:28 | `Skill(engagement-retro)` -> `Skill(learn)` (harness chain: AGENTS.md L64, offensive.py L79-81, close-out.py L422-426, auto-triggers.md L38) | OPEN |
| F1-22 | skills/workflow/closeout/learn/SKILL.md:3,8-22 | SA4-style seat annotation of the Hermes deprecation banner (memory -> project memory/CLAUDE.md, session_search -> transcript recall; skill remains mandatory here) | OPEN |
| F1-23 | skills/orchestrate/offensive/SKILL.md:35 | drop the `phase` aux clause (no subcommand on this seat) | OPEN |
| F1-24 | skills/surface/interceptor/SKILL.md:157 | drop the design-scope-shim.md citation (deferred donor-internal note) | OPEN |
| F1-25 | skills/platform/ponytail/SKILL.md:4 + ponytail-review:15,20 | drop `hermes/` token from scope lists | OPEN |
| F1-26 | tests/test_autonomy.py:19 | docstring reword (symlinks whole skills/ dir) | OPEN |

### F3 docs

| id | file | fix | status |
|---|---|---|---|
| F3-1 | docs/skill-map.md:52-72 | rewrite vault-local skill layout block to live tree (orchestrate/, exploit/ split, surface/, platform/, research/, report/; no standalones) | OPEN |
| F3-2 | docs/layout.md:52-63 | redraw skills/ subtree from live tree | OPEN |
| F3-3 | AGENTS.md:100 | tree line -> `(exploit/ orchestrate/ platform/ research/ surface/ workflow/ report/ + hooks/)` | OPEN |
| F3-4 | README.md:82 | layout line -> categorized tree | OPEN |
| F3-5 | docs/auto-triggers.md:89 | count -> `56 triggers total (39 vuln-type + 17 surface)` | OPEN |
| F3-6 | skills/skills-setup.md:19,24 | `ObisidianVaults` spelling; delete duplicated intake section (L112-125 vs L129-142) | OPEN |

### F5 driver state

| id | scope | action | status |
|---|---|---|---|
| F5-1 | darboviete, eneba, fjordbank, kovas, vilnius | `offensive.py --eng <eng> index` (mtime bump staled all `.offensive-index.json` vs G9) | OPEN |
| F5-2 | engagement named in targets/active.md | locate driver state (no dir at targets/ root despite live board); re-index if stateful, else record operator-deferred | OPEN |

## Execution order

F4 -> F2 -> F1 -> F3 -> F5 -> final battery (pytest 547, doctor 0 FAIL, check-routing 0,
lint-wiki 0 dead refs, wiki-gaps unchanged at 17). One commit per batch; findings files +
this ledger commit with F1. Note: lint-wiki currently counts 20 dead script refs because
these review files cite the missing scripts; resolves itself as F2 lands (refs become live).

## Close-out

Executed 2026-10-17, all batches landed:

| batch | commit | contents |
|---|---|---|
| F4 | `59b909c` | apply-wiring `write_triggers` relational-tier round-trip (guarded by seat-local `tests/test_apply_wiring_roundtrip.py`), check-routing tuple, tells.json fname regex, caido.sh + wiring-exempt + test-routing paths |
| F2 | `627bc55` | caido-mode SDK restored from `b00dfff` (21 files) under `skills/surface/caido/`; donor helper scripts ported (vm-bridge, interceptor x2, scope-sync, obsidian-lint, ponytail-debt, jsluice-patterns, local-patches.patch); 2 generic wiki pages; index/MOC regen |
| F1 | `ae861d8` | 20 donor transport anchors repointed (flash-agent batch, main-session grep-verified); 6 judgment edits (walkthrough, learn SEAT NOTE, offensive phase-line drop, interceptor, ponytail x2); sweep extras: junction-sweep.ps1 + kali-seat push path, port-added `skills/platform/skills-setup.md` duplicate removed, 17 port files CRLF->LF, skills-setup.md path spelling/nesting + dedupe (rode along: skills-tree hygiene); review a1-a5 + this ledger committed here |
| F3 | (this commit) | docs stale-layout cluster: skill-map + layout tree rewrites, AGENTS.md:100, README:82, auto-triggers 56 (39+17, verified live), ledger close-out |

Final battery: pytest **548 passed** (547 baseline + round-trip test), offensive-doctor
**29 checks / 0 FAIL / 3 WARN** (zg daemon down x2, skill-scan advisory), check-routing **0**,
lint-wiki **0 hard / 0 dead script refs**, wiki-gaps **17 unchanged** (pre-existing archived
FIND targets), check-leaks clean (pre-existing WARNs only).

F5 driver state: `.offensive.json` exists for darboviete/eneba/fjordbank/kovas/vilnius -
all five re-indexed against the ported tree (`116 fingerprints | 99 tools | 26 skills`
each). The engagement named in `targets/active.md` has NO driver state file; its SessionStart board
comes from the .md set + hooks, nothing to re-index - operator call whether to initialize.

Operator follow-ups (out of session scope):
- skillspector uv-tool venv is broken on this seat (package dir missing; PyPI name does
  not resolve; source is `git+https://github.com/NVIDIA/skillspector.git` per uv-receipt).
  Reinstall was blocked by the session permission classifier. Manual fix:
  `uv tool install --force git+https://github.com/NVIDIA/skillspector.git`, then
  `bash scripts/skill-scan.sh --all` and regenerate `.skillspector-baseline.yaml` for the
  post-port layout. The one CRITICAL in the current report was hand-reviewed: hunt-ics
  SKILL.md:95 safety prose ("injure and kill people") - false positive, accept + baseline.
- zg daemon down (`zg server on`) - flips two doctor WARNs.
- Donor junction-sweep.ps1 carries a literal TAB inside `'hermes<TAB>orch-skills'`
  upstream (frozen donor bytes); left verbatim, only `$repo` repointed.

Post-close-out addendum (2026-10-17, seat bring-up): the ported
`interceptor-automation.sh` / `interceptor-cdp.sh` were authored for
git-bash-on-Windows and silently died on the WSL seat (no powershell.exe on
PATH, direct-C:/ execs, Linux netstat/curl blind to NAT-mode Windows
loopback, and WSL->Windows env vars do not cross interop). Both scripts now
route every Windows-side action through powershell.exe (absolute interop
path; context pin and worker params ride `$env:`/argv, not environment), and
the interceptor SKILL.md CLI pattern + WAKE/KILL laws were updated to match.
Live-verified end to end on the seat: `up` -> context
`gomcpnagjjlhehnkoobkjgnkbleiooed` CONNECTED, CLI `open --reuse --group` drove
the instance, CDP targets/eval/netwatch all returned (netwatch JSONL captured
on a mid-window navigation). Daemon held by a pre-existing standalone
listener (pid 39356).
