# SA1 port adapt log - exploit/hunt slice (20 skills)

Date: 2026-10-17
Source: C:/Users/Lenovo/Documents/ObisidianVaults/HermesTORCH/skills/exploit/hunt
Dest:   C:/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills/exploit/hunt

Copy verification: diff -r --strip-trailing-cr -> all 20 skill dirs IDENTICAL, 0 missing files.
Adaptations applied (wsl claude cli seat):
1. CRLF -> LF on every file (repo .gitattributes enforces eol=lf; CRLF broke bash here before).
2. Seat-side VMshare paths: C:/Users/Lenovo/Desktop/VMshare -> /mnt/c/Users/Lenovo/Desktop/VMshare.
3. Transport: wsl.exe -d kali-linux -u root bash -c "cd .../HermesTORCH && bash scripts/vm-ssh.sh ..."
   -> plain shell: cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch && bash scripts/vm-ssh.sh '<command>'
   (vm-ssh.sh / kali-vm / tz@192.168.23.128 kept as-is; verified ZTorch/scripts/vm-ssh.sh exists.)
4. Comment 'seat side (Windows)' -> 'seat side (wsl)'.
Left unchanged (verified non-breaking): frontmatter 'metadata: hermes:' tags/related_skills (inert YAML),
VM-side /mnt/VMshare spelling, qmd/wiki MCP references, no LOCALAPPDATA/AppData/torch-skills/MEDID/MEMORY:/hermes-CLI hits in slice.

## hunt-ad
- hunt-ad/SKILL.md: ADAPTED
  - x325 before: '\r\n'
    after:  '\n'
  - x2 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'
  - x1 before: '# seat side (Windows)'
    after:  '# seat side (wsl)'
  - x1 before: 'wsl.exe -d kali-linux -u root bash -c "cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults...'
    after:  'cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch && bash scripts/vm-ssh.s...'
- hunt-ad/checklist.md: ADAPTED
  - x55 before: '\r\n'
    after:  '\n'
  - x1 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'

## hunt-ad-acl
- hunt-ad-acl/SKILL.md: ADAPTED
  - x234 before: '\r\n'
    after:  '\n'
  - x1 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'
  - x1 before: '# seat side (Windows)'
    after:  '# seat side (wsl)'
  - x1 before: 'wsl.exe -d kali-linux -u root bash -c "cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults...'
    after:  'cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch && bash scripts/vm-ssh.s...'
- hunt-ad-acl/checklist.md: ADAPTED
  - x55 before: '\r\n'
    after:  '\n'
  - x1 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'

## hunt-ad-adcs
- hunt-ad-adcs/SKILL.md: ADAPTED
  - x237 before: '\r\n'
    after:  '\n'
  - x1 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'
  - x1 before: '# seat side (Windows)'
    after:  '# seat side (wsl)'
  - x1 before: 'wsl.exe -d kali-linux -u root bash -c "cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults...'
    after:  'cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch && bash scripts/vm-ssh.s...'
- hunt-ad-adcs/checklist.md: ADAPTED
  - x58 before: '\r\n'
    after:  '\n'
  - x1 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'

## hunt-ad-kerberos
- hunt-ad-kerberos/SKILL.md: ADAPTED
  - x270 before: '\r\n'
    after:  '\n'
  - x1 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'
  - x1 before: '# seat side (Windows)'
    after:  '# seat side (wsl)'
  - x1 before: 'wsl.exe -d kali-linux -u root bash -c "cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults...'
    after:  'cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch && bash scripts/vm-ssh.s...'
- hunt-ad-kerberos/checklist.md: ADAPTED
  - x61 before: '\r\n'
    after:  '\n'
  - x1 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'

## hunt-api
- hunt-api/SKILL.md: ADAPTED
  - x470 before: '\r\n'
    after:  '\n'
  - x3 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'
  - x1 before: '# seat side (Windows)'
    after:  '# seat side (wsl)'
  - x1 before: 'wsl.exe -d kali-linux -u root bash -c "cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults...'
    after:  'cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch && bash scripts/vm-ssh.s...'
