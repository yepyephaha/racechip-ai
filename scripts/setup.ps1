param([switch]$SkipFrontendBuild)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python venv creation failed. Install Python 3.11+.' }
}
$requirementsFile = if (Test-Path -LiteralPath 'backend\requirements-lock.txt') { 'backend\requirements-lock.txt' } else { 'backend\requirements.txt' }
& '.\.venv\Scripts\python.exe' -m pip install -r $requirementsFile
if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
if ($SkipFrontendBuild) {
    if (-not (Test-Path -LiteralPath 'frontend\dist\index.html')) {
        throw 'Prebuilt frontend missing. Run setup.ps1 without -SkipFrontendBuild.'
    }
} else {
    Push-Location -LiteralPath 'frontend'
    try {
        npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
        npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    } finally { Pop-Location }
}
Write-Host 'Setup complete. Run: powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1'
