# Start PostgreSQL and both application servers in the background.
$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$localPath = Join-Path $projectRoot ".local"
$pythonPath = Join-Path $projectRoot "backend\.venv\Scripts\python.exe"
New-Item -ItemType Directory -Path $localPath -Force | Out-Null
if (Test-Path (Join-Path $localPath "postgres\PG_VERSION")) {
    & $pythonPath "$projectRoot\scripts\local_db.py" start
    if ($LASTEXITCODE -ne 0) { throw "Could not start project PostgreSQL." }
}
Push-Location (Join-Path $projectRoot "backend")
try {
    & $pythonPath manage.py upgrade
    if ($LASTEXITCODE -ne 0) { throw "Database migration failed." }
} finally { Pop-Location }

$managed = @()
$statePath = Join-Path $localPath "servers.json"
if (Test-Path $statePath) {
    foreach ($entry in (Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json)) {
        $managed += $entry
    }
}

function Test-ProjectServer($url, $marker) {
    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
        if ($response.Content -notmatch $marker) { throw "Port is occupied by another application: $url" }
        return $true
    } catch [System.Net.WebException] {
        return $false
    }
}

if (-not (Test-ProjectServer "http://127.0.0.1:5000/api/health" '"database":\s*"postgresql"')) {
    $apiProcess = Start-Process -FilePath $pythonPath -ArgumentList @("server.py") -WorkingDirectory "$projectRoot\backend" -WindowStyle Hidden -PassThru -RedirectStandardOutput "$localPath\backend.stdout.log" -RedirectStandardError "$localPath\backend.stderr.log"
    $managed += @{ id = $apiProcess.Id; started = $apiProcess.StartTime.ToUniversalTime().ToString("o"); name = "backend" }
}
if (-not (Test-ProjectServer "http://localhost:5174" "AI.*Resume")) {
    $nodePath = (Get-Command node.exe).Source
    $webProcess = Start-Process -FilePath $nodePath -ArgumentList @("node_modules/vite/bin/vite.js", "--port", "5174", "--strictPort") -WorkingDirectory "$projectRoot\frontend" -WindowStyle Hidden -PassThru -RedirectStandardOutput "$localPath\frontend.stdout.log" -RedirectStandardError "$localPath\frontend.stderr.log"
    $managed += @{ id = $webProcess.Id; started = $webProcess.StartTime.ToUniversalTime().ToString("o"); name = "frontend" }
}
ConvertTo-Json -InputObject $managed | Set-Content -LiteralPath $statePath
$ready = $false
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    if ((Test-ProjectServer "http://127.0.0.1:5000/api/health" '"database":\s*"postgresql"') -and (Test-ProjectServer "http://localhost:5174" "AI.*Resume")) {
        $ready = $true
        break
    }
    Start-Sleep -Milliseconds 250
}
if (-not $ready) { throw "Servers did not become ready. Check .local/*.log." }
Write-Output "App: http://localhost:5174 | API: http://localhost:5000"
Write-Output "Logs: .local/ | Stop application servers: .\stop.ps1"
