---
name: fuzz
description: Adaptive web fuzzing - deterministic wordlist pick (wl-pick.sh), tier climbing, WAF handling. Use for "fuzz", "content discovery", "directory brute", "vhost fuzz", "find hidden params", "which wordlist", "gobuster/ffuf/feroxbuster".
---

# fuzz - adaptive web fuzzing

## 0. Profile (do this first)
Read `engagement_type` from the active `targets/<eng>/state.md` frontmatter and set the profile:
- **ctf** - loud/fast, ignore WAF, recurse deep, exhaust the big list.
- **pt** - calibrated rate, obey RoE flags (`no_bruteforce`/`no_dos` -> SKIP the brute tiers entirely).
- **bb** - stealth: low rate + jitter, watch for the ban BEFORE it lands, request-budget aware.
`wl-pick.sh` emits the profile flags; you apply them.

## 1. Two axes
- **Surface (widen):** content, files, vhost (Host-header fuzz against one IP; catches hosts with no DNS record), api, artifacts. Recursive by default.
- **Parameter (deepen):** once an endpoint takes input, fuzz hidden params. Triggered by OBSERVING a param-accepting endpoint, never blind.

## 2. Select (deterministic) - always via wl-pick.sh
```bash
# what to run for a surface, given the engagement type and any fingerprint:
bash scripts/wl-pick.sh content "" ctf          # generic content discovery
bash scripts/wl-pick.sh content wordpress bb    # WordPress-aware, BB-stealth
bash scripts/wl-pick.sh vhost "" pt
bash scripts/wl-pick.sh params "" bb
```
It prints the seclists base, the profile flags line, and the ordered absolute paths (T0 harness -> T3 fingerprint list -> T1 surface lists, size-ordered). NEVER hand-pick a list from memory and NEVER start with `directory-list-2.3-medium` (220k). The size order is already correct in the output; run top-to-bottom, stop climbing when you have enough signal.

## 3. Calibrate (native first, backstop with judgment)
- Launch every fuzz run detached in its own tmux tab: `bash scripts/vm-scan.sh --win ffuf <eng> <target> '<cmd>'` (output stays in-pane, autocard cards it; a foreground run dies with the SSH round trip).
- Default to ffuf `-ac`/`-acc` and feroxbuster auto-filtering.
- If a wildcard/soft-404 fools `-ac` (everything returns 200 with varying size): fire 2-3 known-bogus random paths first, read status/size/words, then set explicit `-fs`/`-fw` on the catch-all baseline, or `-mc 200,301,302,401,403` on a clean 404.
- Uniform catch-all (every path returns the same-size SPA index): content fuzzing is BLIND on that host; stop after calibration and mine the JS bundle for the real surface instead ([[api-testing]]).
- VHost fuzzing is the extreme catch-all: the server answers EVERY Host value, so filter on the default-site baseline size (`-fs`), never on status code ([[wiki/tools/ffuf]]).
- READ tool output END-TO-END, never a grep. A real hit hides in the noise.

## 4. Climb tiers on SIGNAL (the adaptive core)
Climb T0 -> T1 -> T2 -> T3 when the current tier is exhausted OR a fingerprint unlocks a better list:
- **T2 cewl** when T0/T1 run dry: `cewl -d 3 -m 5 --lowercase -w targets/<eng>/custom-words.txt https://TARGET` then feed that list back through the same axis. See [[cewl]].
- **T3 app-specific** the moment you fingerprint a known product: re-run `wl-pick.sh <surface> <product> <type>` to jump straight to its shipped list. For a product with no shipped list, `Skill(wiki-arsenal)` for its known paths, then cewl its docs / probe `robots.txt` `sitemap.xml` `swagger.json` `openapi.json`.
- Every vhost hit is a fresh docroot: re-run the content axis against it (its `robots.txt` Disallow entries are a free wordlist) before climbing further.

## 5. Pivot to the parameter axis
Extension fuzz BEFORE page fuzz: probe `indexFUZZ` against `web-extensions.txt` (entries already include the dot) to learn the stack, then page-fuzz with `FUZZ.<ext>`; on param mines run GET and POST both, a deprecated GET hit means keep going to POST ([[wiki/tools/ffuf]]).
When a discovered endpoint takes input, fuzz hidden params: `arjun -u https://TARGET/endpoint` (see [[wiki/tools/arjun]]) or ffuf with `bash scripts/wl-pick.sh params`. Discovered params feed the hunt-* skills (SSRF/LFI/IDOR/cmdi).

## 6. WAF / throttle / Cloudflare
Detect: `wafw00f`/`whatwaf` up front; headers `cf-ray`/`server: cloudflare`/`x-sucuri`/`x-datadome`/`incapsula`; mid-run `429`+`Retry-After`, climbing latency, `000`/timeouts, a wall of uniform `403`.
Respond, in order:
1. **WAF fingerprinted up front** -> stealth posture regardless of profile, and PREFER BYPASS over throttle: find the origin IP (cert SANs, historical DNS) and fuzz origin directly - see [[cdn-waf-bypass]].
2. **Throttle mid-run** -> auto-backoff: halve rate, add `-p 0.1-2.0` jitter, drop one size-tier.
3. **Ban / DoS tell** (sustained all-timeout after a burst) -> HARD STOP, do not grind: stop fuzzing the host and call `Skill(redteamlead)` for a re-vector rather than tuning the tooling.
4. **RoE** `no_bruteforce`/`no_dos` -> skip the brute tiers; scope-guard also enforces this at the Bash layer.

## 7. 403 is not a dead end
A `403` on a discovered dir is a signal, not an end. Try bypass BEFORE abandoning: path mutations (`/admin/`, `/admin/.`, `/admin/..;/`, `/%2e/admin`, case, trailing `?`), method swap (`GET`->`POST`/`HEAD`/`TRACE`), and header spoofs (`X-Forwarded-For: 127.0.0.1`, `X-Original-URL`, `X-Rewrite-URL`). Use a dedicated tool (`byp4xx`/`nomore403`) rather than a wordlist - 403 bypass is mutation, not brute. See [[cdn-waf-bypass]].

## Wiki
Tools: [[wiki/tools/ffuf]] [[wiki/tools/feroxbuster]] [[wiki/tools/cewl]] [[wiki/tools/arjun]]. Reference: [[wordlists]] (the selection matrix, human-readable twin of wordlist-map.json), [[cdn-waf-bypass]] (WAF/origin bypass). Stuck -> Skill(redteamlead).