- hunt-api/checklist.md: ADAPTED
  - x70 before: '\r\n'
    after:  '\n'
  - x1 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'
- hunt-api/references/apq-replay.md: ADAPTED
  - x132 before: '\r\n'
    after:  '\n'

## hunt-auth
- hunt-auth/SKILL.md: ADAPTED
  - x464 before: '\r\n'
    after:  '\n'
  - x2 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'
  - x1 before: '# seat side (Windows)'
    after:  '# seat side (wsl)'
  - x1 before: 'wsl.exe -d kali-linux -u root bash -c "cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults...'
    after:  'cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch && bash scripts/vm-ssh.s...'
- hunt-auth/checklist.md: ADAPTED
  - x1 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'
- hunt-auth/references/test-account-minting.md: ADAPTED
  - x62 before: '\r\n'
    after:  '\n'

## hunt-bizlogic
- hunt-bizlogic/SKILL.md: ADAPTED
  - x380 before: '\r\n'
    after:  '\n'
  - x2 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'
  - x1 before: '# seat side (Windows)'
    after:  '# seat side (wsl)'
  - x1 before: 'wsl.exe -d kali-linux -u root bash -c "cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults...'
    after:  'cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch && bash scripts/vm-ssh.s...'
- hunt-bizlogic/checklist.md: ADAPTED
  - x1 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'

## hunt-cache
- hunt-cache/SKILL.md: ADAPTED
  - x299 before: '\r\n'
    after:  '\n'
  - x2 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'
  - x1 before: '# seat side (Windows)'
    after:  '# seat side (wsl)'
  - x1 before: 'wsl.exe -d kali-linux -u root bash -c "cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults...'
    after:  'cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch && bash scripts/vm-ssh.s...'
- hunt-cache/checklist.md: ADAPTED
  - x1 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'

## hunt-cicd
- hunt-cicd/SKILL.md: ADAPTED
  - x195 before: '\r\n'
    after:  '\n'
  - x2 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'
  - x1 before: '# seat side (Windows)'
    after:  '# seat side (wsl)'
  - x1 before: 'wsl.exe -d kali-linux -u root bash -c "cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults...'
    after:  'cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch && bash scripts/vm-ssh.s...'
- hunt-cicd/checklist.md: ADAPTED
  - x55 before: '\r\n'
    after:  '\n'
  - x1 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'

## hunt-cloud
- hunt-cloud/SKILL.md: ADAPTED
  - x361 before: '\r\n'
    after:  '\n'
  - x2 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'
  - x1 before: '# seat side (Windows)'
    after:  '# seat side (wsl)'
  - x1 before: 'wsl.exe -d kali-linux -u root bash -c "cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults...'
    after:  'cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch && bash scripts/vm-ssh.s...'
- hunt-cloud/checklist.md: ADAPTED
  - x58 before: '\r\n'
    after:  '\n'
  - x1 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'
- hunt-cloud/references/presigned-url-escalation.md: ADAPTED
  - x68 before: '\r\n'
    after:  '\n'

## hunt-core
- hunt-core/SKILL.md: ADAPTED
  - x433 before: '\r\n'
    after:  '\n'

## hunt-deserialization
- hunt-deserialization/SKILL.md: ADAPTED
  - x321 before: '\r\n'
    after:  '\n'
  - x2 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'
  - x1 before: '# seat side (Windows)'
    after:  '# seat side (wsl)'
  - x1 before: 'wsl.exe -d kali-linux -u root bash -c "cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults...'
    after:  'cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch && bash scripts/vm-ssh.s...'
- hunt-deserialization/checklist.md: ADAPTED
  - x54 before: '\r\n'
    after:  '\n'
  - x1 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'

## hunt-federation
- hunt-federation/SKILL.md: ADAPTED
  - x336 before: '\r\n'
    after:  '\n'
  - x2 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'
  - x1 before: '# seat side (Windows)'
    after:  '# seat side (wsl)'
  - x1 before: 'wsl.exe -d kali-linux -u root bash -c "cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults...'
    after:  'cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch && bash scripts/vm-ssh.s...'
