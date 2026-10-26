# searchsploit workflow (stage 4 input)

1. Input rows: `poc/<vhost>/js-lists/tech-versions.md` + stage-1 headers.
2. Run ON THE VM: `bash scripts/vm-ssh.sh 'searchsploit <tech> <version>'`
   (base64 block if quoted).
3. Each hit: version-match check, then wigolo for a public PoC before any
   local dev; verified rows go to `poc/<vhost>/version-research.md`
   (`| cve | tech@version | precondition | poc_ref | confidence |`).

## N/A escapes

- `N/A: no versioned tech surfaced by stage 1-2`
