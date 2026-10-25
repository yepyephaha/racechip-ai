$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
& '.\.venv\Scripts\python.exe' -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed.' }
Push-Location -LiteralPath 'frontend'
try {
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally { Pop-Location }
& '.\.venv\Scripts\python.exe' '.\scripts\smoke.py'
if ($LASTEXITCODE -ne 0) { throw 'API smoke test failed.' }
