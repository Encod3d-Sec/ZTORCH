---
title: "wp2shell"
type: tool
tags: [wordpress, sqli, rce, webshell, exploitation, tool, web]
date_created: 2026-08-20
date_updated: 2026-09-15
sources: [gh-icex0-wp2shell]
phase: exploit
---

## Purpose

`wp2shell` is a standalone PoC that chains a **WordPress REST batch route-confusion SQL injection**
into an administrator account, then deploys a webshell plugin for command execution as the web user.
It automates the full path from an unauthenticated (or low-privilege) WordPress target to RCE.

Reference / source: https://github.com/Icex0/wp2shell-poc

> Reference entry only. This page documents WHAT the tool does and HOW to invoke it, not the
> exploit internals (the SQLi primitive, the plugin webshell source). Read the repo for those.

## When to reach for it

- A WordPress target where the version fingerprint is old/spoofed and the REST API is reachable.
- You already hold WordPress admin creds and want a one-command webshell (it also supports an
  authenticated `shell` mode, not just the pre-auth bridge).
- Fingerprint via [[wiki/tools/wpscan]] first; if the build is in range, `wp2shell` is the quick-win RCE.

## Install / setup

```bash
git clone https://github.com/Icex0/wp2shell-poc /home/kali/wp2shell-poc
cd /home/kali/wp2shell-poc
python3 wp2shell.py --help
```

## Usage

```bash
# confirm the vulnerability (non-destructive), single URL or a file of URLs
python3 wp2shell.py check http://target

# read from the DB via blind SQLi
python3 wp2shell.py read http://target

# RCE: with admin creds, or via the pre-auth bridge (omit --user/--password to use the bridge)
python3 wp2shell.py shell --user <admin> --password '<pass>' --cmd 'id; hostname' http://target
python3 wp2shell.py shell -i http://target            # interactive shell after deploy
```

## Notes / gotchas

- **Version gate before firing (affected ranges only).** The chain applies to WordPress 6.9.0-6.9.4 and 7.0.0-7.0.1; fixed in 6.8.6 / 6.9.5 / 7.0.2 and the 7.1 line (Beta 2 onward). Pin first (wpscan `--random-user-agent` upgrade-page `?ver=` vectors survive generator/readme stripping) and cross-check with the **REST route floor**: `/wp-json/` routes that only exist in given core versions bound the version with zero extra requests (Font Library `/wp/v2/font-families` = 6.5+; `wp-abilities/v1` = 6.9+; `/wp/v2/icons` + `/wp/v2/icon-collections` + `/wp/v2/view-config` = 7.1+). A route-floor pin above the affected range closes the finding without sending an exploit-shaped packet. Presence of `/batch/v1` alone proves nothing - it ships with every WP since 5.6.
- **Edge/WAF 403s on the entry forms drift.** A 403 observed on the batch POST forms on day 1 (edge or origin RASP) may not reproduce days later; re-test before citing a transport mitigation as persistent, and distinguish layers via headers (`x-rasp-block`/origin markers vs a bare edge block page).
- The `shell` mode deploys a webshell **plugin that self-cleans after each `--cmd`** - each
  invocation is one-shot (fine for enumeration; for a persistent session, drop an SSH key or a
  reverse shell from within the first `--cmd`).
- Default request `--timeout` (15s) is often too short on a loaded target; pass `--timeout 60`.
- The bridge/`shell` mode creates a throwaway admin (e.g. `wp2_<hex>`); note it for cleanup.
- WordPress `http-generator` version can be **spoofed** - do not trust it; if `wp2shell check`
  confirms, the build is vulnerable regardless of the advertised version.

## Related

- [[wiki/tools/wpscan]] - fingerprint users/plugins/version first.
- [[sql-injection]] - the underlying injection class.
- [[file-upload]] / webshell delivery - the RCE stage.
- WordPress post-ex: DB creds in `wp-config.php`; **check for non-standard `wp_*` tables** (custom tables often hold infra/SSH creds).

## Core usage

Authenticate as an admin and drop a webshell to run a command:

```bash
python3 wp2shell.py shell --user <admin> --password '<pass>' --cmd 'id; hostname' http://target
```
