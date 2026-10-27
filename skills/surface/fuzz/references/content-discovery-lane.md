---
name: content-discovery-lane
description: Archetype brief for a bounded custom-wordlist content-discovery lane (calibrate, run detached, judge from JSON, classify, hand off). Copy per host, fill the placeholders.
---

# Content-discovery lane archetype (custom wordlist)

Copy this skeleton into the lane brief (`targets/<eng>/poc/<host>/<lane>-brief.md`)
and fill every `<placeholder>` (backticked in the brief too; Obsidian-safe rule).

## Standing rules (carry verbatim into every lane brief)

- Read-first mandate: `cat` each file you read in full, zg/grep only to locate.
- Obsidian-safe: any `<token>` written into a `.md` is wrapped in inline backticks.
- All traffic through the engagement proxy per RoE (UA tamper rule); never bypass it.
- Stealth profile, one host at a time, GET only, no logins, no writes.
- Request cap for the whole lane (calibration + runs) stated up front.

## 1. Wordlist (compose mode, NOT a stock directory list)

Per host, from the fingerprint in `state.md`:

```
bash scripts/wl-pick.sh compose <fingerprint> <etype> [stems-file] [cap]
```

- `<fingerprint>`: the host's tech fingerprint; unknown keys fall back to the
  generic theme.
- `<stems-file>`: optional, one route per line from the JS corpus
  (`endpoints.jsonl` parent dirs land in the list automatically).
- Theme matrix (config-exposure: actuator, `_profiler`, `.env` variants,
  `parameters.yml`, secrets/backup files, ...) comes FIRST; it beats directory
  lists on requests-per-finding by orders of magnitude.
- Record the composed list verbatim in the `cap-00` capture card.
- Edge-blocked shapes: after the main run, ONE bounded variant pass via
  `python3 scripts/wl_mutate.py <base-list>` (null byte, double encoding,
  overlong UTF-8, case, trailing junk, path-param). Never a second full pass.

## 2. Calibration (before each host)

2-3 known-bogus paths (`/zz-bogus-<rand>1..3`); read status/size/words, then set
`-fs`/`-fw` on the catch-all baseline or `-mc` on a clean 404. Record baselines.

**Catch-all rule:** any host whose bogus probes return a uniform same-size 200
(SPA shell) is BLIND for content discovery: stop that host after calibration and
say so in the envelope. Its surface lives in the JS corpus, not the path space.

## 3. Execution

- Fuzzer detached (vm-scan / tmux), `-o json` output, `-ac` first then explicit
  filters per calibration.
- Judge ONLY from the JSON parsed programmatically, never from live log bodies.
- EXIT-trailer polling: wait on the run's exit line, not on silence.
- Backoff ladder: 429/`Retry-After` -> halve rate once; sustained timeouts or a
  uniform-403 wall (ban tell) -> HARD STOP that host, record, move on.

## 4. Triage classes (per result row)

| class | tell | verdict |
|---|---|---|
| edge/WAF block page | fixed size, md5 matches the engagement's block-page class | terminal-DENIED, never a hit; variants get the one bounded pass |
| SPA shell | catch-all baseline bytes | false, drop |
| framework error envelope | host's known 404/406 JSON/HTML shape | false, drop |
| content | anything else (config text, listing, swagger JSON, real doc) | HIT |

HIT: full raw pair to the VM tmp dir + capture card. DO NOT self-exploit; flag
the row in the envelope as a hunt-lane candidate (the brain dispatches
`Skill(<hunt-*>)` from the queue, never the discovery lane).

## 5. Deadends (per tier)

Close each host's run with a `Deadends.md` row (`asset x content-discovery`,
what was tried, requests fired, reopen-if: fingerprint change or new corpus
stems), or the hit rows in `Approach.md` 4a.

## 6. Envelope back (single message)

- verdict per host: CLEAN / BLIND / HITS (host, path, what it is, cap path)
- requests fired, rate used, backoff/ban events
- wordlist sizes, one-line deviations

## Brain dispatch-queue row shape

```
[ ] <host>: content-discovery (compose wl, fingerprint <fp>, stems <yes/no>) -> Skill(fuzz) archetype references/content-discovery-lane.md
```

Driver `next` may propose this row after any fingerprint lands on a host with
no content-discovery Deadends row.
