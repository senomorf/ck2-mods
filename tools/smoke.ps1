# Smoke-test a mod on Windows: boot CK2 with the mod, let it reach the main
# menu, close it, and show error.log lines that a vanilla boot does not have.
#
# Usage (from the repo folder, in PowerShell):
#   powershell -ExecutionPolicy Bypass -File tools\smoke.ps1 -Baseline            # once: boot without mods
#   powershell -ExecutionPolicy Bypass -File tools\smoke.ps1 allied_fleets        # each test
#
# Options:
#   -GameDir  CK2 install folder (default: Steam's usual path; pass it if yours differs)
#   -UserDir  CK2 user folder (default: Documents\Paradox Interactive\Crusader Kings II)
#   -Settle   seconds error.log must stay unchanged to count as "booted" (default 20)
#   -Timeout  seconds before giving up (default 300)
#   -GameArgs extra arguments for CK2game.exe
#
# UNVERIFIED (first runs will tell): that CK2game.exe accepts -skiplauncher and
# -mod=mod/<folder>.mod to boot straight into the game with that mod, and that
# an error.log that stops growing means the main menu is up. -debugscripts is
# documented in the game's ChangeLog.txt. The report says whether the mod's
# files were seen in the logs, so a mod that was not loaded doesn't pass.
#
# Results go to %LOCALAPPDATA%\ck2-mods\smoke\<mod>\ (report.txt plus copies
# of the logs). Upload report.txt, or error.log, to the PR or the chat.
param(
    [Parameter(Position = 0)][string]$Mod,
    [switch]$Baseline,
    [string]$GameDir = 'C:\Program Files (x86)\Steam\steamapps\common\Crusader Kings II',
    [string]$UserDir = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Paradox Interactive\Crusader Kings II'),
    [int]$Settle = 20,
    [int]$Timeout = 300,
    [string[]]$GameArgs = @()
)
$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $PSScriptRoot
if (-not $Baseline -and -not $Mod) { throw 'give a mod folder, or -Baseline' }
$Exe = Join-Path $GameDir 'CK2game.exe'
if (-not (Test-Path $Exe)) { throw "CK2game.exe not found in $GameDir (pass -GameDir)" }
$Logs = Join-Path $UserDir 'logs'
$Out = Join-Path $env:LOCALAPPDATA 'ck2-mods\smoke'
$Name = if ($Baseline) { '_baseline' } else { $Mod }
$Dest = Join-Path $Out $Name
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
$BaseLog = Join-Path $Out '_baseline\error.log'

$LaunchArgs = @('-skiplauncher', '-debugscripts') + $GameArgs
if (-not $Baseline) {
    if (-not (Test-Path $BaseLog)) { throw "no baseline yet: run with -Baseline first" }
    & (Join-Path $PSScriptRoot 'install.ps1') $Mod $UserDir
    $LaunchArgs += "-mod=mod/$Mod.mod"
}

if (Get-Process -Name CK2game -ErrorAction SilentlyContinue) { throw 'CK2 is already running; close it first' }
foreach ($f in 'error.log', 'game.log', 'system.log', 'setup.log') {
    $p = Join-Path $Logs $f
    if (Test-Path $p) { Remove-Item $p -Force }
}

Write-Host "starting: $Exe $($LaunchArgs -join ' ')"
$proc = Start-Process -FilePath $Exe -ArgumentList $LaunchArgs -WorkingDirectory $GameDir -PassThru
$err = Join-Path $Logs 'error.log'
$start = Get-Date
$lastSize = -1
$stableSince = Get-Date
$status = 'timeout'
while ($true) {
    Start-Sleep -Seconds 2
    if ($proc.HasExited) { $status = "exited early (code $($proc.ExitCode))"; break }
    $size = if (Test-Path $err) { (Get-Item $err).Length } else { 0 }
    if ($size -ne $lastSize) { $lastSize = $size; $stableSince = Get-Date }
    $elapsed = ((Get-Date) - $start).TotalSeconds
    if ($elapsed -gt 30 -and ((Get-Date) - $stableSince).TotalSeconds -ge $Settle) { $status = 'booted'; break }
    if ($elapsed -gt $Timeout) { break }
}
$secs = [int]((Get-Date) - $start).TotalSeconds
if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force; Start-Sleep -Seconds 2 }

foreach ($f in 'error.log', 'game.log', 'system.log', 'setup.log') {
    $p = Join-Path $Logs $f
    if (Test-Path $p) { Copy-Item $p (Join-Path $Dest $f) -Force }
}
if ($Baseline) {
    Write-Host "baseline saved to $Dest ($status after ${secs}s)"
    exit 0
}

# Lines are compared without their leading [time][file:line] tags.
function Normalize([string]$line) { ($line -replace '^(\[[^\]]*\])+\s*:?\s*', '').Trim() }
$base = @{}
foreach ($l in (Get-Content $BaseLog -Encoding Default -ErrorAction SilentlyContinue)) { $base[(Normalize $l)] = $true }
$cur = if (Test-Path (Join-Path $Dest 'error.log')) { Get-Content (Join-Path $Dest 'error.log') -Encoding Default } else { @() }
$new = $cur | ForEach-Object { Normalize $_ } | Where-Object { $_ -and -not $base.ContainsKey($_) } | Group-Object | Sort-Object Count -Descending

$prefix = (Get-Content (Join-Path $Repo "mods\$Mod\PREFIX") -ErrorAction SilentlyContinue | Select-Object -First 1)
$allLogs = Get-ChildItem $Dest -Filter *.log | ForEach-Object { Get-Content $_.FullName -Encoding Default }
$seen = [bool]($allLogs | Select-String -SimpleMatch -Pattern "mod/$Mod", "mod\$Mod", "$Mod.mod" -Quiet)

$report = @()
$report += "CK2 smoke test: $Mod"
$report += "result: $status after ${secs}s; args: $($LaunchArgs -join ' ')"
$report += "mod named in logs: $seen" + $(if (-not $seen) { '  (cannot confirm the mod loaded; the first runs will show whether CK2 logs it at all)' } else { '' })
$report += "new error.log lines vs baseline: $(($new | Measure-Object).Count)"
foreach ($g in $new) { $report += ('{0,4}x {1}' -f $g.Count, $g.Name) }
$report | Set-Content (Join-Path $Dest 'report.txt') -Encoding UTF8
$report | ForEach-Object { Write-Host $_ }
Write-Host "saved: $Dest"
if ($status -ne 'booted' -or ($new | Measure-Object).Count -gt 0) { exit 1 }
exit 0
