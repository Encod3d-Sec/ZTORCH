---
title: "PyRIT"
type: tool
tags: [llm, ai, scanner, exploitation, web, prompt-injection]
date_created: 2026-09-09
date_updated: 2026-09-09
sources: []
phase: exploit
---

## Purpose

**PyRIT** (Microsoft, `microsoft/PyRIT`) is a Python framework plus scanner CLI for adversarial AI testing: scripted attack scenarios, single- and multi-turn conversation attacks (Crescendo, TAP/Tree of Attacks with Pruning, Skeleton Key), all written to a queryable conversation memory. Reach for it when single-shot probes ([[garak]]) or a config baseline ([[promptfoo]]) come back clean but you suspect a guardrail that conversational escalation can walk through.

## Install / setup

```bash
python3 -m venv ~/.venvs/pyrit && . ~/.venvs/pyrit/bin/activate
pip install pyrit                                # python 3.13 recommended by the docs
python -c "import pyrit; print(f'PyRIT version installed: {pyrit.__version__}')"
```

Point it at the target with env vars or `~/.pyrit/.env` (tabbed examples cover OpenAI, Azure, Ollama, Groq, HuggingFace; any OpenAI-compatible endpoint works through the OpenAI variables):

```bash
export OPENAI_CHAT_ENDPOINT="https://api.openai.com/v1"   # ollama: http://127.0.0.1:11434/v1
export OPENAI_CHAT_KEY="sk-..."
export OPENAI_CHAT_MODEL="llama3.1:8b"
```

`~/.pyrit/.pyrit_conf` is the persistent config (initializers that register targets, scorers, datasets; `memory_db_type: in_memory` etc.); required for `pyrit_scan`. Memory backends: in-memory, SQLite, Azure SQL.

## Core usage

```bash
pyrit_scan list-scenarios

# scan family.scenario against the configured target
pyrit_scan run airt.scam --target openai_chat
pyrit_scan run foundry.red_team_agent --target openai_chat --initializers target --techniques base64

pyrit_backend                                    # local GUI
```

Scenario families (per `list-scenarios` docs): `airt` (Jailbreak, Leakage, Scam, Cyber, Psychosocial, Multilingual, RapidResponse), `foundry` (RedTeamAgent), `garak` (Encoding, FigStep, WebInjection, SystemPromptExtraction, and more), `benchmark` (AdversarialBenchmark), `adaptive` (TextAdaptive).

Python API for custom attacks (initialize first, then drive an executor):

```python
from pyrit.setup import initialize_pyrit_async
from pyrit.setup.initializers import ScorerInitializer, TargetInitializer

await initialize_pyrit_async(memory_db_type="InMemory", initializers=[TargetInitializer(), ScorerInitializer()])
```

Terminology note: pre-1.x docs and notebooks call the drivers **orchestrators** (`PromptSendingOrchestrator`, `RedTeamingOrchestrator`, `CrescendoOrchestrator`); 1.x renames the concept to **executors/attacks**. Old notebook names map onto the same machinery.

## Common use cases

```bash
# System-prompt extraction scenario against a local model
pyrit_scan run garak.system_prompt_extraction --target openai_chat

# Jailbreak escalation with a converter technique
pyrit_scan run airt.jailbreak --target openai_chat --techniques base64
```

Custom multi-turn escalation (Crescendo/TAP/Skeleton Key) is scripted against the Python API: the attack executor alternates between an adversarial model (which iterates the jailbreak) and the target, so multi-turn runs need **two** endpoints, the target and an attacking model, even when the target is local.

## Interpreting results

- Every prompt/response pair is stored in the **conversation memory** (CentralMemory over the configured SQLite/in-memory/Azure SQL backend): after a run, pull the transcript per session, not just the final score. The winning escalation transcript is your evidence chain for how the guardrail folded.
- Scan runs report which scenarios produced hits; treat a scored "attack succeeded" as a lead. The harness confirmation gate ([[llm-attacks]]) still applies: reproduce in a clean session, capture the raw exchange into `poc/`, and only a crossed boundary (leaked secret, invoked tool, verified prompt leak) is a finding.
- `--auth-mode` flags (`device_code`, `none`, `azure_cli`) matter only for Entra-backed Foundry flows; local/OpenAI-compatible targets run with no auth discovery.

## Tips and gotchas

- Multi-turn attacks are request-hungry: each turn costs a target call plus an adversarial-model call; budget accordingly on fragile or rate-limited endpoints.
- Docker/devcontainer installs mount the host's `~/.pyrit/.env` (home resolves to `/home/vscode` in-container); set env vars inside the container for notebook use.
- The classic `pyrit` notebooks on the docs site still reference orchestrator names; prefer the 1.x `pyrit_scan` CLI for repeatable runs.

## Related techniques

Primary technique page [[llm-attacks]]; payloads in [[llm-prompt-injection]]; agent/tool-calling surfaces chain to [[mcp-server-attacks]]. Siblings in the scanner ladder: [[promptfoo]] (baseline first), [[garak]] (breadth sweep).

## Sources

- microsoft/PyRIT README (github.com/microsoft/PyRIT; org confirmed, no further move)
- PyRIT 1.1.0 docs (microsoft.github.io/PyRIT): install, configuration, scanner pages
