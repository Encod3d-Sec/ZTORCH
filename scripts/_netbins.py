"""Single source of the network/scan/exploit binary set.

Shared by skills/hooks/drift-guard.py (drift accounting)
(the PreToolUse drift pre-filter). Kept in its own tiny module so the hook can import
it without parsing the ~90KB campaign.py on every Bash PreToolUse call.
"""
NET_BINS = {"curl", "wget", "nmap", "rustscan", "dnsx", "httpx", "nc", "ncat", "ffuf",
            "feroxbuster", "gobuster", "sqlmap", "nuclei", "nxc", "netexec", "katana",
            "gau", "subfinder", "amass", "nikto", "wpscan", "dig", "openssl", "hydra"}
