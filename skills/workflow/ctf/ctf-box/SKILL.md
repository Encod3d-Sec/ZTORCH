---
name: ctf-box
description: Boot-to-root methodology for a full machine (THM/HTB/PG/CTF), basic-tool recon first, wiki-first, pspy + linpeas/winpeas always. Use when handed a box/IP to own end-to-end ("root the box", "get user.txt+root.txt").
---
state: active
created: 2026-10-12
last_used: 2026-10-12

# CTF / Boot-to-Root Box

Own a whole machine: recon -> service triage -> foothold -> user.txt -> privesc -> root.txt.
**Run everything from the engagement tooling host (e.g. Kali in tmux), capture into `targets/<eng>/`.**

Track progress in `targets/<eng>/Approach.md` -- work the current phase's open items, mark `[x]` as each
lands; honor GATE 1 (no hand-rolled exploit before its wiki item is `[x]`), GATE 2 (no exploit step `[x]`
without a `poc/` image), GATE 3 (exhausted vector -> `[!]` + one `Deadends.md` line, never re-run it).

**Run `python3 scripts/offensive.py next` before every exploit step, and `done` after each lands.** The driver reprints the required posture (msf-shell rule, searchsploit+msf-first, the RTL stop-tells) and is the forcing function now that the drift-guard block is advisory-only - do not free-hand a box off the board.

## Standing mandate: Wiki-first, tools-before-scripts (GATE 1, all phases)

This mandate stands over every phase below. Before writing ANY custom script or recalling an exploit from memory:
1. `qmd_query "<tech/version> exploit"` and `qmd_query "<service> privilege escalation"` via wiki-search MCP. Read matches. If the MCP is down (it drops mid-session), run `bash scripts/wiki-query.sh "<tech> exploit"` (same qmd index; `-k` for an exact CVE) - do NOT skip wiki-first or fall back to grep.
2. Pull payloads from `wiki/payloads/` and chains from `wiki/cheatsheets/attack-chains.md` + `wiki/cheatsheets/cve-arsenal.md`, or `Skill(wiki-arsenal)` to resolve the exact file.
3. Privesc reference: `wiki/techniques/linux/linux-privesc.md` (or windows-privesc).
Only after the wiki has nothing do you write a custom PoC. Do not reinvent what the wiki already documents.

**Tooling home:** check `/opt/arsenal` first for pspy/linpeas/shot/capture. pspy64/linpeas/winPEAS live in `/opt/arsenal`, seeded by `vm-provision.sh` from their GitHub releases; our own helpers (`shot.py`, `capture.sh`) are pushed on demand by `bash scripts/vm-sync.sh <name>` from the vault.

**Version-pinned tooling -> a THROWAWAY docker container, never mutate the VM's runtime.** A tool that needs a specific/older interpreter or an abandoned dependency (e.g. `h2csmuggler` pins the deprecated `hyper` lib and only runs on Python <=3.11; a legacy exploit needs `node:16`) should run inside a disposable container matched to that version, NOT via a host downgrade or a fragile venv that leaves the Kali VM in a broken state for the next box. `docker run -it --rm -v $(pwd):/app python:3.11 bash` (swap the tag: `python:3.9`, `node:16`, ...); `--rm` deletes it the moment you exit, so nothing persists and nothing on the VM breaks. Keep the VM's system python/tooling pristine.

**Anti-pattern:** a raw one-shot `bash /root/vm.sh '<exploit>'` (or an inline `node -e`/`python3 -c` payload through it) for a listener, shell, or chained exploit is the smell this mandate exists to catch -- it skips wiki-first and leaves no session to capture. Run persistent/interactive steps in their own named tmux tab instead: `scripts/vm-scan.sh <eng> <target> '<cmd>'`.

## Phase 1 Recon: basic tools only (in this order)

Use the standard toolkit. Do NOT hand-roll recon scripts.

