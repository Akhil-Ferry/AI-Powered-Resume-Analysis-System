$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
Push-Location (Join-Path $projectRoot "backend")
try {
    uv sync
    if ($LASTEXITCODE -ne 0) { throw "Backend dependency installation failed." }
} finally { Pop-Location }
& "$projectRoot\backend\.venv\Scripts\python.exe" "$projectRoot\scripts\local_db.py" setup
if ($LASTEXITCODE -ne 0) { throw "PostgreSQL setup failed." }
Push-Location (Join-Path $projectRoot "backend")
try {
    & ".venv\Scripts\python.exe" manage.py upgrade
    if ($LASTEXITCODE -ne 0) { throw "Database migration failed." }
} finally { Pop-Location }
Push-Location (Join-Path $projectRoot "frontend")
try {
    if (-not (Test-Path ".env")) { Copy-Item -LiteralPath ".env.example" -Destination ".env" }
    npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed." }
} finally { Pop-Location }
Write-Output "Setup complete. Add OPENAI_API_KEY to backend/.env, save it, then run .\run.ps1."
