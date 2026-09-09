---
title: "llm-guard"
type: tool
tags: [llm, ai, scanner, prompt-injection, defence, web]
date_created: 2026-09-09
date_updated: 2026-09-09
sources: [git-llm-guard]
phase: exploit
---

## Purpose

**llm-guard** (Protect AI) is a scanner framework wrapped around an LLM call: input scanners
sanitize the prompt before the model, output scanners screen the response after. The repo is now
archived upstream (README carries an ARCHIVED banner; bundled models unmaintained), but it remains
the cleanest published taxonomy of LLM guardrail scanner classes, which makes it equally the
attacker's map of what sits in front of a target: 15 input + 20 output scanner classes. Read the
class names off a target's behavior, then pick the matching evasion from [[llm-prompt-injection]].

## Install / setup

```bash
pip install llm-guard        # Python 3.9+; heavy per-scanner deps (torch, transformers, NER) install on first use
```
Online playground for scanner behaviour without wiring it up:
huggingface.co/spaces/ProtectAI/llm-guard-playground.

## Core usage

```python
from llm_guard import scan_prompt, scan_output
from llm_guard.input_scanners import Anonymize, Toxicity, TokenLimit, PromptInjection
from llm_guard.output_scanners import Deanonymize, NoRefusal, Relevance, Sensitive
from llm_guard.vault import Vault

vault = Vault()
input_scanners = [Anonymize(vault), Toxicity(), TokenLimit(), PromptInjection()]
output_scanners = [Deanonymize(vault), NoRefusal(), Relevance(), Sensitive()]

sanitized_prompt, valid, scores = scan_prompt(input_scanners, prompt)
sanitized_output, valid, scores = scan_output(output_scanners, sanitized_prompt, response_text)
```
`Anonymize`/`Deanonymize` share one `Vault` so entities redacted on input can be restored on
output; `scan_output` takes the sanitized prompt as context for relevance/consistency checks.

## Scanner taxonomy (know which scanner you are evading)

Input scanners:

| scanner | what it blunts (attack class) |
|---|---|
| Anonymize | PII handling in the prompt (redacts entities before the model sees them) |
| BanCode | code smuggled into prompt text |
| BanCompetitors | competitor-mention prompts |
| BanSubstrings | blocklist string matches (payload splitting / fragmentation) |
| BanTopics | topic classifier (violence, self-harm framings) |
| Code | code-detection prompts |
| Gibberish | noise carriers; heavy context-flooding shows up as gibberish-heavy input |
| InvisibleText | zero-width / BiDi / hidden-Unicode carriers |
| Language | multilingual evasion pinned to one language |
| PromptInjection | on-device classifier for direct/indirect injection phrasings |
| Regex | custom patterns (known payload strings) |
| Secrets | secrets (keys, tokens) pasted into the input |
| Sentiment | emotional-manipulation framings at the extremes |
| TokenLimit | context flooding above a size cap |
| Toxicity | toxic-language framings |

Output scanners:

| scanner | what it blunts |
|---|---|
| BanCompetitors / BanSubstrings / BanTopics / BanCode | same classes as input, on the reply |
| Bias | biased completions |
| Deanonymize | restores vault-redacted entities (pairs with Anonymize) |
| JSON | non-conforming structured output |
| Language / LanguageSame | wrong-language or language-switching output |
| MaliciousURLs | exfil links in the reply |
| NoRefusal | refusal phrasings; flags jailbreak-success markers |
| ReadingTime | oversized output (cost/DoS) |
| FactualConsistency | hallucinated claims vs the prompt |
| Gibberish | degenerate output |
| Regex | custom output patterns |
| Relevance | off-topic drift (goal redirection residue) |
| Sensitive | PII leakage in the reply |
| Sentiment / Toxicity | tonal classes |
| URLReachability | dead links in output |

Evasion notes by scanner family:

- **Classifier scanners** (PromptInjection, Toxicity, BanTopics, Bias, Gibberish, Sentiment): semantic camouflage, math abstraction, encoding wrappers, and non-English phrasing shift the input off the training distribution and drop classifier confidence.
- **Regex / blocklist scanners** (BanSubstrings, Regex, Secrets): variable fragmentation, leetspeak, homoglyphs, and cross-turn payload splitting defeat contiguous matching. InvisibleText closes the pure zero-width route, so prefer fragmentation over hiding.
- **NoRefusal on output is also an oracle for the attacker**: it pattern-matches refusal phrases, so a multi-turn ladder has landed when refusal-shaped replies stop appearing, and its phrase-based nature means a rephrased refusal evades it while still blocking progress.
- **Language/LanguageSame**: caught only by pinning a language; mixing languages mid-conversation slips per-call checks.
- **MaliciousURLs / URLReachability**: route exfil through an allowlisted redirector or a non-URL side channel instead of a bare link.
- **TokenLimit / ReadingTime**: flooding under the cap still biases classifiers without tripping the limit.

## Tips and gotchas

- Archived upstream: treat a passing llm-guard config as a data point, never as a control claim in a report without the archive caveat.
- First use of a scanner downloads on-device models (injection classifier, NER, toxicity); pre-stage them on offline boxes.
- The scanner list is a latency stack; a full input+output chain adds seconds per request, which is itself a fingerprint (slow first token + uniform scan latency).
- Scores are per-scanner (`valid`, `scores`); a scanner tripping on benign input is the signal the target tuned thresholds loose, which maps directly to which evasion headroom you have.

## Related techniques

[[llm-attacks]] for mechanisms; [[llm-prompt-injection]] and [[mcp-tool-poisoning]] for the payloads
these scanners try to catch; [[agentdojo]] to score attack-vs-defense pairs; offensive scanner
siblings [[garak]], [[promptfoo]], [[pyrit]].

## Sources

- protectai/llm-guard README, docs nav (mkdocs.yml), examples/openai_api.py
- protectai.github.io/llm-guard (scanner reference)
