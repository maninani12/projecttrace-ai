$ErrorActionPreference = 'Stop'
$projectPath = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectPath '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run the README setup commands first.' }
$backendPath = Join-Path $projectPath 'backend'
$frontendPath = Join-Path $projectPath 'frontend'
New-Item -ItemType Directory -Path (Join-Path $projectPath '.storage') -Force | Out-Null
Push-Location -LiteralPath $backendPath
try { & $pythonPath -m alembic upgrade head; if ($LASTEXITCODE -ne 0) { throw 'Migration failed' } } finally { Pop-Location }
$apiProcess = Start-Process -FilePath $pythonPath -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000','--no-access-log' -WorkingDirectory $backendPath -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $projectPath '.storage/api-out.log') -RedirectStandardError (Join-Path $projectPath '.storage/api-error.log')
$workerProcess = Start-Process -FilePath $pythonPath -ArgumentList '-m','app.workers.runner' -WorkingDirectory $backendPath -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $projectPath '.storage/worker-out.log') -RedirectStandardError (Join-Path $projectPath '.storage/worker-error.log')
Write-Output "API PID: $($apiProcess.Id); Worker PID: $($workerProcess.Id)"
Write-Output 'Frontend runs in this terminal. Open http://127.0.0.1:5173 after Vite is ready.'
Push-Location -LiteralPath $frontendPath
try { & npm.cmd run dev } finally {
    Pop-Location
    # Windows virtualenv launchers spawn the interpreter as a child process.
    if (-not $apiProcess.HasExited) { & taskkill.exe /PID $apiProcess.Id /T /F | Out-Null }
    if (-not $workerProcess.HasExited) { & taskkill.exe /PID $workerProcess.Id /T /F | Out-Null }
}
