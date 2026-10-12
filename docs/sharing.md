# Sharing TORCH (client-data boundary)

TORCH mixes shareable methodology with private client data. The split is enforced by git.

## The boundary

| Surface | Contains | Shareable? | Mechanism |
|---------|----------|-----------|-----------|
| git repo | AGENTS.md, `.zcode/config.json`, `skills/`, `scripts/`, `setup/`, `docs/`, `wiki/`* | **yes** | what you publish |
| Obsidian vault (full folder) | the above **plus** `targets/`, `session/`, `raw/` | **no** | private working copy |

`targets/`, `session/`, `raw/` are git-ignored (see `.gitignore`). They never enter the repo.

`targets/` is client data: engagement narrative lives ONLY in `targets/<eng>/` (see AGENTS.md).

**Backup assumption (verify on YOUR setup):** `targets/`, `session/`, `raw/` are git-ignored by design, so engagement data survives machine loss only through your own sync (this vault: Obsidian Sync). If that is NOT configured, snapshot before risky work: `tar czf raw/eng-backup-$(date +%F).tgz targets/<eng>/` (raw/ is also git-ignored). The wiki corpus IS tracked and ships with the repo (522+ pages, client-free by the leak gate).

## How to share

**Share the git repo, never the Obsidian vault folder.**

```bash
bash scripts/check-leaks.sh        # must print "clean"
git archive --format=tar.gz -o /tmp/torch-share.tar.gz HEAD
# or push the repo to a (private first, then public) remote
```

Copying the vault directory (zip, cloud folder, Obsidian Sync to a shared vault) **leaks `targets/`**. Don't.

## Leak check

`scripts/check-leaks.sh` greps every git-tracked file against the private term list `targets/scrub-terms.txt` (itself git-ignored, so it never ships). It fails if a client name, hostname, or IP appears in a shareable file.

- Add each engagement's markers (client name, internal hostnames, domains, IP ranges) to `targets/scrub-terms.txt` when you start.
- Run the check before every push / archive / handoff.

## Rules going forward

- **Code stays client-agnostic.** Hooks/scripts self-locate and read `targets/active.md`; no hardcoded client names or IPs. Keep it that way.
- **Docs/specs use placeholders** (`acme-internal`, `10.0.0.0/24`, `host1`), never real client data.
- **Commit messages** describe mechanism, not client specifics. Git history is hard to scrub; keep it clean from the start.
- **All client engagement data lives only under `targets/<engagement>/`** (state, loot, Killchain, ingest, findings, scope, poc).

## Trust model (what actually contains what)

Adopted from the hermes posture audit (docs/port-specs/proposals-posture.md): the ONLY hard
trust boundary in this harness is the Kali VM seat - lanes, hooks, and this session all run
on the operator's own box with the operator's own credentials. Everything else is convention
enforced by advisory machinery: scope-guard (out-of-scope deny), lane-guard (host-destructive
deny), session-guard (protected-config ask + client-marker warn), check-leaks (marker +
secret-shape scans at commit/share time). `targets/` is git-ignored and the client-data
boundary lives there; `.enforce-off` downgrades every deny, `.roe-ok`/`.cfg-edit-ok` are
short-lived operator consent markers (RoE tooling, harness-config edits). Never treat an
advisory as a boundary, and never assume a lane sees less than the operator's full environment:
credential-bearing env vars reach lanes only through explicit lane-manifest env names
(lane_manifest.py blocklist refuses provider keys outright).
