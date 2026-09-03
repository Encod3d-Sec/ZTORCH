# ZTORCH

```sh
     )
    ( (
   ) ) (
  ( ( ) )                                          Z   T   O   R   C   H
   ) (*)                             ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄
    )|(                              Z.AI Targeted Offensive Recon & Compromise Harness
     |
    |=|
    | |
    |_|
```

[![Built for ZCode](https://img.shields.io/badge/built%20for-ZCode%20%2F%20Z.AI-blue.svg)](https://z.ai)
[![Wiki pages](https://img.shields.io/badge/wiki-500%2B%20pages-brightgreen.svg)](wiki/)

**An AI-driven pentesting / bug-bounty knowledge base and automation harness for [ZCode](https://z.ai) (Z.AI's GLM coding agent).** Clone it and you get a 500+ page offensive-security wiki, a driver that runs a whole engagement autonomously, and per-vulnerability "hunt" skills wired together so the agent checks the knowledge base before it attacks and never repeats a dead end. Think HackTricks or PayloadsAllTheThings, but semantically searchable and driven by an autonomous agent instead of you ctrl-F'ing a browser tab.

> **Authorized testing only.** Everything here assumes a legal engagement: a signed pentest, an in-scope bug-bounty program, or your own lab/CTF. Staying in scope and within the rules of engagement is on you.

---

## Quickstart

```bash
git clone <this-repo> ZTORCH && cd ZTORCH

bash setup/bootstrap.sh   # one-time per-machine setup: MCP servers, hooks, skill links
qmd update                # build the wiki search index (re-run after adding pages)

# open the folder in ZCode so it loads AGENTS.md + the hooks + the skills, then:
bash setup/new-engagement.sh acme pentest   # or: bugbounty | ctf

# inside ZCode:
#   Skill(engage)                     # router -> picks the right next skill
#   Skill(offensive) --type pentest   # runs the whole engagement autonomously

python3 -m pytest -q          # test suite
bash scripts/check-leaks.sh   # run before every push - client-data leak gate
```

Per-machine paths (vault location, hostnames) go in the git-ignored `AGENTS.local.md` -- copy [`AGENTS.local.example.md`](AGENTS.local.example.md) to create it. Full walkthrough: [`docs/setup.md`](docs/setup.md).

---

## What you get

- **An autonomous engagement driver.** `Skill(engage)` routes to `Skill(offensive)`, which owns the whole loop: `scripts/offensive.py` builds a coverage board from recon and prints the exact next action (which skill, which tool) every turn -- wiki-first, tool-first, typed-evidence, dead-end-first, no operator approvals needed. One `--type` flag (`pentest`/`bb`/`ctf`) picks the flavor.
- **A 500+ page wiki, fully committed** -- not an empty shell. `wiki/techniques/` (AD, cloud, web, network, Linux/macOS, exploit-dev, OSINT...), `wiki/tools/` (per-tool references), `wiki/payloads/`, `wiki/cheatsheets/`. Indexed by `qmd` for semantic + keyword search over an MCP server, so "SSRF to cloud metadata" resolves to the right page in one query. It grows every engagement via the `learn` skill.
- **One hunt skill per vulnerability class** (`skills/hunt/hunt-*`): XSS, SQLi, SSRF, IDOR, RCE, auth bypass, OAuth/SAML, deserialization, cloud, Active Directory, Windows/macOS privesc, API, LLM, ICS/OT, smuggling, and more -- each wiki-first, OOB-gated for blind bugs, emitting a uniform finding schema.
- **Deterministic hooks**, not vibes: `hunt-trigger.py` loads the right hunt skill from your prompt, `recon-capture.py` fingerprints discovered tech and auto-correlates OOB callbacks, `scope-guard.py` hard-denies an out-of-scope or RoE-forbidden command. All fail open.
- **State-first, not stateless.** Every engagement lives under `targets/<name>/`; `next_move.py` ranks what to do next and a coverage table surfaces untested vuln classes so nothing in scope gets skipped.
- **A hard client-data boundary.** Everything client-specific stays under `targets/` (git-ignored); `scripts/check-leaks.sh` gates tracked files before you ever push.

---

## What ships vs. what stays private

| Tracked (public, safe to push) | Git-ignored (stays local) |
|---|---|
| `wiki/` -- the full 500+ page corpus | `targets/` -- client engagements and findings |
| `skills/`, `scripts/`, `setup/`, `docs/`, `tests/` | `AGENTS.local.md` -- machine hostnames/paths |
| `AGENTS.md`, `.zcode/config.json` | `session/`, `raw/`, `~/.claude/skills/` -- local working state |
| `targets/TARGETS.md` -- the generic engagement playbook | `.obsidian/`, runtime caches |

The client-data boundary is a hard rule: hosts, credentials, findings, and engagement narrative live *only* under `targets/`. Run `bash scripts/check-leaks.sh` before your first push -- it scans tracked files for engagement markers, private IPs, and emails.

---

## Requirements

Linux or WSL, `bash`, `python3` 3.10+, Node.js >= 18 + [bun](https://bun.sh), and [ZCode](https://z.ai) with a GLM plan. `qmd` (the wiki search engine) installs via bootstrap.

## Layout

```
AGENTS.md    top-level instructions ZCode loads natively
.zcode/      config.json (hook registration, committed)
wiki/        500+ page technique corpus (semantic + keyword indexed)
skills/      hunt-* (one per vuln class), vector-workflow/, workflow/ (the offensive driver + process skills)
scripts/     offensive.py (driver), next_move, check-leaks, index/lint tooling
setup/       bootstrap, install-hooks, install-skills, new-engagement, templates
docs/        workflows, page-types, setup, sharing (client-data boundary), conventions
tests/       pytest suite for the automation
targets/     engagements -- git-ignored, client data lives ONLY here
```

Full annotated tree: [`docs/layout.md`](docs/layout.md). Day-to-day flow: [`docs/workflows.md`](docs/workflows.md).

## Plugins and MCP servers

`bootstrap.sh` registers the required ones for you: **qmd** (semantic + keyword search over `wiki/`, exposed as the `wiki-search` MCP) and **caveman-shrink** (a token-compressed wrapper around it). Everything else -- `superpowers` (planning workflow), `ponytail` (engineering-discipline mode), `context7` (library docs), `burp-mcp` (Burp Suite driver) -- is optional; the harness degrades gracefully without them. Details: [`docs/setup.md`](docs/setup.md).

## Safety and boundaries

- Client/engagement data lives **only** under `targets/` (git-ignored). Never write it into `wiki/`, `docs/`, `skills/`, or a commit message.
- `bash scripts/check-leaks.sh` before any push -- scans tracked files for engagement markers, emails, and private IPs.
- Hunt skills require out-of-band confirmation for blind vulnerability classes; no inference-only findings.

## The model underneath

ZTORCH is a *harness* -- the intelligence it orchestrates is GLM, trained by Z.AI. If you want to understand what an LLM actually is under the hood, Andrej Karpathy's [nanoGPT](https://github.com/karpathy/nanoGPT), [nanochat](https://github.com/karpathy/nanochat), and [Neural Networks: Zero to Hero](https://karpathy.ai/zero-to-hero.html) are the clearest from-scratch treatments on the internet. Those show you the engine; ZTORCH shows you how to point it at a target and keep it disciplined.

## License

MIT, see [LICENSE](LICENSE).
