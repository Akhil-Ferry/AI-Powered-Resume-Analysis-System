# Starts the Flask API and React development server on Windows.
# One-time setup: run "uv sync" in backend and "npm install" in frontend.

$projectRoot = Split-Path -Parent $PSCommandPath
$backendPath = Join-Path $projectRoot "backend"
$frontendPath = Join-Path $projectRoot "frontend"

Write-Host "Starting backend on http://localhost:5000 ..."
$backend = Start-Process -FilePath "uv" -ArgumentList @("run", "python", "app.py") `
    -WorkingDirectory $backendPath -PassThru -NoNewWindow

Start-Sleep -Seconds 2
Write-Host "Starting frontend on http://localhost:5173 ..."
$frontend = Start-Process -FilePath "npm.cmd" -ArgumentList @("run", "dev") `
    -WorkingDirectory $frontendPath -PassThru -NoNewWindow

Write-Host "Press Ctrl+C to stop both servers."
try {
    Wait-Process -Id $backend.Id, $frontend.Id
}
finally {
    foreach ($process in @($backend, $frontend)) {
        if ($process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
        }
    }
}
