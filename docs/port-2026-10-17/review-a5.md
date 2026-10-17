# A5 functional battery review - Torchv2 port (7ffe4c9)

Battery: 9 commands from vault root, HEAD f0ca5fd (direct child of the port commit).
Summary: 7 findings; 1 BROKEN, 1 INTENTIONAL, 5 UNCLEAR. Biggest risk: the wholesale
skills/ rewrite staled every engagement's driver index, so `offensive.py next` refuses
(RC=2) on all 5 stateful boards until each is re-indexed; the active engagement
additionally has no `.offensive.json` at all. Engagement names below are redacted to
`<eng>` (client-data boundary).

## Findings

| # | file | line | class | evidence | proposed fix |
|---|------|------|-------|----------|--------------|
| 1 | scripts/offensive.py | 1095 | BROKEN | Post-port run: `error: index stale or missing (a routing/tool/skill source changed) - run: offensive.py --eng <eng> index`, RC=2. Root cause at scripts/offensive_index.py:277: `stale = any(p.stat().st_mtime > cache_mtime for p in _index_sources(vault_root))`; the wholesale mirror re-wrote every hunt `SKILL.md`, so all pre-port `.offensive-index.json` caches are older than every source. Verified on a stateful board (5 boards carry `.offensive.json`; one exercised live). G9 refuses by design; the port shipped no re-index step, so the driver's core move is dead on every existing board. | After the port, run `python3 scripts/offensive.py --eng <eng> index` once per engagement (or a one-liner looping over dirs holding `.offensive.json`). |
| 2 | `targets/<eng>/.offensive.json` | n/a | UNCLEAR | `targets/active.md` names an engagement whose dir has no `.offensive.json` while sibling dot-state (`.events.jsonl`, `.fp-fired`, `.doa-stamp`) survived: `offensive.py --eng <eng> next` -> `error: .offensive.json missing - run `init` first`, RC=2. Driver state is git-ignored seat-local; it was lost or never built on this seat. Active engagement is unusable by the driver even after finding 1's re-index. | Run `python3 scripts/offensive.py --eng <eng> init` (main session; writes into `targets/`, outside review scope). Escalate: re-init may re-rank from scratch. |
| 3 | skills/workflow/bb-workflow/SKILL.md | 3 | UNCLEAR | Description contains bare `>` characters in `->` arrows: `surface mapping -> JS corpus -> signal-based hunt-* class selection -> confirm -> triage -> report`. Flagged by scripts/skill-lint.py (rule at scripts/skill-lint.py:52: `if "<" in desc or ">" in desc`). Donor-identical (inherited verbatim from HermesTORCH, checked). Advisory only; linter exits 0 by design. | Reword the description arrows without `>` (commas or `then`). |
| 4 | scripts/skill-lint.py | 70 | INTENTIONAL | 44 of 45 advisories are `invoke as `bash scripts/<name>.sh` (exec bits unreliable on NTFS)` emitted by SCRIPT_CALL_RE, which has no inline-code exemption: e.g. skills/orchestrate/kali-seat/SKILL.md:104 flags the backticked reference `` `scripts/win-rsh.sh` `` (a path mention, not an invocation). Linter working as designed on the NTFS seat; advisory, exit 0, across 10 skills. | None required; optionally skip inline-code spans (`` `...` ``) in the script-call scan to cut false positives. |
| 5 | scripts/find-lint.py | 261 | UNCLEAR | `python3 scripts/find-lint.py --help` ignores the flag (`verbose = "-v" in sys.argv` is the only argv check) and silently runs a scan: `find-lint (active-eng): no FIND-*.md files yet.` Docstring documents only the default run and `-v`; no self-test/check mode exists. | One line: `if "--help" in sys.argv: print(__doc__); return 0`. |
| 6 | skills/hooks/hunt-trigger.py | n/a | UNCLEAR | AGENTS.md names `hunt-trigger.py` unqualified (reads as `scripts/`); the file lives at `skills/hooks/hunt-trigger.py` (find confirmed, nothing in `scripts/`). Hook registration is correct (.zcode/config.json:30 points at `skills/hooks/hunt-trigger.py`) and the dry run fires correctly, so this is a discoverability snag only. | One line in AGENTS.md: name the path `skills/hooks/hunt-trigger.py`. |
| 7 | tests/ | n/a | UNCLEAR | Suite passes (547) but `tests/` is untracked on this seat: commit f0ca5fd message reads `gitignore: seat-local state (.hermes.md, .skillspector-baseline.yaml) + tests/ local-only; untrack them`. A fresh clone gets no tests, so the 547-pass expectation is seat-local state, not a repo guarantee. | Confirm `tests/` untracking is intended for the port; otherwise re-track before merge. |

