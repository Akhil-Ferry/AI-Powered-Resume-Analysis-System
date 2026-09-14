# Stop only processes started by run.ps1; leave PostgreSQL data and service intact.
$ErrorActionPreference = "Stop"
$statePath = Join-Path $PSScriptRoot ".local\servers.json"
if (-not (Test-Path $statePath)) { Write-Output "No managed application servers."; exit }
$managed = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
foreach ($entry in $managed) {
    $serverProcess = Get-Process -Id $entry.id -ErrorAction SilentlyContinue
    if ($serverProcess -and $serverProcess.StartTime.ToUniversalTime().ToString("o") -eq $entry.started) {
        & taskkill.exe /PID $entry.id /T /F | Out-Null
        Write-Output "Stopped $($entry.name)."
    }
}
Set-Content -LiteralPath $statePath -Value "[]"
Write-Output "PostgreSQL remains running. Stop it separately with: backend\.venv\Scripts\python.exe scripts\local_db.py stop"
