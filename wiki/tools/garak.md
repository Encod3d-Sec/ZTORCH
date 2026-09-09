---
title: "garak"
type: tool
tags: [llm, ai, scanner, exploitation, web, prompt-injection]
date_created: 2026-09-09
date_updated: 2026-09-09
sources: []
phase: exploit
---

## Purpose

**garak** (NVIDIA) is an LLM vulnerability scanner: it fires a catalog of probes (jailbreaks, prompt injection, encoding smuggling, data leak, hallucination) at a model endpoint and reports which prompts made the model misbehave. Reach for it when you want the widest single-pass probe sweep; [[promptfoo]] for a small declarative baseline, [[pyrit]] when single-shot fails and you need multi-turn.

## Install / setup

```bash
python3 -m pipx install garak                    # Kali python is externally-managed
# or a venv (docs: python >=3.11, <=3.13)
python3 -m venv ~/.venvs/garak && . ~/.venvs/garak/bin/activate
python -m pip install -U garak                   # dev: git+https://github.com/NVIDIA/garak.git@main
```

The endpoint is a generator plugin. OpenAI-compatible endpoints use the `openai` type; ollama has a native plugin (chat endpoint is the default, host defaults to `127.0.0.1:11434`); anything else REST goes through the `rest` generator, configured via a YAML file (`uri`, `req_template` with `$INPUT`/`$KEY` placeholders, `response_json` + `response_json_field`, `headers`, `skip_codes`). `litellm` is also a supported backend.

## Core usage

```bash
garak --list_probes                              # full catalog; also --list_detectors, --list_generators

export OPENAI_API_KEY="sk-..."
python3 -m garak --target_type openai --target_name gpt-4o-mini --spec probes.encoding

# ollama (native plugin)
python3 -m garak --target_type ollama --target_name llama3.1:8b --spec probes.encoding
```

Flag names changed: older writeups show `--model_type/--model_name -p`; current syntax is `--target_type/--target_name --spec`.

```bash
# Probe scoping with --spec
--spec probes.encoding          # whole family
--spec probes.dan.Dan_11_0      # single probe
--spec probes.lmrc.SlurUsage    # family.Class syntax
```

## Common use cases

```bash
# Wide jailbreak sweep against a local model
python3 -m garak --target_type ollama --target_name llama3.1:8b --spec probes.dan

# Prompt-injection family (buffed/encoding/promptinject are the usual starters)
python3 -m garak --target_type openai --target_name MODEL --spec probes.promptinject
```

Start with `probes.encoding` (payload smuggled past naive filters), `probes.dan` (jailbreaks), `probes.promptinject` (injection), `probes.lmrc` (risk taxonomy checks); enumerate the rest with `--list_probes`.

## Reading the output

- Each probe prints a progress bar, then one row per detector: unwanted behaviour is marked **FAIL** with a failure rate; the row-end figure (e.g. `840/840`) is generations that behaved OK vs total (default 10 generations per prompt).
- Every run writes a JSONL report (filename printed at start and end); errors land in `garak.log`.
- `analyse/analyse_log.py` ranks the probes and prompts that produced the most hits.
- A FAIL row is a **lead, not a finding**: the scanner proves a prompt class got through, the harness confirmation gate ([[llm-attacks]]) still requires the boundary crossed and captured (Burp Repeater replay, raw request + response pair into `poc/`).

## Tips and gotchas

- Sweeps are loud: 10 generations per prompt across hundreds of prompts. On rate-limited or sensitive scopes scope with `--spec` and expect request counts comparable to a nuclei pass; respect RoE.
- Old `--model_type` references in blog posts silently misroute on current builds; the target/generator rename also renamed `-p` to `--spec`.
- Non-OpenAI JSON APIs: the `rest` generator reads endpoint config from YAML; `$INPUT` is the prompt placeholder and `response_json_field` names the response key (a leading `$` treats it as JSONPath).
- garak probe scenarios can also be driven from [[pyrit]] (`pyrit_scan` lists a `garak` scenario family) when you want them inside a scripted attack run.

## Related techniques

Primary technique page [[llm-attacks]]; payloads in [[llm-prompt-injection]]; model-layer attacks in [[adversarial-ml]]. Siblings in the scanner ladder: [[promptfoo]] (config baseline first), [[pyrit]] (multi-turn escalation last).

## Sources

- NVIDIA/garak README (github.com/NVIDIA/garak; project moved under the NVIDIA org, point pre-move clone remotes at the new URL)
- reference.garak.ai (usage + REST generator reference)
- Generator sources: `garak/generators/ollama.py`, `garak/generators/rest.py`