**Preflight (every engagement, before scanning): prune the tooling VM's `/etc/hosts` and `/etc/krb5.conf` of PRIOR-box entries.** The VM persists across boxes, so a stale `<ip> <domain>/<realm>` line (or a stale `default_realm`) silently mis-resolves this box while nxc/certipy (explicit IP) look fine; impacket Kerberos hangs on a dead KDC instead. `bash /root/vm.sh 'grep -vE "^#|^127\.|^::1|^$" /etc/hosts'`, delete any line not for this box, add only this target; `bash /root/vm.sh 'grep -i default_realm /etc/krb5.conf'`, blank/reset it.

Tooling-first: rustscan/nmap/feroxbuster/ffuf/nuclei/nxc, never a hand-rolled `/dev/tcp` or curl fuzz loop (skips the fingerprint router). **feroxbuster is the DEFAULT web content-discovery tool** (recursive, faster than ffuf/big.txt); launch it the moment nmap shows a web port; ffuf is for param-mining + vhosts.

**Card EVERY scan tab AS it finishes, not at the end:** `scripts/capture.sh recon <eng> <slug> <tab>` renders the tmux tab into `recon/`, rustscan, nmap, feroxbuster, ffuf, nuclei, whatweb (its own tab). Even an empty result gets a card. `status.py` surfaces the recon-card count.

**ONE tmux session per engagement, one WINDOW per parallel scan.** `bash scripts/vm-scan.sh <eng> <target> '<scan>'` for the first, then `--win nuclei`/`--win ferox`/`--win whatweb` for the rest on the same host; never bump the session name to dodge a collision. Screenshot a tab with `Skill(screenshot) --tmux <eng>:<tab>`.

**`vm.sh` drops long foreground commands (exit 255, no output) past ~2 min.** Run scans/cracks/sprays DETACHED (a tmux tab via `vm-scan.sh`, or `nohup <cmd> >/tmp/out 2>&1 &` + poll for a DONE marker), never blocking one `vm.sh` call. Stdin is not forwarded through `vm.sh`; push files via base64 (`echo <b64> | base64 -d > ~/file`), write+run in one call.

**Never `pkill -f <pattern>` with a pattern that also matches your OWN driver/ssh command** - it kills your own tooling (a pattern on the target IP can match the ssh session carrying it).

Basic-tool sweep order (rustscan -> nmap -sCV -> full-TCP confirm -> ferox/nuclei/whatweb in parallel, each scan its own tmux tab + recon card): [[wiki/cheatsheets/recon]] -- never hand-roll it.

**Missing `-w` wordlist = ffuf prints help text and silently finds NOTHING** (a false "no hidden endpoints"). Preflight every fuzz (`ls "$W" || W=/usr/share/wordlists/dirb/big.txt`); seclists may be absent on the VM, push harness lists over via base64 first.

**Slow vs worker-starved, don't conflate them.** Fast HTTP 000 under concurrency (ffuf/sqlmap/parallel scans) = the box is WORKER-STARVED: back off to serial, one request per call, drop fuzzers, let it drain. A request that just never returns = the box is SLOW, not dead: raise the timeout to 120s+ and be patient (a heavy CMS/backend page can take 60-90s). Tell: nmap shows "filtered" but a single `nc`/`curl` connection succeeds = it drops fast-scan probes, switch to gentle serial mode rather than declaring it dead.

**An all-filtered verdict from a NARROW probe is an artifact, not a firewall fact** - and a box's whole purpose can sit on one high port. Only the full sweep (`rustscan -g` / `nmap -p-`) is a verdict; re-run wide before writing a host off ([[wiki/cheatsheets/recon]]).

**Dead-end tells, one probe each:** a DNS server refusing every query except `version.bind` is a stock forwarder (no zones, no intel, move on); loopback redis with `DBSIZE 0` has nothing ([[service-enumeration]]).

**UDP-only services sit invisible under every TCP sweep: SNMP (161), IPMI/BMC (623), TFTP (69).** One `nmap -sU --top-ports 100` per box when the TCP surface looks thin; a guessed SNMP community string (`onesixtyone`) then dumps process command lines with creds in the args, and BMC vendor default pairs are in [[default-credentials]] ([[service-enumeration]]).

**Open 110/143/993/995 (POP3/IMAP) is a loot room, not just a service:** reuse any held cred (`curl -k 'imaps://<ip>' --user <u>:<p>` or `openssl s_client -connect <ip>:imaps`), LIST then FETCH message bodies; mailboxes habitually carry creds and SSH keys ([[service-enumeration]]).