## Battery log (raw outputs)

### 1. pytest

Command: `python3 -m pytest tests/ -q`

```
........................................................................ [ 13%]
........................................................................ [ 26%]
........................................................................ [ 39%]
........................................................................ [ 52%]
........................................................................ [ 65%]
........................................................................ [ 78%]
........................................................................ [ 92%]
...........................................                              [100%]
547 passed in 152.69s (0:02:32)
```

Matches the expected 547 passed. No failures. See finding 7 (tests/ untracked).

### 2. offensive-doctor

Command: `python3 scripts/offensive-doctor.py`

```
WARN  zg MCP server registered (user scope)  - claude mcp add -s user -t http zvec-grep http://127.0.0.1:7999/mcp
WARN  zg daemon reachable (loopback 7999)  - zg server on
WARN  skill-scan: no new findings vs baseline (advisory)  - 11/44 skills with new findings, 17 total

offensive-doctor: 29 checks, 26 PASS, 3 WARN, 0 FAIL
OK with warnings (see the WARN lines).
```

0 FAIL as expected. WARN meanings: (1) zvec-grep MCP server not registered in user
scope (seat config suggestion); (2) zg daemon not reachable on loopback 7999 (run
`zg server on`); (3) skill-scan advisory: 11 of 44 skills have findings vs baseline
(17 total) - informational only.

### 3. check-routing

Command: `python3 scripts/check-routing.py`

```
check-routing: 0 violation(s)
```

Clean.

### 4. skill-lint

Command: `python3 scripts/skill-lint.py` (output 46 lines; tail below)

