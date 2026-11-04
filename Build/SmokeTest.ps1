[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ReleaseDirectory,
    [int]$Port = 8765
)

$ErrorActionPreference = 'Stop'
$releaseRoot = [System.IO.Path]::GetFullPath($ReleaseDirectory)
$backendExe = Join-Path $releaseRoot 'Backend\BreakroomBackend.exe'
$gameExe = Join-Path $releaseRoot 'Breakroom.exe'
$contentPath = Join-Path $releaseRoot 'Content\NPCProfiles.json'

foreach ($requiredPath in @($backendExe, $gameExe, $contentPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Missing release artifact: $requiredPath"
    }
}

function Wait-Health {
    param(
        [int]$HealthPort,
        [int]$TimeoutSeconds = 45,
        [System.Diagnostics.Process]$OwnedProcess,
        [string]$LogPath = ''
    )
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        try {
            return Invoke-RestMethod -Uri "http://127.0.0.1:$HealthPort/health" -TimeoutSec 2
        }
        catch {
            Start-Sleep -Milliseconds 200
        }
    } while ([DateTime]::UtcNow -lt $deadline)
    if ($null -ne $OwnedProcess) {
        $OwnedProcess.Refresh()
        Write-Error "Owned process $($OwnedProcess.Id) exited=$($OwnedProcess.HasExited)." -ErrorAction Continue
        if ($OwnedProcess.HasExited) {
            Write-Error "Owned process exit code: $($OwnedProcess.ExitCode)." -ErrorAction Continue
        }
    }
    if ($LogPath -and (Test-Path -LiteralPath $LogPath)) {
        Get-Content -LiteralPath $LogPath -Tail 30 | Write-Error -ErrorAction Continue
    }
    throw "Health endpoint did not become ready on port $HealthPort."
}

function Stop-OwnedProcess {
    param([System.Diagnostics.Process]$Process, [string]$ExpectedCommand)
    if ($null -eq $Process -or $Process.HasExited) { return }
    $record = Get-CimInstance Win32_Process -Filter "ProcessId = $($Process.Id)" -ErrorAction SilentlyContinue
    if ($null -eq $record -or $record.CommandLine -notmatch [regex]::Escape($ExpectedCommand)) {
        throw "Refusing to stop an unverified process: $($Process.Id)"
    }
    Stop-Process -Id $Process.Id
    $Process.WaitForExit()
}

function Assert-PortFree {
    param([int]$TargetPort)
    $listener = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $TargetPort -State Listen -ErrorAction SilentlyContinue
    if ($listener) { throw "Port $TargetPort is still occupied." }
}

function Start-FrozenBackend {
    param([string]$DataDirectory, [int]$TargetPort)
    return Start-Process -FilePath $backendExe -ArgumentList @(
        '--port', "$TargetPort",
        '--data-dir', $DataDirectory,
        '--content-path', $contentPath
    ) -PassThru -WindowStyle Hidden
}

function Assert-ReleaseContents {
    $forbiddenNames = @('.env', '.git', '.godot', '__pycache__', '.pytest_cache', '.ruff_cache')
    $forbiddenExtensions = @(
        '.db', '.sqlite', '.sqlite3', '.log', '.py', '.pyc', '.pyo', '.ps1', '.spec'
    )
    foreach ($item in Get-ChildItem -LiteralPath $releaseRoot -Recurse -Force) {
        if ($forbiddenNames -contains $item.Name) {
            throw "Forbidden release item: $($item.FullName)"
        }
        if (-not $item.PSIsContainer -and $forbiddenExtensions -contains $item.Extension.ToLowerInvariant()) {
            throw "Forbidden release file: $($item.FullName)"
        }
        if ($item.FullName -match '[\\/]tests?[\\/]') {
            throw "Test content leaked into release: $($item.FullName)"
        }
    }
    $textExtensions = @('.txt', '.json', '.cfg', '.md', '.toml', '.ini')
    foreach ($file in Get-ChildItem -LiteralPath $releaseRoot -Recurse -File) {
        if ($textExtensions -notcontains $file.Extension.ToLowerInvariant()) { continue }
        $content = [System.IO.File]::ReadAllText($file.FullName)
        $keyAssignments = [regex]::Matches(
            $content,
            '(?im)^\s*(LLM_API_KEY|BREAKROOM_MODEL_API_KEY)\s*=\s*([^\s#]+)'
        )
        foreach ($assignment in $keyAssignments) {
            $value = $assignment.Groups[2].Value
            if ($value -notin @('your-api-key', '<your-api-key>', 'replace-me')) {
                throw "API key value found in release text: $($file.FullName)"
            }
        }
    }
}

Assert-ReleaseContents
Assert-PortFree -TargetPort $Port

$smokeRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("Breakroom-Smoke-" + [guid]::NewGuid())
$dataDir = Join-Path $smokeRoot 'Data'
$appDataDir = Join-Path $smokeRoot 'AppData'
$originalContent = [System.IO.File]::ReadAllText($contentPath)
New-Item -ItemType Directory -Path $dataDir, $appDataDir | Out-Null
$previousPath = $env:PATH
$previousAppData = $env:APPDATA
$smokeEnvironmentNames = @(
    'BREAKROOM_DIALOGUE_MODE',
    'BREAKROOM_MODEL_BASE_URL',
    'BREAKROOM_MODEL_NAME',
    'BREAKROOM_MODEL_API_KEY',
    'LLM_BASE_URL',
    'LLM_MODEL_ID',
    'LLM_API_KEY'
)
$previousEnvironment = @{}
foreach ($name in $smokeEnvironmentNames) {
    $previousEnvironment[$name] = [System.Environment]::GetEnvironmentVariable($name, 'Process')
    Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue
}
$env:APPDATA = $appDataDir
$smokeLog = Join-Path $appDataDir 'Breakroom\Logs\Breakroom.log'