**On any TLS host, dump the cert SANs early**; a hidden vhost that decoy services and ffuf/feroxbuster never surface can be listed only in the Subject Alternative Name, see [[cdn-waf-bypass]].

**On any web surface, before moving to exploitation, all of this, in parallel where possible:**
- **Capture it as-is first**: `capture.sh web <eng> <slug> http://T:PORT/` (browser shot) + `curl -s http://T:PORT/ > poc/<slug>-source.html` (raw source), for EVERY distinct surface (login, dashboards, OSINT/social apps) as you open it.
- **Read full, not grep.** Fetch a file/response (source, config, HLS manifest, JS bundle) and read it END-TO-END; the vuln hides in the line a narrow `grep` skips. Never pipe an exploit/lead response through `head`/`grep` before reading it whole.
- **Exploit requests -> Burp.** curl is fine for quick loops; push every load-bearing request (SSRF/LFI/SQLi/BFLA/deser/flag-returning) into Repeater via `Skill(hunt-burp)`, card with `capture.sh burp`.
- **Source-read primitive first.** The moment you can read files (LFI/.git/backup), read ALL the app source before brute-forcing a login/DB; the vuln is usually in source you can already read.
- **Read the client JS and snippet what it reveals.** Grep bundles for `fetch(`/`axios`/`/api`/`token`/`secret`/`admin`; a JS/SPA's POST-only JSON API is invisible to feroxbuster/ffuf (they GET, a bare `/api` 404s so recursion never descends). The moment source reveals something load-bearing, capture it: `scripts/capture.sh snippet <eng> <slug> <url-or-file> '<pattern>' '<what it reveals>'` -> paste the fenced block into walkthrough.md Recon.
- **Launch scanners in parallel the moment a web port appears**, feroxbuster + nuclei + whatweb, one tmux tab each, don't wait serially; card each on finish. Never conclude "no web vuln" until both feroxbuster and nuclei have run AND been read.

Fingerprint the exact app + version. **`Skill(wiki-arsenal)` FIRST** on any fingerprinted surface (maps it to `wiki/tools/` automation), then INVOKE `Skill(hunt-<class>)` for each fingerprinted vuln class; actually load and follow it, not just the router's advisory nudge (a routed-but-never-invoked hunt skill is drift in eval.md). Record HOW each vuln was discovered, not just the exploit; screenshot findings as they land. **OT/ICS ports (502/102/44818/1880, an HMI web app) -> `Skill(hunt-ics)`.** A web surface -> `scripts/recon-web.sh <eng> <url>` (fans out feroxbuster+nuclei+whatweb+backup-sweep); re-run per new vhost/path, nothing auto-launches it.

## Phase 2 Weaponize: pick the exploit