```
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/workflow/bb-workflow/SKILL.md: bare angle bracket in description
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/workflow/closeout/learn/SKILL.md: invoke as `bash scripts/check-leaks.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/workflow/ctf/ctf-box/SKILL.md: invoke as `bash scripts/vm-scan.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/workflow/ctf/ctf-box/SKILL.md: invoke as `bash scripts/capture.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/workflow/ctf/ctf-box/SKILL.md: invoke as `bash scripts/recon-web.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/workflow/ctf/ctf-box/SKILL.md: invoke as `bash scripts/vm-rsh.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/workflow/ctf/ctf-box/SKILL.md: invoke as `bash scripts/capture.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/workflow/ctf/ctf-box/SKILL.md: invoke as `bash scripts/autocard.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/workflow/ctf/ctf-box/SKILL.md: invoke as `bash scripts/capture.sh` (exec bits unreliable on NTFS)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/workflow/ctf/ctf-box/SKILL.md: invoke as `bash scripts/wl-add.sh` (exec bits unreliable on NTFS)
skill-lint: 45 issue(s) across skills/ (advisory)
```

Exit 0 (advisory by design). Category census: 44 `invoke as bash scripts/*.sh`
advisories + 1 bare angle bracket (finding 3). The 44 are finding 4 (INTENTIONAL
linter behavior). No name/fence/frontmatter-key/em-dash/smart-quote failures.

### 5. find-lint

Command: `python3 scripts/find-lint.py --help`

```
find-lint (<eng>): no FIND-*.md files yet.
```

Exit 0. No self-test/check mode exists per the source (only `-v` verbose); see
finding 5.

### 6. wiki-gaps

Command: `python3 scripts/wiki-gaps.py`

```
active-directory-certificate-esc-attacks
active-directory-certificate-services
active-directory-gpo
aws-identity-access-management
azure-attacks
cicd-azure-devops
cookie-attacks
hardcoded-secrets-enumeration
hash-overpass-the-hash
hash-pass-the-key
internal-kerberos-relay
kerberos-tickets
network-pivoting-techniques
network-pivoting-tools
reverse-shell-cheat-sheet
source-code-analysis
vpn-appliances
x
```

Exit 0. All 17 gaps trace to `targets/` capture dumps via `-v` (e.g. `x` comes from
a path-form match in a `targets/<eng>/poc/cmdlog/grep.md` dump); zero gaps referenced
from the ported `skills/exploit/hunt/` tree, so no ported skill points at a wiki
page this vault lacks.

### 7. wl-pick

Command: `bash scripts/wl-pick.sh` (no args; the usage line documents this as the
usage path - there is no `--help` flag)

```
usage: wl-pick.sh <content|files|vhost|api|params|artifacts> [fingerprint] [ctf|pt|bb]
```

Exit 2 (documented usage gate). Functional follow-up with a valid surface:
`bash scripts/wl-pick.sh content`

```
# seclists: /usr/share/seclists
# flags: threads=60 rate=0 recursion=2 jitter=off (profile=ctf)
/mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/scripts/wordlists/harness-paths.txt
/usr/share/seclists/Discovery/Web-Content/common.txt
/usr/share/seclists/Discovery/Web-Content/quickhits.txt
/usr/share/seclists/Discovery/Web-Content/raft-small-directories.txt
/usr/share/seclists/Discovery/Web-Content/raft-medium-directories.txt
/usr/share/seclists/Discovery/Web-Content/raft-large-directories.txt
/usr/share/seclists/Discovery/Web-Content/DirBuster-2007_directory-list-2.3-medium.txt
```

Exit 0; seclists base resolves on this seat (wordlist-map.json first existing
candidate `/usr/share/seclists`). PASS.

### 8. hunt-trigger dry run

`python3 skills/hooks/hunt-trigger.py -h` - file does not exist at that path (finding 6).
Actual file `skills/hooks/hunt-trigger.py` takes stdin (JSON `{"prompt": ...}` or raw
text), so a stdin dry run is supported. Run:
`printf '{"prompt":"test the login form for SQL injection"}' | python3 skills/hooks/hunt-trigger.py`

```
Relevant skill for this prompt: Skill(hunt-sqli) -- load it before you act on this class; it carries the wiki-first, tooling-first, and methodology steps. Skip only if it is genuinely irrelevant here.
Attack surface matched -- strongly consider loading Skill(hunt-auth) (heuristic; skip only if this prompt is not about testing that surface).
Also load Skill(hunt-core) -- the shared spine every hunt-* skill assumes (scope gate, two-account rule, confirmation gate, enumeration limits, stop conditions, FIND output, Deadends). Load it alongside the skill(s) above.
```

Exit 0. Hard tier, soft tier, and hunt-core spine co-load all fire correctly.
Side effect: one leak-safe telemetry record appended to `.trigger-fire.jsonl`
(verified git-ignored via `.gitignore:46`). Hook registration verified:
.zcode/config.json:30 points at `skills/hooks/hunt-trigger.py`.

### 9. offensive.py next

Read-only board move. Bare `python3 scripts/offensive.py next` (no `--eng`):

```
error: --eng <name|path> required for `next`
```

RC=2 (usage error; correct behavior).

`python3 scripts/offensive.py --eng <eng> next` (the active engagement):

```
error: .offensive.json missing - run `init` first
```

RC=2. See finding 2.

`python3 scripts/offensive.py --eng <eng> next` (a board that has driver state;
specifics redacted per contract - the output below contains none):

```
offensive: index stale or missing (a routing/tool/skill source changed) - run: offensive.py --eng <eng> index
```

RC=2. No banner or next line could be produced on any board: see finding 1 (the
port staled every index; re-index writes into `targets/`, outside review write
scope). Flag order note: `--eng` must precede the subcommand
(`offensive.py --eng <name> next`); after it, argparse rejects it with
`unrecognized arguments: --eng active-eng` (RC=2).
