param([int]$Port = 8000, [string]$SearchCredentialsFile = '')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { throw 'Run scripts\setup.ps1 first.' }
if (-not (Test-Path -LiteralPath 'frontend\dist\index.html')) { throw 'Run scripts\setup.ps1 to build the frontend first.' }
Write-Host "RaceChip AI: http://127.0.0.1:$Port"
Write-Host 'SearchPro uses backend API KEY or TC3 credentials. Contextual dialogue uses a separate TokenHub key; open Model settings to configure locally.'
if ($SearchCredentialsFile) {
    & '.\.venv\Scripts\python.exe' '.\scripts\run_configured.py' --port $Port --search-credentials-file $SearchCredentialsFile
} else {
    & '.\.venv\Scripts\python.exe' '.\scripts\run_configured.py' --port $Port
}
exit $LASTEXITCODE
