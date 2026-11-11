# Link a mod from this repo into the CK2 user mod folder (Windows).
# Usage: powershell -ExecutionPolicy Bypass -File tools\install.ps1 <mod_folder> [ck2_user_dir]
# Uses a directory junction, which needs no admin rights.
param(
    [Parameter(Mandatory = $true)][string]$Mod,
    [string]$UserDir = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Paradox Interactive\Crusader Kings II')
)
$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $PSScriptRoot
$Src = Join-Path $Repo "mods\$Mod"
if (-not (Test-Path $Src)) { throw "no mods\$Mod in repo" }
if (-not (Test-Path $UserDir)) { throw "CK2 user dir not found: $UserDir (pass it as 2nd argument)" }
$ModDir = Join-Path $UserDir 'mod'
New-Item -ItemType Directory -Force -Path $ModDir | Out-Null
$Link = Join-Path $ModDir $Mod
if (Test-Path $Link) { (Get-Item $Link).Delete() }
New-Item -ItemType Junction -Path $Link -Target $Src | Out-Null
Copy-Item (Join-Path $Repo "mods\$Mod.mod") (Join-Path $ModDir "$Mod.mod") -Force
Write-Host "linked $Link -> $Src"
Write-Host "copied $Mod.mod (re-run after changing the descriptor)"