try {
    $backend = Start-FrozenBackend -DataDirectory $dataDir -TargetPort $Port
    try {
        $health = Wait-Health -HealthPort $Port -OwnedProcess $backend -LogPath $smokeLog
        if ($health.status -ne 'ready' -or $health.dialogue_mode -ne 'mock') {
            throw 'Frozen backend did not start ready in mock mode.'
        }
        $requestId = [guid]::NewGuid().ToString()
        $dialogueBody = @{
            client_request_id = $requestId
            player_id = 'release-smoke-player'
            npc_id = 'zhang_xu'
            message = 'release build smoke test'
        } | ConvertTo-Json -Compress
        $dialogue = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/dialogues" -Method Post -ContentType 'application/json' -Body $dialogueBody -TimeoutSec 10
        if ($dialogue.reply_source -ne 'mock' -or [string]::IsNullOrWhiteSpace($dialogue.reply)) {
            throw 'Frozen backend mock dialogue failed.'
        }
    }
    finally {
        Stop-OwnedProcess -Process $backend -ExpectedCommand 'BreakroomBackend.exe'
    }
    Assert-PortFree -TargetPort $Port

    $document = $originalContent | ConvertFrom-Json
    $profile = $document.npcs | Where-Object { $_.npc_id -eq 'zhang_xu' }
    $profile.name = 'Zhang Xu Test'
    $profile.personality = @('release-config-personality')
    [System.IO.File]::WriteAllText(
        $contentPath,
        ($document | ConvertTo-Json -Depth 20),
        [System.Text.UTF8Encoding]::new($false)
    )

    $backend = Start-FrozenBackend -DataDirectory $dataDir -TargetPort $Port
    try {
        $null = Wait-Health -HealthPort $Port -OwnedProcess $backend -LogPath $smokeLog
        $npcs = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/npcs" -TimeoutSec 5
        $renamed = $npcs.npcs | Where-Object { $_.npc_id -eq 'zhang_xu' }
        if ($renamed.name -ne 'Zhang Xu Test') { throw 'External NPC name change was not loaded.' }
        $renamedDialogueBody = @{
            client_request_id = [guid]::NewGuid().ToString()
            player_id = 'release-smoke-player'
            npc_id = 'zhang_xu'
            message = 'verify renamed NPC dialogue'
        } | ConvertTo-Json -Compress
        $renamedDialogue = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/dialogues" -Method Post -ContentType 'application/json' -Body $renamedDialogueBody -TimeoutSec 10
        if ($renamedDialogue.npc.name -ne 'Zhang Xu Test' -or $renamedDialogue.reply_source -ne 'mock') {
            throw 'Dialogue did not use the updated NPC configuration.'
        }
        $history = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/v1/conversations/zhang_xu?player_id=release-smoke-player&limit=20" -TimeoutSec 5
        if ($history.messages.Count -ne 4) { throw 'NPC history was not preserved after config restart.' }
    }
    finally {
        Stop-OwnedProcess -Process $backend -ExpectedCommand 'BreakroomBackend.exe'
    }
    Assert-PortFree -TargetPort $Port
}
catch {
    $env:APPDATA = $previousAppData
    foreach ($name in $smokeEnvironmentNames) {
        [System.Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], 'Process')
    }
    if (Test-Path -LiteralPath $smokeRoot) { [System.IO.Directory]::Delete($smokeRoot, $true) }
    throw
}
finally {
    [System.IO.File]::WriteAllText($contentPath, $originalContent, [System.Text.UTF8Encoding]::new($false))
}

try {
    $env:PATH = "$env:SystemRoot\System32"
    $env:APPDATA = $appDataDir
    foreach ($attempt in 1..2) {
        Assert-PortFree -TargetPort $Port
        $game = Start-Process -FilePath $gameExe -ArgumentList @('--headless', '--quit-after', '900') -WorkingDirectory $releaseRoot -PassThru -WindowStyle Hidden
        $health = Wait-Health -HealthPort $Port -OwnedProcess $game -LogPath $smokeLog
        if ($health.status -ne 'ready' -or $health.dialogue_mode -ne 'mock') {
            throw "Game launch $attempt did not own a ready mock backend."
        }
        $game.WaitForExit()
        if ($game.ExitCode -ne 0) { throw "Game launch $attempt exited with code $($game.ExitCode)." }
        $deadline = [DateTime]::UtcNow.AddSeconds(5)
        while ([DateTime]::UtcNow -lt $deadline) {
            $listener = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
            if (-not $listener) { break }
            Start-Sleep -Milliseconds 100
        }
        Assert-PortFree -TargetPort $Port
    }
}
finally {
    $env:PATH = $previousPath
    $env:APPDATA = $previousAppData
    foreach ($name in $smokeEnvironmentNames) {
        [System.Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], 'Process')
    }
    if (Test-Path -LiteralPath $smokeRoot) { [System.IO.Directory]::Delete($smokeRoot, $true) }
}

Write-Host 'Release smoke tests passed: frozen backend, external content, history, clean PATH, two game launches, process cleanup.'
