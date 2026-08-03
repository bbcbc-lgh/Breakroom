[CmdletBinding()]
param(
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version = '0.1.0',
    [string]$GodotPath = 'D:\Godot\Godot_v4.7.1-stable_win64.exe',
    [switch]$AllowDirty
)

$ErrorActionPreference = 'Stop'
$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$backendRoot = Join-Path $root 'Backend'
$godotRoot = Join-Path $root 'Game'
$packagingRoot = Join-Path $PSScriptRoot 'Packaging'
$python = Join-Path $backendRoot '.venv\Scripts\python.exe'
$templateRoot = Join-Path $env:APPDATA 'Godot\export_templates\4.7.1.stable'
$godotCli = $GodotPath
if (-not $GodotPath.EndsWith('_console.exe', [System.StringComparison]::OrdinalIgnoreCase)) {
    $consoleCandidate = $GodotPath.Substring(0, $GodotPath.Length - 4) + '_console.exe'
    if (Test-Path -LiteralPath $consoleCandidate -PathType Leaf) { $godotCli = $consoleCandidate }
}
$releaseName = "CyberTown-v$Version-windows-x86_64"
$releaseBase = Join-Path $root 'Release'
$releaseRoot = Join-Path $releaseBase $releaseName
$buildRoot = Join-Path $PSScriptRoot "Work\release-$Version"
$backendDist = Join-Path $buildRoot 'backend-dist'
$backendWork = Join-Path $buildRoot 'backend-work'
$zipPath = Join-Path $releaseBase "$releaseName.zip"
$hashPath = "$zipPath.sha256"

if (-not $AllowDirty) {
    $status = & git -C $root status --porcelain
    if ($LASTEXITCODE -ne 0) { throw 'Git status check failed.' }
    if ($status) { throw 'Git worktree is dirty. Commit or stash changes, or use -AllowDirty intentionally.' }
}

foreach ($required in @($GodotPath, $godotCli, $python, (Join-Path $godotRoot 'export_presets.cfg'))) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Missing build prerequisite: $required" }
}
foreach ($packagingFile in @('README.txt', 'LICENSES\Godot.txt', 'LICENSES\Font.txt', 'LICENSES\ThirdParty.txt')) {
    $packagingPath = Join-Path $packagingRoot $packagingFile
    if (-not (Test-Path -LiteralPath $packagingPath -PathType Leaf)) {
        throw "Missing packaging file: $packagingPath"
    }
}
$templates = @('windows_release_x86_64.exe', 'windows_release_x86_64_console.exe', 'icudt_godot.dat')
foreach ($template in $templates) {
    if (-not (Test-Path -LiteralPath (Join-Path $templateRoot $template))) { throw "Missing Godot export template: $template" }
}

foreach ($target in @($buildRoot, $releaseRoot, $zipPath, $hashPath)) {
    if (Test-Path -LiteralPath $target) {
        $resolved = [System.IO.Path]::GetFullPath($target)
        if (-not $resolved.StartsWith($root + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove path outside project: $resolved"
        }
        if ([System.IO.Directory]::Exists($resolved)) { [System.IO.Directory]::Delete($resolved, $true) }
        elseif ([System.IO.File]::Exists($resolved)) { [System.IO.File]::Delete($resolved) }
    }
}
New-Item -ItemType Directory -Path $releaseBase, $buildRoot, $releaseRoot -Force | Out-Null

Push-Location $backendRoot
try {
    & $python -m ruff check CyberTown tests RunBackend.py
    if ($LASTEXITCODE -ne 0) { throw 'Ruff failed.' }
    & $python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed.' }
    & $python -m PyInstaller --noconfirm --clean --distpath $backendDist --workpath $backendWork (Join-Path $PSScriptRoot 'CyberTownBackend.spec')
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
}
finally {
    Pop-Location
}

$frozenBackend = Join-Path $backendDist 'CyberTownBackend'
if (-not (Test-Path -LiteralPath (Join-Path $frozenBackend 'CyberTownBackend.exe'))) { throw 'Frozen backend executable is missing.' }
Copy-Item -LiteralPath $frozenBackend -Destination (Join-Path $releaseRoot 'Backend') -Recurse

& $godotCli --headless --path $godotRoot --import
if ($LASTEXITCODE -ne 0) { throw 'Godot import failed.' }
& $godotCli --headless --path $godotRoot --export-release 'Windows Desktop' (Join-Path $releaseRoot 'CyberTown.exe')
if ($LASTEXITCODE -ne 0) { throw 'Godot export failed.' }
foreach ($artifact in @('CyberTown.exe', 'CyberTown.pck')) {
    if (-not (Test-Path -LiteralPath (Join-Path $releaseRoot $artifact))) { throw "Godot artifact is missing: $artifact" }
}

New-Item -ItemType Directory -Path (Join-Path $releaseRoot 'Content') | Out-Null
Copy-Item -LiteralPath (Join-Path $root 'Content\NPCProfiles.json') -Destination (Join-Path $releaseRoot 'Content\NPCProfiles.json')
Copy-Item -LiteralPath (Join-Path $packagingRoot 'README.txt') -Destination (Join-Path $releaseRoot 'README.txt')
Copy-Item -LiteralPath (Join-Path $packagingRoot 'LICENSES') -Destination (Join-Path $releaseRoot 'LICENSES') -Recurse

& (Join-Path $PSScriptRoot 'SmokeTest.ps1') -ReleaseDirectory $releaseRoot
if ($LASTEXITCODE -ne 0) { throw 'Release smoke test failed.' }

Compress-Archive -LiteralPath $releaseRoot -DestinationPath $zipPath -CompressionLevel Optimal
$hash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
[System.IO.File]::WriteAllText($hashPath, "$hash  $([System.IO.Path]::GetFileName($zipPath))`n", [System.Text.UTF8Encoding]::new($false))

Write-Host "Release directory: $releaseRoot"
Write-Host "ZIP: $zipPath"
Write-Host "SHA-256: $hash"
