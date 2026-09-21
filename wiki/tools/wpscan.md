---
title: "WPScan"
type: tool
tags: [brute-force, enumeration, scanner, thm, tool, web]
date_created: 2026-05-08
date_updated: 2026-09-15
sources: [thm-tool-wpscan]
phase: enumerate
---

## Purpose

WPScan is a WordPress-specific black-box security scanner that enumerates users, plugins, themes, and known vulnerabilities, and can perform credential brute force attacks against WordPress login and XML-RPC.

## Install / setup

```bash
# Install via RubyGems
gem install wpscan

# Or update existing install
gem update wpscan

# On Kali Linux (usually pre-installed)
sudo apt install wpscan

# Get a free API token (25 requests/day) at https://wpscan.com/register
# Add to ~/.wpscan/scan.yml or pass as flag
```

## Core usage

```bash
wpscan --url http://TARGET/wordpress [options]
```

| Flag | Description |
|---|---|
| `--url` | Target WordPress URL (required) |
| `-e u` | Enumerate users |
| `-e p` | Enumerate installed plugins |
| `-e t` | Enumerate installed themes |
| `-e vp` | Enumerate vulnerable plugins (requires API token) |
| `-e vt` | Enumerate vulnerable themes (requires API token) |
| `-e ap` | Enumerate all plugins |
| `-e at` | Enumerate all themes |
| `-U user` | Specify username(s) for brute force |
| `-P /path/wordlist` | Password wordlist for brute force |
| `--api-token TOKEN` | WPVulnDB API token for CVE data |
| `--plugins-detection aggressive` | Use aggressive detection mode (more requests, finds more plugins) |
| `--detection-mode passive` | Passive only — minimal footprint |
| `-o output.txt` | Write results to file |

## Common use cases

### Full passive enumeration

```bash
wpscan --url http://blog.thm -e | tee wpscan.initial
```

### Enumerate users

```bash
wpscan --url http://blog.thm --enumerate u
# Finds users from: author pattern, WP JSON API, login error messages
```

### Enumerate plugins and cross-reference CVEs

```bash
# Requires API token — check plugins for known vulnerabilities
wpscan --url http://target.thm --enumerate vp --api-token YOUR_TOKEN
```

### Enumerate themes

```bash
wpscan --url http://target.thm --enumerate t
# Detects active theme by reading wp-content/themes/ URL references
# Theme version extracted from README.txt or style.css
```

### Brute force WordPress login

```bash
# Single user
wpscan --url http://target.thm --usernames admin --passwords /usr/share/wordlists/rockyou.txt

# Multiple users (from enumeration output)
wpscan --url http://target.thm -U kwheel,bjoel -P /usr/share/wordlists/rockyou.txt
```

### Aggressive plugin detection (bypass WAF noise concern)

```bash
# Aggressive mode sends more requests but finds plugins that passive misses
wpscan --url http://target.thm --enumerate p --plugins-detection aggressive
```

### Save output to file

```bash
wpscan --url http://target.thm -e u,p,t -o wpscan_results.txt
```

### Pin the WordPress core version (the pinning ladder, hardest first)

```bash
wpscan --url https://TARGET --random-user-agent --enumerate p,t
```

Ladder, stop at the first rung that pins: (1) `readme.html` root version stamp; (2) `<meta name="generator">` on the homepage; (3) `<generator>` element in `/feed/`; (4) wpscan's **upgrade-page CSS vectors** - `wp-includes/css/*.min.css?ver=N.N` files referenced from the upgrade/404 pages (aggressive detection) - this rung survives hardened estates that strip 1-3; (5) hash-style `?ver=` on dist scripts gives only a build floor. Cross-check any pin with the **REST route floor** (see Notes in [[wiki/tools/wp2shell]]): routes that exist only in specific core versions (e.g. Font Library routes = 6.5+, icons/view-config = 7.1+) bound the version from the `/wp-json/` index alone, independent of wpscan.

## Tips and gotchas

- **WAF/edge-fronted estates 403 the default user agent** (and whatweb sees nothing at all - absence of WordPress in whatweb output is a tool limitation, not evidence). Re-run with `--random-user-agent`; wpscan aborts with "The target is responding with a 403, this might be due to a WAF" until you do.
- **`--enumerate v` is not a valid choice** in current builds ("Scan Aborted: --enumerate Unknown choice: v") - version detection is automatic, enumerate p,t alongside it.
- **XML-RPC**: WPScan will flag `xmlrpc.php` if enabled. This endpoint allows brute force even if `wp-login.php` is rate-limited or blocked. Use Metasploit `auxiliary/scanner/http/wordpress_xmlrpc_login` or a custom script to abuse it.
- **API token**: Without an API token (`--api-token`), WPScan will enumerate plugins/themes but will not report associated CVEs. Free tokens allow 25 lookups/day at wpscan.com.
- **Plugin versions**: WPScan reads `README.txt` files in `/wp-content/plugins/PLUGIN/` to determine version. If directory listing is disabled and README is absent, version may be unknown.
- **Detection modes**:
  - `passive` — reads only what's in the page HTML/headers
  - `mixed` (default) — passive + some aggressive requests
  - `aggressive` — many requests; noisy but thorough. Set with `--plugins-detection aggressive` or `--themes-detection aggressive`
- **Add hosts file entry** if the WP site is virtualhost-based: `echo "IP hostname" >> /etc/hosts`
- **User enumeration technique**: WPScan detects users from author archive URLs (`/?author=1`), WP JSON API (`/wp-json/wp/v2/users`), and login error message differences.

## Related techniques

- [[cms-exploitation]] — WordPress admin panel RCE via theme editor, plugin upload
- [[cms-exploitation]] — xmlrpc.php brute force and credential harvesting
- [[linux-privesc]] — post-exploitation after gaining WP shell

## Sources

- THM: Web Enumeration Redux (WPScan room)
- THM: Blog (blog)
- THM: Internal (internal)