- hunt-federation/checklist.md: ADAPTED
  - x61 before: '\r\n'
    after:  '\n'
  - x1 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'

## hunt-ics
- hunt-ics/SKILL.md: ADAPTED
  - x213 before: '\r\n'
    after:  '\n'
  - x1 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'
  - x1 before: '# seat side (Windows)'
    after:  '# seat side (wsl)'
  - x1 before: 'wsl.exe -d kali-linux -u root bash -c "cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults...'
    after:  'cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch && bash scripts/vm-ssh.s...'
- hunt-ics/checklist.md: ADAPTED
  - x55 before: '\r\n'
    after:  '\n'
  - x1 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'

## hunt-idor
- hunt-idor/SKILL.md: ADAPTED
  - x428 before: '\r\n'
    after:  '\n'
  - x2 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'
  - x1 before: '# seat side (Windows)'
    after:  '# seat side (wsl)'
  - x1 before: 'wsl.exe -d kali-linux -u root bash -c "cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults...'
    after:  'cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch && bash scripts/vm-ssh.s...'
- hunt-idor/checklist.md: ADAPTED
  - x1 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'

## hunt-injection
- hunt-injection/SKILL.md: ADAPTED
  - x419 before: '\r\n'
    after:  '\n'
  - x2 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'
  - x1 before: '# seat side (Windows)'
    after:  '# seat side (wsl)'
  - x1 before: 'wsl.exe -d kali-linux -u root bash -c "cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults...'
    after:  'cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch && bash scripts/vm-ssh.s...'
- hunt-injection/checklist.md: ADAPTED
  - x1 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'

## hunt-llm
- hunt-llm/SKILL.md: ADAPTED
  - x383 before: '\r\n'
    after:  '\n'
  - x2 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'
  - x1 before: '# seat side (Windows)'
    after:  '# seat side (wsl)'
  - x1 before: 'wsl.exe -d kali-linux -u root bash -c "cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults...'
    after:  'cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch && bash scripts/vm-ssh.s...'
- hunt-llm/checklist.md: ADAPTED
  - x1 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'

## hunt-m365
- hunt-m365/SKILL.md: ADAPTED
  - x351 before: '\r\n'
    after:  '\n'
  - x2 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'
  - x1 before: '# seat side (Windows)'
    after:  '# seat side (wsl)'
  - x1 before: 'wsl.exe -d kali-linux -u root bash -c "cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults...'
    after:  'cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch && bash scripts/vm-ssh.s...'
- hunt-m365/checklist.md: ADAPTED
  - x54 before: '\r\n'
    after:  '\n'
  - x1 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'

## hunt-macos
- hunt-macos/SKILL.md: ADAPTED
  - x253 before: '\r\n'
    after:  '\n'
  - x1 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'
  - x1 before: '# seat side (Windows)'
    after:  '# seat side (wsl)'
  - x1 before: 'wsl.exe -d kali-linux -u root bash -c "cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults...'
    after:  'cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch && bash scripts/vm-ssh.s...'
- hunt-macos/checklist.md: ADAPTED
  - x1 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'

## hunt-mcp
- hunt-mcp/SKILL.md: ADAPTED
  - x319 before: '\r\n'
    after:  '\n'
  - x2 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'
  - x1 before: '# seat side (Windows)'
    after:  '# seat side (wsl)'
  - x1 before: 'wsl.exe -d kali-linux -u root bash -c "cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults...'
    after:  'cd /mnt/c/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch && bash scripts/vm-ssh.s...'
- hunt-mcp/checklist.md: ADAPTED
  - x54 before: '\r\n'
    after:  '\n'
  - x1 before: 'C:/Users/Lenovo/Desktop/VMshare'
    after:  '/mnt/c/Users/Lenovo/Desktop/VMshare'
- hunt-mcp/references/user-connectors.md: ADAPTED
  - x60 before: '\r\n'
    after:  '\n'

Files adapted: 43