- **Any fingerprinted admin panel / login: try vendor default pairs from [[default-credentials]] BEFORE brute force or CVE hunting.** A live default pair on a CMS/product admin panel is the instant foothold, and its authenticated features (theme editor, deploy console) are then yours.
- **Version-known -> [[wiki/tools/searchsploit]] AND [[metasploit]] FIRST (the quick-win reflex): run both before hand-rolling or deep-diving a CVE.** Exact commands (`searchsploit <app> <ver>`, `-m`/`-x`/`--nmap`, the `msfconsole -q -x 'search ...'` probe) live in [[wiki/tools/searchsploit]]; the full `search`->`use`->`check`->`run` sequence and DB-backed recon in [[metasploit]]. (GATE 1 still holds: the wiki item for the tech is `[x]` before a hand-rolled PoC - but a canned searchsploit/msf exploit for a known version IS the wiki-blessed tool, use it.)
- **Treat a documented exploit tool as a BLACK BOX: use its interface, do not read its source.** For a known/public tool or PoC (e.g. `[[wp2shell]]`, a searchsploit/msf module, a vendor advisory PoC), drive it through its documented CLI as a trusted reference. Opening a tool's full source to study its mechanics wastes tokens and can stall the engagement on the safety classifier; keep your understanding at the WHAT-it-does / HOW-to-invoke level (its wiki page), not the source level. **When a step needs a PoC pulled from GitHub (or any external exploit fetched/run), pause for the OPERATOR's nudge** - the operator supplies the authorizing context at that point rather than the agent deriving the mechanics itself.
- Pick the payload set from `wiki/payloads/` for the fingerprinted class (GATE 1: the wiki item is `[x]` before you hand-roll a PoC).
- Stage the chosen exploit/PoC into `targets/<eng>/poc/scripts/` before firing, so the code and the run are captured together.
- **A fingerprinted service can expose SEVERAL vuln classes - do not tunnel on the first.** One plugin/app often has an SQLi AND a file-read AND an authed RCE; the intended door is usually the CHEAPEST (a source/config read), not the loudest (a blind SQLi you grind for hours). Two mechanical tells that the vector you picked is the WRONG one - switch it, do not tune the tooling (see `Skill(hunt-core)`'s Stop conditions): (1) **the box starves under your own exploit loop** (repeated `000`/timeout/empty-reply) - a vector that DoSes a lab box is almost never intended; (2) **two verified hashes in a row fail the wordlist** - the passwords are delivered out-of-band (email/note/KeePass/config), so stop cracking and read the app's OTHER surfaces (LFI/source, a second vhost, mail) for where creds are handed out. Re-fingerprint the asset for untested classes (`offensive.py coverage` / `offensive.py board`) before extracting a third hash. When the next door is not obvious, call `Skill(redteamlead)` for wiki-grounded ranked directions with a STOP - one RTL call the moment a vector fights back beats an hours-long sunk-cost grind (do not wait to be told; the box's `/redteamlead` reminder is a real instruction).

## Phase 3 Deliver: land a shell

- **Diagnose target->attacker EGRESS before committing to a shell channel (recurring time-sink).** A connect-back that silently fails is usually a FILTERED egress port, not a broken payload - common C2 ports (4444/1337) are often blocked while 443/80/53/8000 pass. Test it FIRST with one clean single-command probe (a `curl`/`wget` to your listener port, or `bash -c 'echo x >/dev/tcp/<you>/<port>'`) across a couple of ports; if connect-back is filtered, DO NOT grind ports or a reverse shell - pivot to an HTTP-pull + one-shot-webshell/SSH channel (the box's "beacons OUT on a schedule" theme is a literal hint the network is egress-shaped). Deliver the shell payload **base64-wrapped or as a hosted script run via a download cradle**, NEVER a nested-quote `bash -i >& /dev/tcp/...` one-liner through the `vm.sh -> ssh -> --cmd` bridge (the quotes mangle and you cannot tell a dead port from a mangled payload - same delivery discipline as `vm-rsh.sh` for commands).
- Deliver the staged payload/exploit against the target; prefer the documented PoC over a fresh one.
- **Webshell-only channel on a Windows host: stage tools where they survive.** `C:\Windows\temp` is periodically cleaned (binaries vanish) and `certutil -urlcache` is intermittently silent on larger files; stage in a directory the compromised service writes to (e.g. the app server's own webapps tree) via `curl.exe`, hash-verify, and redirect privileged tool output into the served web path to read it back ([[windows-download-and-execute-methods]]).
- **Stabilize EVERY Linux shell the moment it lands** (a raw `nc` shell has no job control, no arrow keys, no tab-complete, and Ctrl-C kills it). Full upgrade ladder (pty.spawn fallbacks, `stty raw -echo; fg` Enter-twice gotcha, TERM, rows/cols, and the authorized_keys skip-the-dance alternative): [[reverse-shells]] TTY Upgrade section. (Windows shells: no PTY dance; grab a proper shell via a C2/`ConPtyShell` or just RDP/WinRM once you have creds.)
- **Catch every reverse-shell pop through `msfconsole` `multi/handler` - never a raw `nc` listener by default.** A raw `nc` PTY has the footgun that `Ctrl-C` kills the LISTENER (dropping the shell back to your own prompt - the false-RCE trap) and needs quoting gymnastics to drive. Default the payload to **meterpreter** (`linux/x64/meterpreter/reverse_tcp` etc.); when meterpreter is blocked or unstable - routine on **Windows/EDR**, where the stager dies but a plain shell survives - fall back to a **plain `shell_reverse_tcp`** payload still caught in `multi/handler` (a bare `nc`/`vm-scan.sh --win shell` listener is the last resort). Meterpreter also gives `autoroute`/`portfwd`/`socks` to reach internal-only ports - use that before hand-rolling SSH `-L` forwards. `msfconsole`/`msfvenom` are on the VM. (An already-interactive SSH/`evil-winrm`/cred session needs none of this - drive it directly.) Drive the whole handler setup + catch through `Skill(metasploit)`.
- **Drive commands into the landed shell (reverse shell or tmux tab) with `scripts/vm-rsh.sh <eng> '<cmd>'`** - it base64-wraps the command so any metachars survive the vm.sh -> ssh -> tmux bridge and returns clean output. NEVER hand-quote `tmux send-keys` + `capture-pane`, or `/dev/tcp` file-transfers, to run commands; that quoting hell is a known repeat drift.
- **On FIRST foothold, stand up ONE persistent multiplexed channel and reuse it.** SSH `ControlMaster`/`ControlPersist` (plus `-L` forwards for internal-only ports), or a reverse shell that survives home-perm resets. Opening a fresh SSH per command through an unstable VPN tunnel was the dominant wall-clock sink on a recent box. See [[pivoting-tunneling]].
- **Cred-reuse FIRST.** Capture creds to `targets/<eng>/loot.md` immediately; try reuse (su / ssh / other services) BEFORE hunting new ones. DB/web creds are very often **reused for SSH**.
  - **Spray EVERY secret you hold against EVERY user x surface, not just the newest one.** The drift: a cred gets written to loot.md, one obvious target is tried, and the rest of the matrix is never run while a fresh privesc vector is ground for half an hour. Re-run the FULL matrix each time a new secret lands. `su` and SSH are NOT equivalent - `PermitRootLogin no` makes `ssh root@` fail while `su root` with the same password succeeds, so a "root: []" SSH result is NOT a negative for root (needs a PTY: `pty.spawn`/`script -qc`).
  - **The leaked config is not the live secret.** An app that does `load_dotenv()` / `os.environ.get(...)` keeps its REAL password in a `.env` beside the source, not in the seeded `.sql`. Read every config the app actually loads, and diff it against what the leak gave you.
  - **Crack the hashes you ALREADY hold before hunting a new vector.** A DB account with `ALL PRIVILEGES` lets you read the DBMS's own account table; a second, otherwise-invisible account there is a deliberate lead. MySQL 8 `caching_sha2_password` (`$A$005$...`) is hashcat `-m 7401` (see [[password-cracking]]) - convert `$A$<iter>$<20-byte salt><43-byte digest>` to `$mysql$A$005*<salt-hex>*<digest-hex>`. A DBMS password is a prime candidate for OS-account reuse.

## Phase 4 Exploit: finish the foothold, then privesc

**RCE-first (impact-first).** When more than one vector is open, take the one that yields code-exec
first - an RCE foothold is the attack vector that carries impact. Grind XSS/IDOR/enum only after
code-exec is ruled out or the objective specifically needs them (the driver now ranks code-exec
classes ahead of access/enum rows).

**Web foothold = STAY in Burp (anti-drift).** If the foothold is an HTTP primitive (RCE/LFI/SSRF/authed
API), the recurring failure is abandoning Burp the instant it lands and scripting the ENTIRE
post-exploitation over raw `curl`/`vm.sh`/urllib - so the operator, who is watching Burp, loses all
visual on the exploitation. Keep the load-bearing follow-ups (the injection that reads user.txt, the
authed call that leaks config, each privesc-relevant fetch) in **Burp Repeater** (native `mcp__burp__*`
first, CLI bridge fallback; `Skill(hunt-burp)`). Quick throwaway enumeration loops over the bridge are
fine; the requests you'd screenshot are not throwaway. See AGENTS.md "Burp-first does NOT stop at foothold".

**STOP-and-think the moment ANY shell lands (before reaching for a shortcut).** The recurring
failure is following the FASTEST path instead of the INTENDED one, then going off the rails. Pause and:
1. Read the box's THEME/name + any notes/creds/files you already have - CTF boxes telegraph the
   intended vector (a module lesson, a service left on, a labelled secret). `qmd_query` the wiki for
   that theme + the exact fingerprinted tech before acting.
2. Enumerate the INTENDED escalation surface FIRST: `sudo -l`, writable configs/cron/timers/scripts
   you own, group memberships, service creds - the deliberate path is almost always one of these and
   `pspy`/`linpeas` surface it in seconds. **When a user is in `sudo`/`wheel` but the password is
   nowhere findable AND cron/writable/SUID/group vectors dead-end, READ `/etc/pam.d/{sudo,su}` and
   `/etc/sudoers.d/*` (not a grep) - a `pam_ssh_agent_auth` (hijack a forwarded agent socket in
   `/tmp/ssh-*/agent.*` -> passwordless sudo), `pam_exec`, or bare `NOPASSWD` line IS the vector; a
   user conspicuously in `lxd`/`docker` that's unreachable is often a DECOY (see [[linux-privesc]]).**
   Read linpeas output WHOLE - the pam/sudoers tell is there but a keyword grep skips it.
3. **Kernel-LPE arsenal (dirtyfrag/copyfail/PwnKit/...) is a LABELLED FALLBACK, not the opening move.**
   We DO carry instant-escalation payloads for old kernels ([[privesc-exploit-arsenal]], [[dirty-frag]]) -
   note the `uname -r` band as a fallback, but VERIFY the intended path is genuinely absent AND verify
   the CVE precondition (userns/module/patch-band) before firing. A shortcut that works is fine; taking
   it BEFORE checking the taught vector is the drift. Once you have full root, look back at what was
   INTENDED and record it (walkthrough + Deadends), so the fast win still teaches the lesson.
   **The confirmed compile-and-run itself** (cross-compile the PoC, deliver it, execute, verify) **is a
   `Skill(delegate)` hand-off** - fully specified once the CVE/precondition is verified, cheap-model-shaped.
   On an active meterpreter session, run `post/multi/recon/local_exploit_suggester` first (via
   `Skill(metasploit)`) to surface the candidate before delegating the run.

Finish the foothold first (leftover Rule 2 techniques, if the shell landed mid-app):
- **Consistent escalation primitive:** if a box exposes the SAME pivot at each stage (a Docker socket/TLS pivot per level, an SSRF each hop), verify/exhaust that intended vector end-to-end BEFORE an opportunistic shortcut (raw device mount, a memory CVE). A shortcut that relies on `--privileged`/a loose cap can mask that a hardened config would block it, and it is less reproducible/auditable. Getting the flag via a shortcut is fine; SKIPPING the taught vector without testing it is the miss.
- Web SQLi: in-band (UNION/error) before blind; test EVERY quote context (`'` `"` numeric) and second-order (a stored value used unsafely on another page). If the app hashes the password inside the query, read plaintext from `information_schema.PROCESSLIST`. Load `Skill(hunt-sqli)` / see [[sql-injection]].
- Recovered unsalted MD5/SHA1: **online lookup first** (CrackStation/hashes.com) before hashcat/john. A hash that resists everything on a hard box may be a deliberate decoy; pivot, don't grind.
- **A custom binary that signs its own protocol (HMAC/token): decompile the KEY SCHEDULE before brute-guessing key/message combos.** When an implant/agent/updater HMACs its IPC/C2 and the key is derived from readable material (a `.rodata` blob, a PRNG pad with a hardcoded seed, `/etc/machine-id`), reproduce the derivation offline (the derivation functions are usually tiny) and VERIFY against one captured live signature, then forge - do not spend rounds guessing `blob`/`machine-id`/`HMAC(blob,mid)` permutations. Recognize the glibc `rand()` LCG (`*0x41c64e6d + 0x3039`, byte `(state>>16)&0xff`). See [[cryptography-attacks]] "binary signed-protocol forge".

Then privesc = pspy ALWAYS + linpeas/winpeas, then manual. **Run a long tool reliably with
`bash scripts/vm-bg.sh <eng> <win> '<tool>'`** - it stages the tool to `/dev/shm`, runs it inside the
stabilized tmux shell (line-buffered to a `/dev/shm/*.log`), and you `--read` / `--wait 120` the
logfile. Never hand-roll a backgrounded watcher over the one-shot SSH bridge (it gets reaped / `tee`
buffers), and never retry a broken tool-execution pattern >2x - switch method (vm-bg) or
`Skill(redteamlead)`. See [[pspy]] / [[linpeas]].

**pspy shows exec/process events, NOT unix-socket/IPC beacons.** If the privesc lead is an internal listener/socket (a service "talking to itself" on loopback), RE and interact with THAT directly - do not grind pspy or stage linpeas for a socket-protocol vector they cannot see. Run pspy when the suspected vector is cron/timer/exec.

pspy ALWAYS + linpeas/winpeas before any manual check -- invocation, flags, and the small-RAM linpeas gotcha: [[pspy]] / [[linpeas]] / [[peass]].

Capture linpeas/pspy TWO ways: a `--term` screenshot of the highlighted findings (Skill(screenshot),
the colored hits survive) AND the FULL text log - redirect the tool to a file, then
`scripts/capture.sh log <eng> <slug> /tmp/linpeas.txt` pulls the whole scan (ANSI stripped) into
`poc/NN-<slug>.md`. The screenshot is unreadable past one screen; the `.md` keeps every line so you
(and the operator) can grep it later. Do this for full nmap output too when it is long.

**Read-whole is not just for recon: grep is NOT the read for PAYLOAD RESULTS or pspy/linpeas output either.** A UNION/echo dump can reflect in an unexpected phrasing (singular "1 word" vs plural "N words"), and a root cron hides in the full pspy stream; read the whole result block, not a keyword grep.

Walk the full manual checklist ([[linux-privesc]] Quick wins) -- the box's intended path is usually ONE of those rows; do not skip any.

**Windows runs the same manual discipline off [[windows-privesc]] (winpeas + `whoami /priv` first).** Key shape the Linux table has no row for: a writable service-binary directory + a LocalSystem AUTO_START service you cannot start/stop = trigger execution with a REBOOT (SeShutdownPrivilege); a vendor repair watchdog can revert the swap, so re-arm and issue the reboot in the SAME action ([[wiki/cheatsheets/windows-privesc]]).

Box-specific chains now live in wiki (see the technique pages linked per class on the hunt skills' Wiki maps).

**Don't assume the flag path** (e.g. `/root/root.txt`); once you have exec, `find` it - the root flag can live at a non-standard path, and the USER flag has TWO conventions (`/user.txt` at the filesystem root AND `/home/*/local.txt`): check both before declaring one absent.

## Capture (engagement discipline)

After each phase, write to `targets/<eng>/`: hosts/access -> `state.md`, creds -> `loot.md`, chain -> `state.md`'s `## Chain` section, vulns -> `Vuln-index.md`, dead-ends -> `Deadends.md`, narrative -> `walkthrough.md` (at close-out). Flags go in the writeup, never in `session/*` or `wiki/`.

**Board hygiene, live (GATE 3).** `state.md`'s `## Chain` section and `Deadends.md` rot under momentum while other state.md prose absorbs the narrative instead; the instant a vector (a potato variant, a kernel CVE, a cred spray) is exhausted, append ONE `Deadends.md` line + set its status in `state.md`'s `## Chain` BEFORE trying the next. `status.py` shows board phase + deadend count to spot the drift.

**Live-capture machinery; evidence is never backfilled at close-out:**
- **Auto-card is a backstop, not primary.** The Stop hook (`scripts/autocard.sh`, capped `AUTOCARD_MAX=2`/run) renders any finished scan tmux tab into `recon/`; hand-carding as you go (Phase 1: `capture.sh recon <eng> <slug> <tab>`) stays PRIMARY. 0 cards while tabs finished = VM down / `timeout` missing; hand-card now.
- **Hand-card exploit-state shots** (the flag, the RCE firing, an authed panel) the moment they land; persist to `state.md`/`loot.md` immediately, never deferred.
- **A PoC card is ONE human-authored command**, concrete values, full paths, NO `export`/`$VAR`, NO `;`/`&&`-chains, NO echo banners, NO base64/pty wrappers. Re-run the clean single command for the capture even if a messy pipeline was needed to work the box (that stays in `poc/scripts/`).

**`walkthrough.md` (assembled at close-out) is the narrative** and the clean human version (concrete one-liners, no `$VAR`s); the messy automation (base64 wrappers, pty helpers) stays in `poc/scripts/`.

**Read UI/source hints literally before fuzzing.** A placeholder, button label, or leaked source usually states the intended input format directly; do not default to injection-fuzzing a field that already told you its format.

**Locally-substituted payloads = false-positive RCE.** `$(...)`/backticks/`$VAR` sent through the VM bridge or any local shell get substituted LOCALLY before reaching the target, and the tooling VM runs as root; a reflected `uid=0` may be YOUR box. Always single-quote or base64 injection payloads; confirm execution with a target-only marker (hostname, a file only it has) before claiming RCE.

**Preserve exploit scripts and source reads.** Copy any exploit script or read target source into `targets/<eng>/poc/scripts/`, saved as `<name>.md` with a fenced code block (`sh`/`js`/`py`/`html`), NOT a bare `.sh`/`.js`/`.py`, since Obsidian only previews `.md`/images. `capture.sh snippet <eng> <slug> <url-or-file> '<pattern>' '<reveals>'` for a targeted excerpt.

**Video/media -> mp4 into `poc/` early.** `ffmpeg -i <in> -c copy poc/<slug>.mp4`, then hand it to the operator; a visual puzzle (shoulder-surf, on-screen code) is far cheaper read by a human than brute-analyzed frame-by-frame; frame extraction/OCR is the fallback, not the opening move.

**Screenshot every successful step live, not at the end.** Capture EACH privilege milestone (foothold / user / operator / root) the MOMENT it lands - a fast box is not an excuse to defer capture to walkthrough time (a transient exploited state may not be re-shootable, and backfilling evidence is the documented drift). No auto-capture net exists; `scripts/capture.sh` (`ev`/`req`/`tmux`/`burp`) captures straight into `poc/` the moment a step lands. `capture.sh ev <eng> <slug> "<url>" "<cmd-label>"` for a one-call output+request card; `capture.sh req <eng> <slug> -- <curl-args>` for a full request/response card; `capture.sh tmux` for a session card; `capture.sh burp` for a Repeater PoC. `Skill(screenshot)` covers authed/exploited GUI states. Never hand-write a `--term` card (fabricated evidence); `tee` real output into the pane if it was redirected to a file. `python3 scripts/build-walkthrough.py <eng>` auto-populates the `## Evidence` gallery from every `poc/` card.

**Grow the harness wordlist.** A non-obvious route/param that cracked the box -> `python3 scripts/wordlist-suggest.py` (leak-safe) then `scripts/wl-add.sh paths <token>` / `wl-add.sh params <name>`, generic methodology names only, never client branding.

**Leave-no-trace at close-out (pentest/real engagements only; optional on CTF/lab).** Before marking a real engagement done, remove what you dropped on the target: planted SSH keys in `authorized_keys`, uploaded tools (pspy/linpeas/webshells) in `/tmp` `/dev/shm` `/var/www`, staged exploit scripts, and any throwaway account you created. Track droppings as you plant them so cleanup is a checklist, not a memory test. (On a CTF this is optional - note it, don't grind.)

## Context tools

<!-- auto-wired: documented tools to reach for; do not hand-roll -->
- [[wiki/tools/nmap]]
- [[wiki/tools/rustscan]]
- [[naabu]]
- [[wiki/tools/ffuf]]
- [[wiki/tools/feroxbuster]]
- [[gobuster]]
- [[wiki/tools/nuclei]]
- [[nikto]]
- [[wiki/tools/whatweb]]
- [[wiki/tools/arjun]]
- [[dalfox]]
- [[wiki/tools/swaks]]
- [[wiki/cheatsheets/recon]]
- [[nuclei-arsenal]]
- [[wordlists]]
- [[network-service-attacks]]
- [[linux-enumeration]]
- [[windows-enumeration]]
- [[windows-privesc]]
- [[password-attacks]]
- [[wiki/tools/sqlmap]]
- [[pivoting-tunneling]]
- [[web-client-attacks]]
- [[metasploit]]
