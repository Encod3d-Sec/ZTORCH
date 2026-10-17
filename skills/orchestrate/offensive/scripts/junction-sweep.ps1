# junction-sweep.ps1 - (re)junction every repo-ring skill into the desktop torch-skills set.
# Idempotent: existing junction dirs are left alone. Run after any skill-tree rework,
# new ring, or when G2 refuses a repo skill that plainly fired (see offensive SKILL.md
# G2 condition 3).
#
# Usage from the seat (git-bash):
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/junction-sweep.ps1
# Or inline (same logic, no file needed):
#   powershell.exe -NoProfile -Command "<paste the process block below>"

$ErrorActionPreference = 'Stop'
$repo = 'C:/Users/Lenovo/Documents/ObisidianVaults/ZTorch/ZTorch/skills'   # <-- adjust per seat
$ts = Join-Path $env:LOCALAPPDATA 'hermes	orch-skills'

if (-not (Test-Path $ts)) { New-Item -ItemType Directory -Path $ts | Out-Null }

# Recurse every ring dir; any subdir holding a SKILL.md is a junctionable skill.
# Nesting is unbounded (-Recurse): skills/exploit/hunt/hunt-xss and any deeper
# ring layout both get junctioned. Same-basename skills across rings collide on
# the torch-skills side; the first junction made wins and later ones report a
# COLLISION line (the known hunt-injection twin-dir case).
$made = 0
Get-ChildItem $repo -Directory | ForEach-Object {
    Get-ChildItem $_.FullName -Recurse -Directory | Where-Object {
        Test-Path (Join-Path $_.FullName 'SKILL.md')
    } | ForEach-Object {
        $dst = Join-Path $ts $_.Name
        if (-not (Test-Path $dst)) {
            New-Item -ItemType Junction -Path $dst -Target $_.FullName | Out-Null
            Write-Output ("junction: " + $_.Name)
            $made++
        } else {
            $item = Get-Item $dst -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                Write-Output ("skip-existing: " + $_.Name)
            } else {
                Write-Output ("COLLISION: " + $_.Name + " exists in torch-skills as a REAL dir - junction skipped, resolve by hand")
            }
        }
    }
}
Write-Output ("sweep done, new junctions: " + $made + ", total skills visible: " + (Get-ChildItem $ts).Count)
